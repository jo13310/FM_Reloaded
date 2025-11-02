#!/usr/bin/env python3
# FM26 Mod Manager (FM_Reloaded_26)
# Cross-platform (macOS/Windows) GUI with:
# - Enable/disable mods, load order, filter by type
# - Import from .zip or folder
# - Conflict manager (detects overlapping target files; disable selected)
# - Restore points & rollback
# - Finder-safe file operations on macOS (no -R reveals)
# - Footer text credit line

import os, sys, json, shutil, hashlib, webbrowser, subprocess, zipfile, tempfile
from typing import Optional
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading

# Import new modules
try:
    from mod_store_api import ModStoreAPI, check_mod_updates
    from discord_webhook import DiscordChannels
    from bepinex_manager import BepInExManager, find_fm_install_dir
    from app_updater import AppUpdater
    ENHANCED_FEATURES = True
except ImportError as e:
    print(f"Warning: Enhanced features unavailable: {e}")
    ENHANCED_FEATURES = False

APP_NAME = "FM_Reloaded_26"
VERSION = "0.5.0"  # Updated version with enhanced features


# -----------------------
# Paths & storage helpers
# -----------------------
def _platform_tag():
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "other"


def legacy_appdata_dir() -> Path:
    """Older location we may migrate *from*."""
    if sys.platform.startswith("win"):
        base = os.getenv("APPDATA") or str(Path.home() / "AppData/Roaming")
        return Path(base) / APP_NAME
    else:
        # Old mac path placed under App Support/APP_NAME (same as new, but keep for completeness)
        return Path.home() / "Library/Application Support" / APP_NAME


def appdata_dir() -> Path:
    """Current storage base. Windows = %APPDATA%/APP_NAME ; macOS = ~/Library/Application Support/APP_NAME"""
    if sys.platform.startswith("win"):
        base = os.getenv("APPDATA") or str(Path.home() / "AppData/Roaming")
        p = Path(base) / APP_NAME
    else:
        p = Path.home() / "Library/Application Support" / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


BASE_DIR = appdata_dir()
CONFIG_PATH = BASE_DIR / "config.json"
BACKUP_DIR = BASE_DIR / "backups"
MODS_DIR = BASE_DIR / "mods"
LOGS_DIR = BASE_DIR / "logs"
RESTORE_POINTS_DIR = BASE_DIR / "restore_points"

RUN_LOG = LOGS_DIR / f"run_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
LAST_LINK = LOGS_DIR / "last_run.log"


def safe_open_path(path: Path):
    """Open folder/file (falls back to parent). Finder-safe (no -R)."""
    try:
        path = Path(path)
        target = path if path.exists() else path.parent
        if sys.platform.startswith("win"):
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target)], check=False)
    except Exception as e:
        messagebox.showerror("Open Error", f"Could not open:\n{path}\n\n{e}")


def _init_storage():
    for p in (BACKUP_DIR, MODS_DIR, LOGS_DIR, RESTORE_POINTS_DIR):
        p.mkdir(parents=True, exist_ok=True)
    # write "pointer" to last run log (symlink if allowed, else text)
    try:
        if LAST_LINK.exists() or LAST_LINK.is_symlink():
            try:
                LAST_LINK.unlink()
            except Exception:
                pass
        try:
            LAST_LINK.symlink_to(RUN_LOG.name)
        except Exception:
            LAST_LINK.write_text(str(RUN_LOG), encoding="utf-8")
    except Exception:
        pass


def migrate_legacy_storage_copy_only():
    old = legacy_appdata_dir()
    new = BASE_DIR
    try:
        if old.exists() and any(old.iterdir()) and not any(new.iterdir()):
            shutil.copytree(old, new, dirs_exist_ok=True)
    except Exception:
        pass


migrate_legacy_storage_copy_only()
_init_storage()


# -------------
# Config I/O
# -------------
def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_target() -> Path | None:
    p = load_config().get("target_path")
    return Path(p) if p else None


def set_target(path: Path):
    cfg = load_config()
    cfg["target_path"] = str(path)
    save_config(cfg)


def get_enabled_mods():
    return load_config().get("enabled_mods", [])


def set_enabled_mods(mods):
    cfg = load_config()
    cfg["enabled_mods"] = mods
    save_config(cfg)


def get_load_order():
    return load_config().get("load_order", [])


def set_load_order(order):
    cfg = load_config()
    cfg["load_order"] = order
    save_config(cfg)


def get_store_url():
    return load_config().get("store_url", "https://raw.githubusercontent.com/jo13310/FM_Reloaded_Trusted_Store/main/mods.json")


def set_store_url(url):
    cfg = load_config()
    cfg["store_url"] = url
    save_config(cfg)


def get_discord_webhooks():
    cfg = load_config()
    return {
        'error': cfg.get("discord_error_webhook", "https://discord.com/api/webhooks/1434612338970857474/D0pdw_G1lltO3ylLJv5DFu6aMXAgTrdqzH8iH-KUsyDmiKLQ5YYBqFRvdhI0S62tBNPp"),
        'mod_submission': cfg.get("discord_mod_webhook", "https://discord.com/api/webhooks/1434612412467904652/iF2wgQfFJoQRzXYzQZ-UtKfVDEAWSF-V-OLqp0MWl1BOGvda2ue4-SFaPVXxt77Eirxe")
    }


def set_discord_webhooks(error_url, mod_url):
    cfg = load_config()
    cfg["discord_error_webhook"] = error_url
    cfg["discord_mod_webhook"] = mod_url
    save_config(cfg)


# -----------------------
# Game detection (common)
# -----------------------
def default_candidates():
    """Try to discover the 'Standalone...' asset folder by platform."""
    home = Path.home()
    out = []
    if sys.platform.startswith("win"):
        steam = (
            Path(os.getenv("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
            / "Steam/steamapps/common/Football Manager 26"
        )
        epic = (
            Path(os.getenv("PROGRAMFILES", "C:/Program Files"))
            / "Epic Games/Football Manager 26"
        )
        for base in (steam, epic):
            for sub in (
                "fm_Data/StreamingAssets/aa/StandaloneWindows64",
                "data/StreamingAssets/aa/StandaloneWindows64",
            ):
                p = base / sub
                if p.exists():
                    out.append(p)
    else:
        # macOS
        for p in (
            home
            / "Library/Application Support/Steam/steamapps/common/Football Manager 26/fm.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX",
            home
            / "Library/Application Support/Steam/steamapps/common/Football Manager 26/fm_Data/StreamingAssets/aa/StandaloneOSXUniversal",
            home
            / "Library/Application Support/Epic/Football Manager 26/fm_Data/StreamingAssets/aa/StandaloneOSXUniversal",
        ):
            if p.exists():
                out.append(p)
    return out


def detect_and_set():
    c = default_candidates()
    if c:
        set_target(c[0])
        return c[0]
    return None


# -------------
# Manifest I/O
# -------------
def read_manifest(mod_dir: Path):
    mf = Path(mod_dir) / "manifest.json"
    if not mf.exists():
        raise FileNotFoundError(f"No manifest.json in {mod_dir}")
    data = json.loads(mf.read_text(encoding="utf-8"))
    # sensible defaults
    data.setdefault("type", "misc")
    data.setdefault("author", "")
    data.setdefault("homepage", "")
    data.setdefault("description", "")
    data.setdefault("compatibility", {})
    data.setdefault("dependencies", [])
    data.setdefault("conflicts", [])
    data.setdefault("load_after", [])
    data.setdefault("license", "")
    if "files" not in data or not isinstance(data["files"], list):
        data["files"] = []
    return data


def resolve_target(base: Path, sub: str) -> Path:
    return Path(base) / sub


# ----------
# Backups
# ----------
def backup_original(target_file: Path):
    if not Path(target_file).exists():
        return None
    h = hashlib.sha256(str(target_file).encode("utf-8")).hexdigest()[:10]
    dest = BACKUP_DIR / f"{Path(target_file).name}.{h}.bak"
    i, final = 1, dest
    while final.exists():
        final = BACKUP_DIR / f"{dest.name}.{i}"
        i += 1
    shutil.copy2(target_file, final)
    return final


def find_latest_backup_for_filename(filename: str):
    cands = sorted(
        [p for p in BACKUP_DIR.glob(f"{filename}*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None


# -------------
# Mod actions
# -------------
def enable_mod(mod_name: str, log):
    mod_dir = MODS_DIR / mod_name
    if not mod_dir.exists():
        raise FileNotFoundError(f"Mod not found: {mod_name} in {MODS_DIR}")
    mf = read_manifest(mod_dir)
    base = get_target()
    if not base or not base.exists():
        raise RuntimeError("No valid FM26 target set. Use Detect or Set Target.")
    files = mf.get("files", [])
    if not files:
        raise ValueError("Manifest has no 'files' entries.")
    plat = _platform_tag()
    log(f"[enable] {mf.get('name', mod_name)}  →  {base}")
    log(f"  [context] platform={plat} files={len(files)}")
    wrote = skipped = backed_up = errors = 0
    for e in files:
        ep = e.get("platform")
        src_rel = e.get("source")
        tgt_rel = e.get("target_subpath")
        if ep and ep != plat:
            log(f"  [skip/platform] {src_rel} (entry platform={ep})")
            skipped += 1
            continue
        if not src_rel or not tgt_rel:
            log(f"  [error/entry] Missing 'source' or 'target_subpath' in {e}")
            errors += 1
            continue
        src = mod_dir / src_rel
        tgt = resolve_target(base, tgt_rel)
        if not src.exists():
            log(f"  [error/missing] Source not found: {src}")
            errors += 1
            continue
        try:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            if tgt.exists():
                b = backup_original(tgt)
                log(f"  [backup] {tgt_rel}  ←  {b.name if b else 'skipped'}")
                backed_up += 1
            shutil.copy2(src, tgt)
            log(f"  [write] {src_rel}  →  {tgt_rel}")
            wrote += 1
        except Exception as ex:
            log(f"  [error/copy] {src_rel} → {tgt_rel} :: {ex}")
            errors += 1
    log(
        f"[enable/done] wrote={wrote} backup={backed_up} skipped={skipped} errors={errors}"
    )


def disable_mod(mod_name: str, log):
    mod_dir = MODS_DIR / mod_name
    mf = read_manifest(mod_dir)
    base = get_target()
    if not base or not base.exists():
        raise RuntimeError("No valid FM26 target set. Use Detect or Set Target.")
    files = mf.get("files", [])
    if not files:
        log("[disable] Manifest has no files to disable.")
        return
    log(f"[disable] {mf.get('name', mod_name)}  from  {base}")
    removed = restored = missing_backup = not_present = errors = 0
    for e in files:
        tgt_rel = e.get("target_subpath")
        if not tgt_rel:
            log(f"  [error/entry] Missing 'target_subpath' in {e}")
            errors += 1
            continue
        tgt = resolve_target(base, tgt_rel)
        if tgt.exists():
            try:
                tgt.unlink()
                log(f"  [remove] {tgt_rel}")
                removed += 1
                b = find_latest_backup_for_filename(tgt.name)
                if b and b.exists():
                    shutil.copy2(b, tgt)
                    log(f"  [restore] {b.name}  →  {tgt_rel}")
                    restored += 1
                else:
                    log(f"  [no-backup] {tgt.name} (left removed)")
                    missing_backup += 1
            except Exception as ex:
                log(f"  [error/remove] {tgt_rel} :: {ex}")
                errors += 1
        else:
            log(f"  [absent] {tgt_rel}")
            not_present += 1
    log(
        f"[disable/done] removed={removed} restored={restored} no_backup={missing_backup} absent={not_present} errors={errors}"
    )


def install_mod_from_folder(src_folder: Path, name_override: str | None, log=None):
    src_folder = Path(src_folder).resolve()
    if not (src_folder / "manifest.json").exists():
        raise FileNotFoundError("Selected folder does not contain a manifest.json")
    mf = json.loads((src_folder / "manifest.json").read_text(encoding="utf-8"))
    name = (name_override or mf.get("name") or src_folder.name).strip()
    if not name:
        raise ValueError("Mod name cannot be empty.")
    dest = MODS_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src_folder, dest)
    if log:
        log(f"Installed mod '{name}' to {dest}")
    return name


# ----------------
# Conflict detect
# ----------------
def build_mod_index(names=None):
    if names is None:
        names = [p.name for p in MODS_DIR.iterdir() if p.is_dir()]
    manifests = {}
    idx = {}
    for m in names:
        mf = read_manifest(MODS_DIR / m)
        manifests[m] = mf
        for f in mf.get("files", []):
            tgt = f.get("target_subpath")
            if not tgt:
                continue
            idx.setdefault(tgt, []).append(m)
    return idx, manifests


def find_conflicts(names=None):
    """Return {target_subpath: [mods...]} and manifests dict."""
    idx, manifests = build_mod_index(names)
    conflicts = {t: ms for t, ms in idx.items() if len(ms) > 1}
    return conflicts, manifests


# --------------------
# Restore points
# --------------------
def create_restore_point(base: Path, log):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rp = RESTORE_POINTS_DIR / ts
    rp.mkdir(parents=True, exist_ok=True)
    idx, _ = build_mod_index(get_enabled_mods())
    for rel in idx.keys():
        src = base / rel
        if src.exists() and src.is_file():
            dst = rp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    log(f"Restore point created: {rp.name}")
    return rp.name


def rollback_to_restore_point(name: str, base: Path, log):
    rp = RESTORE_POINTS_DIR / name
    if not rp.exists():
        raise FileNotFoundError("Restore point not found.")
    for p in rp.rglob("*"):
        if p.is_file():
            rel = p.relative_to(rp)
            dst = base / rel.as_posix()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    log(f"Rolled back to restore point: {name}")


# --------------
# Apply order
# --------------
def apply_enabled_mods_in_order(log):
    base = get_target()
    if not base or not base.exists():
        raise RuntimeError("No valid FM26 target set. Use Detect or Set Target.")
    enabled = get_enabled_mods()
    order = get_load_order()
    ordered = [m for m in order if m in enabled] + [
        m for m in enabled if m not in order
    ]
    if not ordered:
        log("No enabled mods to apply.")
        return
    rp = create_restore_point(base, log)
    for name in ordered:
        try:
            enable_mod(name, log)
        except Exception as ex:
            log(f"[WARN] Failed enabling {name}: {ex}")
    log(
        f"Applied {len(ordered)} mod(s) in order (last-write-wins). Restore point: {rp}"
    )


# ==========
#   GUI
# ==========
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"FM Reloaded Mod Manager v{VERSION}")
        self.geometry("1200x900")
        self.minsize(1100, 800)

        # Initialize enhanced features
        if ENHANCED_FEATURES:
            self.mod_store_api = ModStoreAPI(get_store_url())
            webhooks = get_discord_webhooks()
            self.discord = DiscordChannels(webhooks['error'], webhooks['mod_submission'])
            fm_dir = find_fm_install_dir()
            self.bepinex_manager = BepInExManager(fm_dir) if fm_dir else None
        else:
            self.mod_store_api = None
            self.discord = None
            self.bepinex_manager = None

        self.create_widgets()
        self.refresh_target_display()
        self.refresh_mod_list()
        self._log("Ready.")

        # Auto-check for updates if enabled
        if ENHANCED_FEATURES and load_config().get("auto_check_updates", True):
            self.after(2000, self._auto_check_updates)  # Check after 2 seconds

    # ---- logging ----
    def _log(self, msg: str):
        try:
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        except Exception:
            pass
        try:
            with open(RUN_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    # ---- UI layout ----
    def create_widgets(self):
        # Menus
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Detect Target\tCtrl+D", command=self.on_detect)
        file_menu.add_command(label="Set Target…\tCtrl+O", command=self.on_set_target)
        file_menu.add_separator()
        file_menu.add_command(label="Open Target", command=self.on_open_target)
        file_menu.add_command(label="Open Mods Folder", command=self.on_open_mods)
        file_menu.add_command(label="Open Logs Folder", command=self.on_open_logs_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        actions_menu = tk.Menu(menubar, tearoff=0)
        actions_menu.add_command(label="Apply Order\tF5", command=self.on_apply_order)
        actions_menu.add_command(label="Conflicts…", command=self.on_conflicts)
        actions_menu.add_command(label="Rollback…", command=self.on_rollback)
        if ENHANCED_FEATURES:
            actions_menu.add_separator()
            actions_menu.add_command(label="Generate Mod Template…", command=self.on_generate_template)
        menubar.add_cascade(label="Actions", menu=actions_menu)

        # Settings menu (if enhanced features available)
        if ENHANCED_FEATURES:
            settings_menu = tk.Menu(menubar, tearoff=0)
            settings_menu.add_command(label="Preferences…", command=self.on_settings)
            menubar.add_cascade(label="Settings", menu=settings_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Manifest Help", command=self.on_show_manifest_help)
        if ENHANCED_FEATURES:
            help_menu.add_command(label="Check for Updates…", command=self.on_check_updates)
        help_menu.add_separator()
        help_menu.add_command(label="About FM Reloaded", command=self.on_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

        # Shortcuts
        self.bind_all("<Control-d>", lambda e: self.on_detect())
        self.bind_all("<Control-o>", lambda e: self.on_set_target())
        self.bind_all("<F5>", lambda e: self.on_apply_order())
        if sys.platform == "darwin":
            self.bind_all("<Command-d>", lambda e: self.on_detect())
            self.bind_all("<Command-o>", lambda e: self.on_set_target())

        # Target row (shared across all tabs)
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)
        self.target_var = tk.StringVar()
        ttk.Label(top, text="Target:").pack(side=tk.LEFT)
        self.target_entry = ttk.Entry(top, textvariable=self.target_var, width=120)
        self.target_entry.pack(side=tk.LEFT, padx=(4, 6))
        ttk.Button(top, text="Detect", command=self.on_detect).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="Set…", command=self.on_set_target).pack(side=tk.LEFT, padx=2)

        # Create Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Tab 1: My Mods
        self.create_my_mods_tab()

        # Tab 2: Mod Store (if enhanced features available)
        if ENHANCED_FEATURES and self.mod_store_api:
            self.create_mod_store_tab()

        # Tab 3: BepInEx (if enhanced features available)
        if ENHANCED_FEATURES and self.bepinex_manager:
            self.create_bepinex_tab()

        # Log pane (shared, below tabs)
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))
        self.log_text = tk.Text(log_frame, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Footer with credits and Discord buttons
        self.create_footer()

    def create_my_mods_tab(self):
        """Create the My Mods tab (original mod manager functionality)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Mods")

        # Controls row
        flt = ttk.Frame(tab)
        flt.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        self.type_filter = tk.StringVar(value="(all)")
        self.type_combo = ttk.Combobox(
            flt,
            textvariable=self.type_filter,
            width=18,
            state="readonly",
            values=["(all)", "ui", "skins", "database", "ruleset", "graphics", "audio", "tactics", "misc"],
        )
        self.type_combo.pack(side=tk.RIGHT, padx=6)
        ttk.Label(flt, text="Filter mod type:").pack(side=tk.RIGHT)
        self.type_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_mod_list())

        # Main list + right panel
        mid = ttk.Frame(tab)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        cols = ("name", "version", "type", "author", "order", "enabled", "update")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
        self.tree.column("name", width=280, anchor="w")
        self.tree.column("version", width=80, anchor="w")
        self.tree.column("type", width=100, anchor="w")
        self.tree.column("author", width=140, anchor="w")
        self.tree.column("order", width=50, anchor="center")
        self.tree.column("enabled", width=70, anchor="center")
        self.tree.column("update", width=70, anchor="center")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)

        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(right, text="Refresh", command=self.refresh_mod_list).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Import Mod…", command=self.on_import_mod).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Enable (mark)", command=self.on_enable_selected).pack(fill=tk.X, pady=(12, 2))
        ttk.Button(right, text="Disable (unmark)", command=self.on_disable_selected).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Up (Order)", command=self.on_move_up).pack(fill=tk.X, pady=(12, 2))
        ttk.Button(right, text="Down (Order)", command=self.on_move_down).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Apply Order", command=self.on_apply_order).pack(fill=tk.X, pady=(12, 2))
        ttk.Button(right, text="Conflicts…", command=self.on_conflicts).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Rollback…", command=self.on_rollback).pack(fill=tk.X, pady=(12, 2))
        ttk.Button(right, text="Open Mods Folder", command=self.on_open_mods).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Help (Manifest)", command=self.on_show_manifest_help).pack(fill=tk.X, pady=(12, 2))

        # Details pane
        det = ttk.LabelFrame(tab, text="Details")
        det.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))
        self.details_text = tk.Text(det, height=6)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

    def create_footer(self):
        """Create footer with credits and Discord buttons."""
        footer = ttk.Frame(self)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)

        # Left side: Credits
        credits_left = ttk.Label(
            footer,
            text="Created by Justin Levine & FM Match Lab Team",
            anchor="w"
        )
        credits_left.pack(side=tk.LEFT)

        # Center: Forked by
        credits_center = ttk.Label(
            footer,
            text=" | Forked & Enhanced by GerKo",
            anchor="center"
        )
        credits_center.pack(side=tk.LEFT)

        # Right side: Discord buttons (if enhanced features available)
        if ENHANCED_FEATURES and self.discord:
            btn_frame = ttk.Frame(footer)
            btn_frame.pack(side=tk.RIGHT)
            ttk.Button(btn_frame, text="Report Bug", command=self.on_report_bug).pack(side=tk.LEFT, padx=2)
            ttk.Button(btn_frame, text="Submit Mod", command=self.on_submit_mod).pack(side=tk.LEFT, padx=2)

    def create_mod_store_tab(self):
        """Create the Mod Store browser tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Mod Store")

        # Top controls
        controls = ttk.Frame(tab)
        controls.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        ttk.Label(controls, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.store_search_var = tk.StringVar()
        search_entry = ttk.Entry(controls, textvariable=self.store_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(controls, text="Search", command=self.on_store_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls, text="Refresh Store", command=self.on_store_refresh).pack(side=tk.LEFT, padx=2)

        # Store mod list + details
        mid = ttk.Frame(tab)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        cols = ("name", "version", "type", "author", "downloads")
        self.store_tree = ttk.Treeview(mid, columns=cols, show="headings", height=15)
        for c in cols:
            self.store_tree.heading(c, text=c.capitalize())
        self.store_tree.column("name", width=300, anchor="w")
        self.store_tree.column("version", width=80, anchor="w")
        self.store_tree.column("type", width=100, anchor="w")
        self.store_tree.column("author", width=150, anchor="w")
        self.store_tree.column("downloads", width=80, anchor="center")
        self.store_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.store_tree.yview)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.store_tree.configure(yscrollcommand=sb.set)

        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(right, text="Install Selected", command=self.on_store_install).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="View Details", command=self.on_store_details).pack(fill=tk.X, pady=2)

        # Details pane
        det = ttk.LabelFrame(tab, text="Mod Details")
        det.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))
        self.store_details_text = tk.Text(det, height=6)
        self.store_details_text.pack(fill=tk.BOTH, expand=True)
        self.store_tree.bind("<<TreeviewSelect>>", self.on_store_select_row)

        # Load store mods
        self.refresh_store_mods()

    def create_bepinex_tab(self):
        """Create the BepInEx management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="BepInEx")

        # Status section
        status_frame = ttk.LabelFrame(tab, text="Installation Status")
        status_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        self.bepinex_status_var = tk.StringVar(value="Checking...")
        ttk.Label(status_frame, textvariable=self.bepinex_status_var, font=("", 10, "bold")).pack(padx=10, pady=10)

        # Installation section
        install_frame = ttk.LabelFrame(tab, text="Installation")
        install_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        ttk.Button(install_frame, text="Install BepInEx", command=self.on_bepinex_install).pack(padx=10, pady=5, fill=tk.X)
        ttk.Label(install_frame, text="Installs BepInEx from BepInEx_Patched_Win_af0cba7.rar", font=("", 8)).pack(padx=10, pady=(0, 10))

        # Configuration section
        config_frame = ttk.LabelFrame(tab, text="Configuration")
        config_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        self.bepinex_console_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            config_frame,
            text="Enable Console Logging (shows console window)",
            variable=self.bepinex_console_var,
            command=self.on_bepinex_toggle_console
        ).pack(padx=10, pady=5, anchor="w")

        ttk.Button(config_frame, text="Open BepInEx Config File", command=self.on_bepinex_open_config).pack(padx=10, pady=5, fill=tk.X)

        # Logs section
        logs_frame = ttk.LabelFrame(tab, text="Logs & Debugging")
        logs_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        ttk.Button(logs_frame, text="View Latest Log", command=self.on_bepinex_view_log).pack(padx=10, pady=5, fill=tk.X)
        ttk.Button(logs_frame, text="Open BepInEx Folder", command=self.on_bepinex_open_folder).pack(padx=10, pady=5, fill=tk.X)

        # Update status
        self.refresh_bepinex_status()

    # ---- menu/button actions ----
    def on_copy_log_path(self):
        self.clipboard_clear()
        self.clipboard_append(str(RUN_LOG))
        self._log(f"Copied log path: {RUN_LOG}")

    def on_open_logs_folder(self):
        safe_open_path(LOGS_DIR)

    def refresh_target_display(self):
        t = get_target()
        self.target_var.set(str(t) if t else "")

    def refresh_mod_list(self):
        # clear
        for i in self.tree.get_children():
            self.tree.delete(i)
        wanted = self.type_filter.get()
        order = get_load_order()
        enabled = set(get_enabled_mods())

        # Check for updates if enhanced features available
        updates = {}
        if ENHANCED_FEATURES and self.mod_store_api:
            try:
                installed_mods = {}
                for p in MODS_DIR.iterdir():
                    if p.is_dir():
                        try:
                            mf = read_manifest(p)
                            installed_mods[mf.get("name", p.name)] = mf.get("version", "0.0.0")
                        except:
                            pass
                updates = self.mod_store_api.check_for_updates(installed_mods)
            except Exception as e:
                self._log(f"Update check failed: {e}")

        rows = []
        # list dirs
        for p in MODS_DIR.iterdir():
            if p.is_dir():
                try:
                    mf = read_manifest(p)
                    mtype = mf.get("type", "misc")
                    if wanted != "(all)" and mtype != wanted:
                        continue
                    ord_idx = order.index(p.name) if p.name in order else -1
                    ord_disp = (ord_idx + 1) if ord_idx >= 0 else ""
                    ena = "yes" if p.name in enabled else ""
                    update_available = "⬆" if mf.get("name") in updates else ""
                    rows.append(
                        (
                            (
                                p.name,
                                mf.get("version", ""),
                                mtype,
                                mf.get("author", ""),
                                ord_disp,
                                ena,
                                update_available,
                            ),
                            mf,
                        )
                    )
                except Exception:
                    rows.append(((p.name, "?", "?", "?", "", "", ""), None))
        for row, _ in rows:
            self.tree.insert("", tk.END, values=row)
        self._log(f"Loaded {len(rows)} mod(s) (filter: {wanted}).")
        if updates:
            self._log(f"ℹ {len(updates)} mod(s) have updates available in the store.")
        enabled = get_enabled_mods()
        conflicts, _ = find_conflicts(enabled if enabled else None)
        if conflicts:
            self._log(
                f"⚠️ Detected {len(conflicts)} file conflict(s) among enabled mods — opening conflict manager."
            )
            self.after(500, self.on_conflicts)

    def selected_mod_name(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"][0]

    def on_detect(self):
        t = detect_and_set()
        if t:
            self._log(f"Detected target: {t}")
        else:
            messagebox.showwarning(
                "Detect",
                "Could not auto-detect FM26 Standalone folder.\nSet it manually.",
            )
        self.refresh_target_display()

    def on_set_target(self):
        chosen = filedialog.askdirectory(
            title="Select FM26 Standalone folder (StandaloneWindows64/StandaloneOSX/OSXUniversal)"
        )
        if not chosen:
            return
        p = Path(chosen).expanduser()
        if not p.exists():
            messagebox.showerror("Set Target", "Selected path does not exist.")
            return
        if "Standalone" not in p.name:
            if not messagebox.askyesno(
                "Confirm",
                f"Selected folder does not contain 'Standalone' in its name.\nUse anyway?\n\n{p}",
            ):
                return
        set_target(p)
        self._log(f"Set target to: {p}")
        self.refresh_target_display()

    def _choose_import_source(self) -> Path | None:
        """Small helper: ask whether to import from ZIP or Folder, then show proper dialog."""
        if messagebox.askyesno(
            "Import", "Import from a .zip file?\n\nClick 'No' to pick a folder instead."
        ):
            path = filedialog.askopenfilename(
                title="Select Mod .zip", filetypes=[("Zip archives", "*.zip")]
            )
            return Path(path) if path else None
        else:
            folder = filedialog.askdirectory(
                title="Select Mod Folder (must contain manifest.json)"
            )
            return Path(folder) if folder else None

    def on_import_mod(self):
        choice = self._choose_import_source()
        if not choice:
            return
        temp_dir = None
        try:
            if choice.is_file() and choice.suffix.lower() == ".zip":
                temp_dir = Path(tempfile.mkdtemp(prefix="fm26_import_"))
                with zipfile.ZipFile(choice, "r") as z:
                    z.extractall(temp_dir)
                # try to find a child folder with manifest.json, else use root
                candidates = [
                    d
                    for d in temp_dir.iterdir()
                    if d.is_dir() and (d / "manifest.json").exists()
                ]
                src_folder = (
                    candidates[0]
                    if candidates
                    else (temp_dir if (temp_dir / "manifest.json").exists() else None)
                )
                if src_folder is None:
                    # as a fallback, if there's exactly one directory, use it
                    subs = [d for d in temp_dir.iterdir() if d.is_dir()]
                    src_folder = subs[0] if subs else temp_dir
            else:
                src_folder = choice
            newname = install_mod_from_folder(src_folder, None, log=self._log)
            order = get_load_order()
            if newname not in order:
                order.append(newname)
                set_load_order(order)
            self.refresh_mod_list()
            messagebox.showinfo("Import", f"Imported '{newname}'.")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def on_enable_selected(self):
        name = self.selected_mod_name()
        if not name:
            messagebox.showinfo("Mods", "Select a mod first.")
            return
        enabled = get_enabled_mods()
        if name not in enabled:
            enabled.append(name)
            set_enabled_mods(enabled)
            self._log(f"Enabled (marked) '{name}'. Use Apply Order to write files.")
            self.refresh_mod_list()
        else:
            messagebox.showinfo("Mods", f"'{name}' already enabled (marked).")

    def on_disable_selected(self):
        name = self.selected_mod_name()
        if not name:
            messagebox.showinfo("Mods", "Select a mod first.")
            return
        enabled = [m for m in get_enabled_mods() if m != name]
        set_enabled_mods(enabled)
        self._log(
            f"Disabled (unmarked) '{name}'. Apply Order to rewrite files without it."
        )
        self.refresh_mod_list()

    def on_move_up(self):
        name = self.selected_mod_name()
        if not name:
            return
        order = get_load_order()
        if name not in order:
            order.append(name)
        i = order.index(name)
        if i > 0:
            order[i - 1], order[i] = order[i], order[i - 1]
            set_load_order(order)
            self._log(f"Moved up: {name}")
            self.refresh_mod_list()

    def on_move_down(self):
        name = self.selected_mod_name()
        if not name:
            return
        order = get_load_order()
        if name not in order:
            order.append(name)
        i = order.index(name)
        if i < len(order) - 1:
            order[i + 1], order[i] = order[i], order[i + 1]
            set_load_order(order)
            self._log(f"Moved down: {name}")
            self.refresh_mod_list()

    def on_apply_order(self):
        try:
            apply_enabled_mods_in_order(self._log)
            messagebox.showinfo(
                "Apply Order",
                "All enabled mods applied in load order.\n(Last-write-wins).",
            )
        except Exception as e:
            messagebox.showerror("Apply Order Error", str(e))

    def on_conflicts(self):
        enabled = get_enabled_mods()
        conflicts, manifests = find_conflicts(enabled if enabled else None)
        if not conflicts:
            messagebox.showinfo("Conflicts", "No file overlaps among enabled mods.")
            return

        order = get_load_order()
        win = tk.Toplevel(self)
        win.title("Conflict Manager — FM26 Mod Manager")
        win.geometry("760x560")

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        text = tk.Text(frame, wrap="word", height=18)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(frame, command=text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        text.configure(yscrollcommand=sb.set)

        text.insert(
            tk.END, "Detected conflicts where multiple mods write the same file(s):\n\n"
        )
        for rel, mods in conflicts.items():
            ranks = [(order.index(m) if m in order else -1, m) for m in mods]
            ranks.sort()
            winner = ranks[-1][1] if ranks else mods[-1]
            details = []
            for m in mods:
                mf = manifests[m]
                details.append(
                    f"{m} ({mf.get('type','misc')}) by {mf.get('author','?')}"
                )
            text.insert(
                tk.END,
                f"{rel}\n  Mods: {', '.join(details)}\n  Winner by load order (last wins): {winner}\n\n",
            )
        text.config(state="disabled")

        ttk.Label(win, text="Select mods to disable:").pack(
            anchor="w", padx=8, pady=(8, 0)
        )

        # Checkbox area
        mods_to_disable = {}
        box_frame = ttk.Frame(win)
        box_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        unique_mods = sorted(set([mm for ms in conflicts.values() for mm in ms]))
        for m in unique_mods:
            var = tk.BooleanVar()
            mods_to_disable[m] = var
            ttk.Checkbutton(box_frame, text=m, variable=var).pack(anchor="w")

        def apply_disables():
            changed = []
            enabled_now = get_enabled_mods()
            for mod_name, var in mods_to_disable.items():
                if var.get() and mod_name in enabled_now:
                    enabled_now.remove(mod_name)
                    changed.append(mod_name)
            if changed:
                set_enabled_mods(enabled_now)
                self._log(f"Disabled mods due to conflicts: {', '.join(changed)}")
                messagebox.showinfo("Conflicts", f"Disabled: {', '.join(changed)}")
                self.refresh_mod_list()
            win.destroy()

        bframe = ttk.Frame(win)
        bframe.pack(pady=(8, 8))
        ttk.Button(bframe, text="Disable Selected Mods", command=apply_disables).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(bframe, text="Close", command=win.destroy).pack(side=tk.LEFT, padx=6)

        self._log(
            f"Opened conflict manager with {len(conflicts)} overlapping file path(s)."
        )

    def on_rollback(self):
        rps = sorted(
            [p.name for p in RESTORE_POINTS_DIR.iterdir() if p.is_dir()], reverse=True
        )[:50]
        if not rps:
            messagebox.showinfo("Rollback", "No restore points found.")
            return

        win = tk.Toplevel(self)
        win.title("Choose Restore Point")
        win.geometry("420x420")
        lb = tk.Listbox(win, height=min(16, len(rps)))
        for rp in rps:
            lb.insert(tk.END, rp)
        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def do_rb():
            sel = lb.curselection()
            if not sel:
                return
            rp = rps[sel[0]]
            try:
                base = get_target()
                if not base or not base.exists():
                    messagebox.showerror("Rollback Error", "No valid FM26 target set.")
                    return
                rollback_to_restore_point(rp, base, self._log)
                messagebox.showinfo("Rollback", f"Rolled back to {rp}.")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Rollback Error", str(e))

        ttk.Button(win, text="Rollback to selected", command=do_rb).pack(pady=(0, 8))

    def on_open_target(self):
        t = get_target()
        if not t or not t.exists():
            messagebox.showinfo("Open Target", "No valid target set.")
            return
        safe_open_path(t)

    def on_open_mods(self):
        safe_open_path(MODS_DIR)

    def on_open_logs_folder(self):
        safe_open_path(LOGS_DIR)

    def on_show_manifest_help(self):
        txt = (
            "Each mod must include a manifest.json at its root:\n\n"
            "{\n"
            '  "name": "FM26 UI Pack",\n'
            '  "version": "1.0.0",\n'
            '  "type": "ui",\n'
            '  "author": "You",\n'
            '  "homepage": "https://example.com",\n'
            '  "description": "Replaces panel IDs bundle",\n'
            '  "files": [\n'
            '    { "source": "ui-panelids_assets_all Mac.bundle", "target_subpath": "ui-panelids_assets_all.bundle", "platform": "mac" },\n'
            '    { "source": "ui-panelids_assets_all Windows.bundle", "target_subpath": "ui-panelids_assets_all.bundle", "platform": "windows" }\n'
            "  ]\n"
            "}\n\n"
            "• target_subpath is relative to the Standalone… folder.\n"
            "• Last-write-wins according to the load order.\n"
            f"• Mods live in: {MODS_DIR}\n"
            f"• Logs live in: {LOGS_DIR}\n"
        )
        messagebox.showinfo("Manifest format", txt)

    def on_select_row(self, _event):
        sel = self.tree.selection()
        if not sel:
            self.details_text.delete("1.0", tk.END)
            return
        name = self.tree.item(sel[0])["values"][0]
        try:
            mf = read_manifest(MODS_DIR / name)
            desc = mf.get("description", "")
            hp = mf.get("homepage", "")
            typ = mf.get("type", "misc")
            auth = mf.get("author", "")
            lic = mf.get("license", "")
            deps = ", ".join(mf.get("dependencies", [])) or "—"
            conf = ", ".join(mf.get("conflicts", [])) or "—"
            comp = mf.get("compatibility", {})
            comp_str = ", ".join([f"{k}: {v}" for k, v in comp.items()]) or "—"
            files = mf.get("files", [])
            file_list = (
                "\n".join(
                    [
                        f"- {f.get('source','?')}  →  {f.get('target_subpath','?')}"
                        for f in files
                    ]
                )
                or "—"
            )
            text = (
                f"Name: {mf.get('name',name)}\nVersion: {mf.get('version','')}\n"
                f"Type: {typ} | Author: {auth} | License: {lic}\nHomepage: {hp}\n"
                f"Compatibility: {comp_str}\nDependencies: {deps}\nConflicts: {conf}\n\n"
                f"Description:\n{desc}\n\nFiles:\n{file_list}\n"
            )
            self.details_text.delete("1.0", tk.END)
            self.details_text.insert(tk.END, text)
        except Exception as e:
            self.details_text.delete("1.0", tk.END)
            self.details_text.insert(tk.END, f"(error reading manifest) {e}")

    # ---- Enhanced feature handlers ----
    def refresh_store_mods(self):
        """Load and display mods from the store."""
        if not ENHANCED_FEATURES or not self.mod_store_api:
            return

        try:
            for i in self.store_tree.get_children():
                self.store_tree.delete(i)

            mods = self.mod_store_api.get_all_mods()
            for mod in mods:
                self.store_tree.insert("", tk.END, values=(
                    mod.get("name", "?"),
                    mod.get("version", "?"),
                    mod.get("type", "?"),
                    mod.get("author", "?"),
                    mod.get("downloads", "—")
                ))
            self._log(f"Loaded {len(mods)} mods from store.")
        except Exception as e:
            self._log(f"Error loading store: {e}")
            messagebox.showerror("Store Error", f"Failed to load mod store:\n{e}")

    def on_store_search(self):
        """Search mods in the store."""
        if not ENHANCED_FEATURES or not self.mod_store_api:
            return

        query = self.store_search_var.get()
        try:
            for i in self.store_tree.get_children():
                self.store_tree.delete(i)

            mods = self.mod_store_api.search_mods(query=query)
            for mod in mods:
                self.store_tree.insert("", tk.END, values=(
                    mod.get("name", "?"),
                    mod.get("version", "?"),
                    mod.get("type", "?"),
                    mod.get("author", "?"),
                    mod.get("downloads", "—")
                ))
            self._log(f"Found {len(mods)} mods matching '{query}'.")
        except Exception as e:
            messagebox.showerror("Search Error", str(e))

    def on_store_refresh(self):
        """Force refresh store cache."""
        if not ENHANCED_FEATURES or not self.mod_store_api:
            return

        self._log("Refreshing store index...")
        threading.Thread(target=self._refresh_store_async, daemon=True).start()

    def _refresh_store_async(self):
        """Async store refresh."""
        try:
            self.mod_store_api.fetch_store_index(force_refresh=True)
            self.after(0, self.refresh_store_mods)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Refresh Error", str(e)))

    def on_store_install(self):
        """Install selected mod from store."""
        sel = self.store_tree.selection()
        if not sel:
            messagebox.showinfo("Install", "Select a mod first.")
            return

        mod_name = self.store_tree.item(sel[0])["values"][0]
        mod_data = self.mod_store_api.get_mod_by_name(mod_name)

        if not mod_data:
            messagebox.showerror("Install Error", f"Mod '{mod_name}' not found in store.")
            return

        download_url = mod_data.get("download_url")
        if not download_url:
            messagebox.showerror("Install Error", "No download URL available for this mod.")
            return

        self._log(f"Downloading {mod_name}...")
        threading.Thread(
            target=self._download_and_install,
            args=(mod_data,),
            daemon=True,
        ).start()

    def _download_and_install(self, mod_data):
        """Download and install mod in background."""
        try:
            mod_name = mod_data.get("name", "Unknown Mod")
            url = mod_data.get("download_url")
            manifest_url = mod_data.get("manifest_url")
            if not url:
                raise ValueError(f"No download URL available for '{mod_name}'.")

            temp_dir = Path(tempfile.mkdtemp(prefix="fm_store_"))
            downloaded = self.mod_store_api.download_mod(url, temp_dir)

            self.after(0, lambda: self._log(f"Downloaded {downloaded.name}, installing..."))

            # Import the downloaded mod
            src_folder: Optional[Path] = None
            if downloaded.suffix.lower() == ".zip":
                temp_extract = Path(tempfile.mkdtemp(prefix="fm_extract_"))
                with zipfile.ZipFile(downloaded, "r") as z:
                    z.extractall(temp_extract)

                # Find manifest
                candidates = [d for d in temp_extract.iterdir() if d.is_dir() and (d / "manifest.json").exists()]
                src_folder = candidates[0] if candidates else temp_extract
            else:
                if not manifest_url:
                    raise ValueError(
                        f"Store entry for '{mod_name}' requires a manifest_url when the release asset is not a ZIP."
                    )
                manifest_data = self.mod_store_api.fetch_manifest(manifest_url)
                package_dir = Path(tempfile.mkdtemp(prefix="fm_package_"))
                manifest_path = package_dir / "manifest.json"
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

                files = manifest_data.get("files", [])
                if not files:
                    raise ValueError(f"Manifest for '{mod_name}' does not define any files.")

                matched_entry = None
                if len(files) == 1:
                    matched_entry = files[0]
                else:
                    for entry in files:
                        source_rel = entry.get("source")
                        if source_rel and Path(source_rel).name.lower() == downloaded.name.lower():
                            matched_entry = entry
                            break

                if not matched_entry or not matched_entry.get("source"):
                    raise ValueError(
                        f"Unable to map downloaded asset '{downloaded.name}' to manifest files for '{mod_name}'."
                    )

                dest_path = package_dir / matched_entry["source"]
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(downloaded, dest_path)
                src_folder = package_dir

            newname = install_mod_from_folder(src_folder, None, log=self._log)
            order = get_load_order()
            if newname not in order:
                order.append(newname)
                set_load_order(order)

            self.after(0, lambda: self.refresh_mod_list())
            self.after(0, lambda: messagebox.showinfo("Install", f"Successfully installed '{newname}'!"))
            self.after(0, lambda: self._log(f"Successfully installed {newname} from store."))

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Install Error", str(e)))
            self.after(0, lambda: self._log(f"Install failed: {e}"))

    def on_store_details(self):
        """Show details for selected store mod."""
        sel = self.store_tree.selection()
        if not sel:
            return

        mod_name = self.store_tree.item(sel[0])["values"][0]
        mod_data = self.mod_store_api.get_mod_by_name(mod_name)

        if mod_data:
            self.store_details_text.delete("1.0", tk.END)
            text = (
                f"Name: {mod_data.get('name', '?')}\n"
                f"Version: {mod_data.get('version', '?')}\n"
                f"Type: {mod_data.get('type', '?')}\n"
                f"Author: {mod_data.get('author', '?')}\n"
                f"Downloads: {mod_data.get('downloads', '—')}\n\n"
                f"Description:\n{mod_data.get('description', 'No description available.')}\n\n"
                f"Homepage: {mod_data.get('homepage', '—')}\n"
            )
            self.store_details_text.insert(tk.END, text)

    def on_store_select_row(self, _event):
        """Handle store mod selection."""
        self.on_store_details()

    def refresh_bepinex_status(self):
        """Update BepInEx installation status."""
        if not ENHANCED_FEATURES or not self.bepinex_manager:
            return

        if self.bepinex_manager.is_installed():
            version = self.bepinex_manager.get_version() or "Unknown"
            self.bepinex_status_var.set(f"✓ Installed (Version: {version})")
            self.bepinex_console_var.set(self.bepinex_manager.is_console_enabled())
        else:
            self.bepinex_status_var.set("✗ Not Installed")

    def on_bepinex_install(self):
        """Install BepInEx."""
        if not ENHANCED_FEATURES or not self.bepinex_manager:
            return

        archive_path = Path(__file__).parent.parent / "BepInEx_Patched_Win_af0cba7.rar"
        if not archive_path.exists():
            messagebox.showerror("Install Error", f"BepInEx archive not found:\n{archive_path}")
            return

        def progress(msg):
            self._log(msg)

        try:
            self.bepinex_manager.install_from_archive(archive_path, progress_callback=progress)
            self.refresh_bepinex_status()
            messagebox.showinfo("BepInEx", "BepInEx installed successfully!")
        except Exception as e:
            messagebox.showerror("Install Error", str(e))

    def on_bepinex_toggle_console(self):
        """Toggle BepInEx console logging."""
        if not ENHANCED_FEATURES or not self.bepinex_manager:
            return

        enabled = self.bepinex_console_var.get()
        if self.bepinex_manager.set_console_enabled(enabled):
            self._log(f"BepInEx console logging {'enabled' if enabled else 'disabled'}.")
        else:
            messagebox.showerror("Config Error", "Failed to update BepInEx config.")
            self.bepinex_console_var.set(not enabled)

    def on_bepinex_open_config(self):
        """Open BepInEx config file in editor."""
        if not ENHANCED_FEATURES or not self.bepinex_manager:
            return

        if self.bepinex_manager.open_config_in_editor():
            self._log("Opened BepInEx config file.")
        else:
            messagebox.showerror("Error", "BepInEx config file not found.")

    def on_bepinex_view_log(self):
        """View latest BepInEx log."""
        if not ENHANCED_FEATURES or not self.bepinex_manager:
            return

        log_path = self.bepinex_manager.get_latest_log_path()
        if log_path:
            safe_open_path(log_path)
        else:
            messagebox.showinfo("Logs", "No BepInEx log files found.")

    def on_bepinex_open_folder(self):
        """Open BepInEx folder."""
        if not ENHANCED_FEATURES or not self.bepinex_manager:
            return

        if self.bepinex_manager.bepinex_dir.exists():
            safe_open_path(self.bepinex_manager.bepinex_dir)
        else:
            messagebox.showinfo("BepInEx", "BepInEx folder not found.")

    def on_report_bug(self):
        """Report a bug via Discord."""
        if not ENHANCED_FEATURES or not self.discord:
            return

        # Create dialog for bug report
        win = tk.Toplevel(self)
        win.title("Report Bug")
        win.geometry("500x400")

        ttk.Label(win, text="Describe the issue:").pack(padx=10, pady=(10, 5))
        desc_text = tk.Text(win, height=10)
        desc_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        ttk.Label(win, text="Email (optional):").pack(padx=10, pady=(10, 5))
        email_var = tk.StringVar()
        ttk.Entry(win, textvariable=email_var).pack(padx=10, pady=5, fill=tk.X)

        def send_report():
            description = desc_text.get("1.0", tk.END).strip()
            if not description:
                messagebox.showwarning("Report", "Please describe the issue.")
                return

            email = email_var.get().strip() or None

            # Get log files
            logs = []
            if RUN_LOG.exists():
                logs.append(RUN_LOG)
            if self.bepinex_manager:
                logs.extend(self.bepinex_manager.get_log_files())

            try:
                success = self.discord.report_error(description, logs, VERSION, email)
                if success:
                    messagebox.showinfo("Report", "Bug report sent successfully!")
                    win.destroy()
                else:
                    messagebox.showerror("Report", "Failed to send report. Check Discord webhook configuration.")
            except Exception as e:
                messagebox.showerror("Report Error", str(e))

        ttk.Button(win, text="Send Report", command=send_report).pack(pady=10)

    def on_submit_mod(self):
        """Submit a mod to the store via Discord."""
        if not ENHANCED_FEATURES or not self.discord:
            return

        # Create dialog for mod submission
        win = tk.Toplevel(self)
        win.title("Submit Mod to Store")
        win.geometry("500x450")

        ttk.Label(win, text="GitHub Repository URL:").pack(padx=10, pady=(10, 5))
        repo_var = tk.StringVar()
        ttk.Entry(win, textvariable=repo_var).pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Mod Name:").pack(padx=10, pady=(10, 5))
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var).pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Author:").pack(padx=10, pady=(10, 5))
        author_var = tk.StringVar()
        ttk.Entry(win, textvariable=author_var).pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Mod Type:").pack(padx=10, pady=(10, 5))
        type_var = tk.StringVar(value="ui")
        ttk.Combobox(win, textvariable=type_var, values=["ui", "graphics", "tactics", "database", "misc"], state="readonly").pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Description:").pack(padx=10, pady=(10, 5))
        desc_text = tk.Text(win, height=5)
        desc_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        ttk.Label(win, text="Contact (optional):").pack(padx=10, pady=(10, 5))
        contact_var = tk.StringVar()
        ttk.Entry(win, textvariable=contact_var).pack(padx=10, pady=5, fill=tk.X)

        def send_submission():
            repo = repo_var.get().strip()
            name = name_var.get().strip()
            author = author_var.get().strip()
            mod_type = type_var.get()
            description = desc_text.get("1.0", tk.END).strip()
            contact = contact_var.get().strip() or None

            if not all([repo, name, author, description]):
                messagebox.showwarning("Submit", "Please fill in all required fields.")
                return

            try:
                success = self.discord.submit_mod(repo, name, author, description, mod_type, contact)
                if success:
                    messagebox.showinfo("Submit", "Mod submission sent successfully!")
                    win.destroy()
                else:
                    messagebox.showerror("Submit", "Failed to send submission. Check Discord webhook configuration.")
            except Exception as e:
                messagebox.showerror("Submit Error", str(e))

        ttk.Button(win, text="Submit Mod", command=send_submission).pack(pady=10)

    def on_generate_template(self):
        """Generate a mod template."""
        # Create dialog for template generation
        win = tk.Toplevel(self)
        win.title("Generate Mod Template")
        win.geometry("500x500")

        ttk.Label(win, text="Mod Name:").pack(padx=10, pady=(10, 5))
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var).pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Version:").pack(padx=10, pady=(10, 5))
        version_var = tk.StringVar(value="1.0.0")
        ttk.Entry(win, textvariable=version_var).pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Author:").pack(padx=10, pady=(10, 5))
        author_var = tk.StringVar()
        ttk.Entry(win, textvariable=author_var).pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Mod Type:").pack(padx=10, pady=(10, 5))
        type_var = tk.StringVar(value="ui")
        ttk.Combobox(win, textvariable=type_var, values=["ui", "graphics", "tactics", "database", "misc"], state="readonly").pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="Description:").pack(padx=10, pady=(10, 5))
        desc_text = tk.Text(win, height=5)
        desc_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        ttk.Label(win, text="Homepage (optional):").pack(padx=10, pady=(10, 5))
        homepage_var = tk.StringVar()
        ttk.Entry(win, textvariable=homepage_var).pack(padx=10, pady=5, fill=tk.X)

        def generate():
            name = name_var.get().strip()
            version = version_var.get().strip()
            author = author_var.get().strip()
            mod_type = type_var.get()
            description = desc_text.get("1.0", tk.END).strip()
            homepage = homepage_var.get().strip()

            if not all([name, version, author, description]):
                messagebox.showwarning("Generate", "Please fill in all required fields.")
                return

            # Ask for save location
            save_path = filedialog.askdirectory(title="Select folder to save template")
            if not save_path:
                return

            try:
                mod_folder = Path(save_path) / name
                mod_folder.mkdir(exist_ok=True)

                # Create manifest.json
                manifest = {
                    "name": name,
                    "version": version,
                    "type": mod_type,
                    "author": author,
                    "description": description,
                    "homepage": homepage if homepage else "",
                    "files": [
                        {
                            "source": "your_mod_file_here.bundle",
                            "target_subpath": "target_file.bundle",
                            "platform": "windows"
                        }
                    ]
                }

                manifest_path = mod_folder / "manifest.json"
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)

                # Create README
                readme_path = mod_folder / "README.md"
                readme_content = f"""# {name}

{description}

## Installation
1. Use FM Reloaded Mod Manager to install this mod
2. Or manually copy files to your FM26 installation

## Version
{version}

## Author
{author}
"""
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(readme_content)

                messagebox.showinfo("Success", f"Template created at:\n{mod_folder}\n\nAdd your mod files and update manifest.json!")
                win.destroy()

            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Generate Template", command=generate).pack(pady=10)

    def on_settings(self):
        """Open settings/preferences dialog."""
        win = tk.Toplevel(self)
        win.title("Preferences")
        win.geometry("600x400")

        # Store URL
        ttk.Label(win, text="Mod Store URL:", font=("", 10, "bold")).pack(padx=10, pady=(10, 5), anchor="w")
        store_url_var = tk.StringVar(value=get_store_url())
        ttk.Entry(win, textvariable=store_url_var, width=70).pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(win, text="URL to mods.json file (usually on GitHub raw)", font=("", 8)).pack(padx=10, pady=(0, 10), anchor="w")

        # Discord webhooks
        ttk.Label(win, text="Discord Integration:", font=("", 10, "bold")).pack(padx=10, pady=(10, 5), anchor="w")

        webhooks = get_discord_webhooks()

        ttk.Label(win, text="Error Report Webhook URL:").pack(padx=10, pady=(5, 2), anchor="w")
        error_webhook_var = tk.StringVar(value=webhooks['error'])
        ttk.Entry(win, textvariable=error_webhook_var, width=70).pack(padx=10, pady=2, fill=tk.X)

        ttk.Label(win, text="Mod Submission Webhook URL:").pack(padx=10, pady=(10, 2), anchor="w")
        mod_webhook_var = tk.StringVar(value=webhooks['mod_submission'])
        ttk.Entry(win, textvariable=mod_webhook_var, width=70).pack(padx=10, pady=2, fill=tk.X)

        ttk.Label(win, text="Get webhook URLs from Discord server settings → Integrations → Webhooks", font=("", 8)).pack(padx=10, pady=(5, 10), anchor="w")

        # Auto-check for updates
        auto_check_var = tk.BooleanVar(value=load_config().get("auto_check_updates", True))
        ttk.Checkbutton(win, text="Automatically check for app updates on startup", variable=auto_check_var).pack(padx=10, pady=10, anchor="w")

        def save_settings():
            # Save store URL
            set_store_url(store_url_var.get().strip())

            # Save Discord webhooks
            set_discord_webhooks(error_webhook_var.get().strip(), mod_webhook_var.get().strip())

            # Save auto-check setting
            cfg = load_config()
            cfg["auto_check_updates"] = auto_check_var.get()
            save_config(cfg)

            # Update runtime instances
            if self.mod_store_api:
                self.mod_store_api.set_store_url(store_url_var.get().strip())

            if self.discord:
                self.discord.set_error_webhook(error_webhook_var.get().strip())
                self.discord.set_mod_webhook(mod_webhook_var.get().strip())

            messagebox.showinfo("Settings", "Settings saved successfully!")
            win.destroy()

        # Buttons
        btn_frame = ttk.Frame(win)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        ttk.Button(btn_frame, text="Save", command=save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=5)

    def _auto_check_updates(self):
        """Silently check for updates on startup."""
        def check_async():
            try:
                updater = AppUpdater(VERSION, "jo13310/FM_Reloaded")
                has_update, release_info = updater.check_for_updates()

                if has_update:
                    self.after(0, lambda: self._show_update_dialog(release_info))
                # If no update, do nothing (silent check)

            except Exception as e:
                # Silent failure on auto-check
                self._log(f"Auto-update check failed: {e}")

        threading.Thread(target=check_async, daemon=True).start()

    def on_check_updates(self):
        """Check for app updates."""
        if not ENHANCED_FEATURES:
            return

        self._log("Checking for updates...")

        def check_async():
            try:
                updater = AppUpdater(VERSION, "jo13310/FM_Reloaded")
                has_update, release_info = updater.check_for_updates()

                if has_update:
                    self.after(0, lambda: self._show_update_dialog(release_info))
                else:
                    self.after(0, lambda: messagebox.showinfo("Check for Updates", f"You are running the latest version ({VERSION})."))

            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Update Check Failed", f"Failed to check for updates:\n{e}"))

        threading.Thread(target=check_async, daemon=True).start()

    def _show_update_dialog(self, release_info):
        """Show update available dialog."""
        win = tk.Toplevel(self)
        win.title("Update Available")
        win.geometry("500x400")

        ttk.Label(win, text=f"New Version Available: {release_info['version']}", font=("", 12, "bold")).pack(padx=10, pady=10)
        ttk.Label(win, text=f"Current Version: {VERSION}").pack(padx=10, pady=(0, 10))

        # Release notes
        ttk.Label(win, text="Release Notes:", font=("", 10, "bold")).pack(padx=10, pady=(10, 5), anchor="w")
        notes_text = tk.Text(win, height=12, wrap="word")
        notes_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        notes_text.insert("1.0", release_info.get('body', 'No release notes available.'))
        notes_text.config(state="disabled")

        def open_download():
            import webbrowser
            webbrowser.open(release_info.get('download_url', release_info.get('html_url', '')))
            win.destroy()

        # Buttons
        btn_frame = ttk.Frame(win)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        ttk.Button(btn_frame, text="Download Update", command=open_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Later", command=win.destroy).pack(side=tk.LEFT, padx=5)

    def on_about(self):
        """Show about dialog."""
        about_text = f"""FM Reloaded Mod Manager
Version {VERSION}

A cross-platform mod manager for Football Manager 2026

Original FM_Reloaded_26 by Justin Levine & FM Match Lab Team
Enhanced and Forked by GerKo

Features:
• Mod installation and management
• Load order control with conflict detection
• Mod Store browser
• BepInEx integration
• Discord integration for bug reports

License: CC BY-SA 4.0 International

GitHub: https://github.com/jo13310/FM_Reloaded
"""
        messagebox.showinfo("About FM Reloaded", about_text)


# ---- main ----
if __name__ == "__main__":
    # macOS may print "Secure coding is not enabled..." warning for Tk — harmless.
    app = App()
    app.mainloop()
