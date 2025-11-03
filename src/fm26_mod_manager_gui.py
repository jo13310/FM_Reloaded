#!/usr/bin/env python3
# FM26 Mod Manager (FM_Reloaded_26)
# Cross-platform (macOS/Windows) GUI with:
# - Enable/disable mods, load order, filter by type
# - Import from .zip or folder
# - Conflict manager (detects overlapping target files; disable selected)
# - Restore points & rollback
# - Finder-safe file operations on macOS (no -R reveals)
# - Footer text credit line
# - Enhanced features: Mod Store, BepInEx, Updates, Discord integration
# - Improved conflict detection and file management
# - Delete functionality for complete mod removal

import os, sys, json, shutil, hashlib, webbrowser, subprocess, zipfile, tempfile
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, filedialog
import threading

# Import ttkbootstrap for modern UI
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:
    from tkinter import ttk
    TTKBOOTSTRAP_AVAILABLE = False
    print("Warning: ttkbootstrap not available, using standard ttk")

# Import core modules
from core.config_manager import ConfigManager, asset_path
from core.path_resolver import (
    _platform_tag, default_candidates, detect_fm_path, fm_user_dir,
    validate_path_safety, resolve_target, get_install_dir_for_type
)
from core.security_utils import (
    safe_extract_zip, safe_delete_path, safe_copy, _copy_any,
    backup_original, find_latest_backup_for_filename
)

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
config = ConfigManager(CONFIG_PATH)  # Global config manager instance
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
                # Intentionally allow symlink deletion for log pointer
                safe_delete_path(LAST_LINK, allow_symlink_delete=True)
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


def detect_fm_path_and_save():
    """Helper to detect FM path and save to config."""
    path = detect_fm_path()
    if path:
        config.target_path = path
        return path
    return None


# -------------
# Mod actions
# -------------
def enable_mod(mod_name: str, log):
    mod_dir = MODS_DIR / mod_name
    if not mod_dir.exists():
        raise FileNotFoundError(f"Mod not found: {mod_name} in {MODS_DIR}")
    mf = read_manifest(mod_dir)

    # Get type-aware base directory (FIXED: was using config.target_path which always returned StandaloneWindows64)
    mod_type = mf.get("type", "misc")
    base = get_install_dir_for_type(mod_type, mf.get("name", mod_name))

    if not base or not base.exists():
        raise RuntimeError("No valid FM26 target set. Use Detect or Set Target.")
    files = mf.get("files", [])
    if not files:
        raise ValueError("Manifest has no 'files' entries.")
    plat = _platform_tag()
    log(f"[enable] {mf.get('name', mod_name)} (type={mod_type})  →  {base}")
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
                b = backup_original(tgt, BACKUP_DIR)
                log(f"  [backup] {tgt_rel}  ←  {b.name if b else 'skipped'}")
                backed_up += 1
            # Use _copy_any() instead of shutil.copy2() to support directories
            _copy_any(src, tgt)
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

    # Get type-aware base directory (FIXED: was using config.target_path which always returned StandaloneWindows64)
    mod_type = mf.get("type", "misc")
    base = get_install_dir_for_type(mod_type, mf.get("name", mod_name))

    if not base or not base.exists():
        raise RuntimeError("No valid FM26 target set. Use Detect or Set Target.")
    files = mf.get("files", [])
    if not files:
        log("[disable] Manifest has no files to disable.")
        return
    log(f"[disable] {mf.get('name', mod_name)} (type={mod_type})  from  {base}")
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
                # Use safe deletion with symlink protection
                if safe_delete_path(tgt, allow_symlink_delete=False):
                    log(f"  [remove] {tgt_rel}")
                    removed += 1
                else:
                    log(f"  [error/remove] {tgt_rel} :: Failed to delete")
                    errors += 1
                    continue
                b = find_latest_backup_for_filename(tgt.name, BACKUP_DIR)
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
        # Use safe deletion with symlink protection
        safe_delete_path(dest, allow_symlink_delete=False)
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
    elif not names:
        # Empty list means no mods enabled - return empty index
        return {}, {}
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
    idx, _ = build_mod_index(config.enabled_mods)
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
    base = config.target_path
    if not base or not base.exists():
        raise RuntimeError("No valid FM26 target set. Use Detect or Set Target.")

    enabled = config.enabled_mods
    enabled_set = set(enabled)
    previously_applied = config.last_applied_mods

    removed = []
    for name in previously_applied:
        if name in enabled_set:
            continue
        try:
            disable_mod(name, log)
            removed.append(name)
        except FileNotFoundError:
            log(f"[disable/skip] {name} not found on disk; skipping removal.")
        except Exception as ex:
            log(f"[WARN] Failed disabling {name}: {ex}")

    order = config.load_order
    ordered = [m for m in order if m in enabled] + [
        m for m in enabled if m not in order
    ]
    if not ordered:
        if removed:
            log(f"Removed {len(removed)} mod(s) no longer enabled.")
        config.last_applied_mods = []
        log("No enabled mods to apply.")
        return
    rp = create_restore_point(base, log)
    for name in ordered:
        try:
            enable_mod(name, log)
        except Exception as ex:
            log(f"[WARN] Failed enabling {name}: {ex}")
    if removed:
        log(f"Removed {len(removed)} mod(s) no longer enabled.")
    log(
        f"Applied {len(ordered)} mod(s) in order (last-write-wins). Restore point: {rp}"
    )
    config.last_applied_mods = ordered


def delete_mod(mod_name: str, log):
    """Delete selected mod from computer."""
    name = self.selected_mod_name()
    if not name:
        messagebox.showinfo("Delete", "Select a mod first.")
        return

    if not messagebox.askyesno(
            "Delete Mod",
            f"Are you sure you want to permanently delete '{name}'?\n\nThis will remove the mod folder and all its files from your computer."
        ):
            return

    try:
        mod_dir = MODS_DIR / name
        if mod_dir.exists():
            # First disable the mod to remove files from game directories
            try:
                disable_mod(name, self._log)
            except Exception as e:
                self._log(f"Error disabling mod before deletion: {e}")

            # Remove from enabled mods list
            enabled = config.enabled_mods
            if name in enabled:
                enabled.remove(name)
                config.enabled_mods = enabled

            # Remove from load order
            order = config.load_order
            if name in order:
                order.remove(name)
                config.load_order = order

            # Delete mod folder
            safe_delete_path(mod_dir, allow_symlink_delete=False)
            self._log(f"Deleted mod '{name}' from {MODS_DIR}")
            self.refresh_mod_list()
            messagebox.showinfo("Delete", f"Mod '{name}' has been permanently deleted.")
        else:
            messagebox.showerror("Delete Error", f"Mod '{name}' not found in {MODS_DIR}")
    except Exception as e:
        messagebox.showerror("Delete Error", f"Failed to delete mod: {e}")
        self._log(f"Delete error for '{name}': {e}")


# --------------------
# Restore points
# --------------------
def create_restore_point(base: Path, log):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rp = RESTORE_POINTS_DIR / ts
    rp.mkdir(parents=True, exist_ok=True)
    idx, _ = build_mod_index(config.enabled_mods)
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
    base = config.target_path
    if not base or not base.exists():
        raise RuntimeError("No valid FM26 target set. Use Detect or Set Target.")

    enabled = config.enabled_mods
    enabled_set = set(enabled)
    previously_applied = config.last_applied_mods

    removed = []
    for name in previously_applied:
        if name in enabled_set:
            continue
        try:
            disable_mod(name, log)
            removed.append(name)
        except FileNotFoundError:
            log(f"[disable/skip] {name} not found on disk; skipping removal.")
        except Exception as ex:
            log(f"[WARN] Failed disabling {name}: {ex}")

    order = config.load_order
    ordered = [m for m in order if m in enabled] + [
        m for m in enabled if m not in order
    ]
    if not ordered:
        if removed:
            log(f"Removed {len(removed)} mod(s) no longer enabled.")
        config.last_applied_mods = []
        log("No enabled mods to apply.")
        return
    rp = create_restore_point(base, log)
    for name in ordered:
        try:
            enable_mod(name, log)
        except Exception as ex:
            log(f"[WARN] Failed enabling {name}: {ex}")
    if removed:
        log(f"Removed {len(removed)} mod(s) no longer enabled.")
    log(
        f"Applied {len(ordered)} mod(s) in order (last-write-wins). Restore point: {rp}"
    )
    config.last_applied_mods = ordered


# ----------
#   GUI
# ----------
class App(ttk.Window if TTKBOOTSTRAP_AVAILABLE else tk.Tk):
    def __init__(self):
        # Initialize with theme if ttkbootstrap is available
        if TTKBOOTSTRAP_AVAILABLE:
            # Use a modern theme (cosmo for light, darkly for dark)
            theme = load_config().get("theme", "cosmo")
            super().__init__(title=f"FM Reloaded Mod Manager v{VERSION}", themename=theme)
        else:
            super().__init__()
            self.title(f"FM Reloaded Mod Manager v{VERSION}")

        self.geometry("1200x900")
        self.minsize(1100, 800)
        self._icon_image_ref: Optional[tk.PhotoImage] = None
        self._set_window_icon()

        # Track selection metadata for detail actions
        self._selected_mod_homepage: str = ""
        self._selected_mod_readme: Optional[Path] = None

        # Initialize enhanced features
        if ENHANCED_FEATURES:
            self.mod_store_api = ModStoreAPI(config.store_url)
            webhooks = config.discord_webhooks
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

    def _set_window_icon(self):
        """Set application icon for window and task bar."""
        try:
            png_path = asset_path("fm_reloaded.png")
            if png_path.exists():
                icon_image = tk.PhotoImage(file=str(png_path))
                self.iconphoto(True, icon_image)
                self._icon_image_ref = icon_image  # Prevent garbage collection
        except Exception as exc:
            print(f"Warning: failed to set PNG icon: {exc}")

        if sys.platform.startswith("win"):
            try:
                ico_path = asset_path("icon.ico")
                if ico_path.exists():
                    self.iconbitmap(default=str(ico_path))
            except Exception as exc:
                print(f"Warning: failed to set ICO icon: {exc}")

    # ---- logging ----
    def _log(self, msg: str):
        try:
            # Detect message type and apply color
            tag = None
            if "[ERROR]" in msg.upper() or "FAILED" in msg.upper() or "ERROR:" in msg.upper():
                tag = "ERROR"
            elif "[WARN]" in msg.upper() or "WARNING" in msg.upper():
                tag = "WARN"
            elif "SUCCESS" in msg.upper() or "APPLIED" in msg.upper() or "ENABLED" in msg.upper():
                tag = "SUCCESS"
            elif "[INFO]" in msg.upper() or "READY" in msg.upper():
                tag = "INFO"

            if tag:
                self.log_text.insert(tk.END, msg + "\n", tag)
            else:
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
        if TTKBOOTSTRAP_AVAILABLE:
            ttk.Button(top, text="Detect", command=self.on_detect, bootstyle="primary-outline").pack(side=tk.LEFT, padx=2)
            ttk.Button(top, text="Set…", command=self.on_set_target, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=2)
        else:
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
        log_frame = ttk.Labelframe(self, text="Log")
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure log text tags for color coding
        self.log_text.tag_config("ERROR", foreground="#dc3545")
        self.log_text.tag_config("WARN", foreground="#ffc107")
        self.log_text.tag_config("SUCCESS", foreground="#28a745")
        self.log_text.tag_config("INFO", foreground="#17a2b8")

        # Footer with credits and Discord buttons
        self.create_footer()

    def create_my_mods_tab(self):
        """Create My Mods tab (original mod manager functionality)."""
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

        cols = ("name", "version", "type", "author", "order", "status", "update")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
        self.tree.column("name", width=280, anchor="w")
        self.tree.column("version", width=80, anchor="w")
        self.tree.column("type", width=100, anchor="w")
        self.tree.column("author", width=140, anchor="w")
        self.tree.column("order", width=50, anchor="center")
        self.tree.column("status", width=90, anchor="center")
        self.tree.column("update", width=70, anchor="center")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure treeview tags for color coding
        if TTKBOOTSTRAP_AVAILABLE:
            self.tree.tag_configure("enabled", background="#d4edda")  # Light green
            self.tree.tag_configure("disabled", foreground="#6c757d")  # Gray
            self.tree.tag_configure("update", background="#fff3cd")  # Light yellow
        else:
            self.tree.tag_configure("enabled", background="#e8f5e9")
            self.tree.tag_configure("disabled", foreground="#999999")
            self.tree.tag_configure("update", background="#fff9c4")

        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)

        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=8)

        # Add styled buttons with bootstyle if available
        if TTKBOOTSTRAP_AVAILABLE:
            ttk.Button(right, text="Refresh", command=self.refresh_mod_list, bootstyle="info-outline").pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Import Mod…", command=self.on_import_mod, bootstyle="primary").pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Enable (mark)", command=self.on_enable_selected, bootstyle="success-outline").pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Disable (unmark)", command=self.on_disable_selected, bootstyle="secondary-outline").pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Delete", command=self.on_delete_selected, bootstyle="danger").pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Up (Order)", command=self.on_move_up, bootstyle="secondary-outline").pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Down (Order)", command=self.on_move_down, bootstyle="secondary-outline").pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Apply Order", command=self.on_apply_order, bootstyle="success").pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Conflicts…", command=self.on_conflicts, bootstyle="warning").pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Rollback…", command=self.on_rollback, bootstyle="danger-outline").pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Open Mods Folder", command=self.on_open_mods, bootstyle="info-outline").pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Help (Manifest)", command=self.on_show_manifest_help, bootstyle="secondary-outline").pack(fill=tk.X, pady=(12, 2))
        else:
            ttk.Button(right, text="Refresh", command=self.refresh_mod_list).pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Import Mod…", command=self.on_import_mod).pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Enable (mark)", command=self.on_enable_selected).pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Disable (unmark)", command=self.on_disable_selected).pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Delete", command=self.on_delete_selected).pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Up (Order)", command=self.on_move_up).pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Down (Order)", command=self.on_move_down).pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Apply Order", command=self.on_apply_order).pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Conflicts…", command=self.on_conflicts).pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Rollback…", command=self.on_rollback).pack(fill=tk.X, pady=(12, 2))
            ttk.Button(right, text="Open Mods Folder", command=self.on_open_mods).pack(fill=tk.X, pady=2)
            ttk.Button(right, text="Help (Manifest)", command=self.on_show_manifest_help).pack(fill=tk.X, pady=(12, 2))

        # Details pane
        det = ttk.Labelframe(tab, text="Details")
        det.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))
        self.details_text = tk.Text(det, height=6)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        links = ttk.Frame(det)
        links.pack(fill=tk.X, pady=(4, 0))
        self.open_homepage_btn = ttk.Button(
            links,
            text="Open Homepage",
            command=self.on_open_mod_homepage,
            state=tk.DISABLED,
        )
        self.open_homepage_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.open_readme_btn = ttk.Button(
            links,
            text="Open Readme",
            command=self.on_open_mod_readme,
            state=tk.DISABLED,
        )
        self.open_readme_btn.pack(side=tk.LEFT, padx=(0, 4))
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
        """Create Mod Store browser tab."""
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
        det = ttk.Labelframe(tab, text="Mod Details")
        det.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))
        self.store_details_text = tk.Text(det, height=6)
        self.store_details_text.pack(fill=tk.BOTH, expand=True)
        self.store_tree.bind("<<TreeviewSelect>>", self.on_store_select_row)

        # Load store mods
        self.refresh_store_mods()

    def create_bepinex_tab(self):
        """Create BepInEx management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="BepInEx")

        # Status section
        status_frame = ttk.Labelframe(tab, text="Installation Status")
        status_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        self.bepinex_status_var = tk.StringVar(value="Checking...")
        ttk.Label(status_frame, textvariable=self.bepinex_status_var, font=("", 10, "bold")).pack(padx=10, pady=10)

        # Installation section
        install_frame = ttk.Labelframe(tab, text="Installation")
        install_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        ttk.Button(install_frame, text="Install BepInEx", command=self.on_bepinex_install, bootstyle="primary" if TTKBOOTSTRAP_AVAILABLE else None).pack(padx=10, pady=5, fill=tk.X)
        ttk.Label(install_frame, text="Installs BepInEx from BepInEx_Patched_Win_af0cba7.rar", font=("", 8)).pack(padx=10, pady=(0, 10))

        # Configuration section
        config_frame = ttk.Labelframe(tab, text="Configuration")
        config_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        self.bepinex_console_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            config_frame,
            text="Enable Console Logging (shows console window)",
            variable=self.bepinex_console_var,
            command=self.on_bepinex_toggle_console
        ).pack(padx=10, pady=5, anchor="w")

        ttk.Button(config_frame, text="Open BepInEx Config File", command=self.on_bepinex_open_config, bootstyle="info-outline" if TTKBOOTSTRAP_AVAILABLE else None).pack(padx=10, pady=5, fill=tk.X)

        # Logs section
        logs_frame = ttk.Labelframe(tab, text="Logs & Debugging")
        logs_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        ttk.Button(logs_frame, text="View Latest Log", command=self.on_bepinex_view_log, bootstyle="info-outline" if TTKBOOTSTRAP_AVAILABLE else None).pack(padx=10, pady=5, fill=tk.X)
        ttk.Button(logs_frame, text="Open BepInEx Folder", command=self.on_bepinex_open_folder, bootstyle="info-outline" if TTKBOOTSTRAP_AVAILABLE else None).pack(padx=10, pady=5, fill=tk.X)

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
        t = config.target_path
        self.target_var.set(str(t) if t else "")

    def refresh_mod_list(self):
        # clear
        for i in self.tree.get_children():
            self.tree.delete(i)
        wanted = self.type_filter.get()
        order = config.load_order
        enabled = set(config.enabled_mods)

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
                        except (FileNotFoundError, json.JSONDecodeError, KeyError):
                            # Skip mods with missing or invalid manifests
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
                    ord_disp = str(ord_idx + 1) if ord_idx >= 0 else "-"
                    status_text = "Enabled" if p.name in enabled else "Disabled"
                    update_available = "Update" if mf.get("name") in updates else ""
                    rows.append(
                        (
                            (
                                p.name,
                                mf.get("version", ""),
                                mtype,
                                mf.get("author", ""),
                                ord_disp,
                                status_text,
                                update_available,
                            ),
                            mf,
                        )
                    )
                except Exception:
                    rows.append(((p.name, "?", "?", "?", "-", "Unknown", ""), None))
        # Insert rows with color tags
        for row, _ in rows:
            # Determine tags based on status
            tags = []
            if row[5] == "Enabled":
                tags.append("enabled")
            else:
                tags.append("disabled")
            if row[6]:
                tags.append("update")

            self.tree.insert("", tk.END, values=row, tags=tags)

        self._log(f"Loaded {len(rows)} mod(s) (filter: {wanted}).")
        if updates:
            self._log(f"[updates] {len(updates)} mod(s) have updates available in the store.")
        enabled = config.enabled_mods
        conflicts, _ = find_conflicts(enabled)
        if conflicts:
            self._log(
                f"[conflict] Detected {len(conflicts)} file conflict(s) among enabled mods; opening conflict manager."
            )
            self.after(500, self.on_conflicts)

    def selected_mod_name(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"][0]

    def on_detect(self):
        t = detect_fm_path_and_save()
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
        config.target_path = p
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
                # Use safe extraction with security validations
                safe_extract_zip(choice, temp_dir)
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
            order = config.load_order
            if newname not in order:
                order.append(newname)
                config.load_order = order
            self.refresh_mod_list()
            messagebox.showinfo("Import", f"Imported '{newname}'.")

        except Exception as e:
            messagebox.showerror("Import Error", str(e))
        finally:
            if temp_dir:
                # Safe cleanup of temporary directory
                try:
                    safe_delete_path(temp_dir, allow_symlink_delete=True)
                except Exception:
                    pass  # Cleanup failure is non-critical

    def on_enable_selected(self):
        name = self.selected_mod_name()
        if not name:
            messagebox.showinfo("Mods", "Select a mod first.")
            return
        enabled = config.enabled_mods
        if name not in enabled:
            enabled.append(name)
            config.enabled_mods = enabled
            self._log(f"Enabled (marked) '{name}'. Use Apply Order to write files.")
            self.refresh_mod_list()
        else:
            messagebox.showinfo("Mods", f"'{name}' already enabled (marked).")

    def on_disable_selected(self):
        name = self.selected_mod_name()
        if not name:
            messagebox.showinfo("Mods", "Select a mod first.")
            return
        enabled = [m for m in config.enabled_mods if m != name]
        config.enabled_mods = enabled
        self._log(
            f"Disabled (unmarked) '{name}'. Apply Order to rewrite files without it."
        )
        self.refresh_mod_list()

    def on_move_up(self):
        name = self.selected_mod_name()
        if not name:
            return
        order = config.load_order
        if name not in order:
            order.append(name)
        i = order.index(name)
        if i > 0:
            order[i - 1], order[i] = order[i], order[i - 1]
            config.load_order = order
            self._log(f"Moved up: {name}")
            self.refresh_mod_list()

    def on_move_down(self):
        name = self.selected_mod_name()
        if not name:
            return
        order = config.load_order
        if name not in order:
            order.append(name)
            i = order.index(name)
        if i < len(order) - 1:
            order[i + 1], order[i] = order[i], order[i + 1]
            config.load_order = order
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
        enabled = config.enabled_mods
        conflicts, manifests = find_conflicts(enabled)
        if not conflicts:
            messagebox.showinfo("Conflicts", "No file overlaps among enabled mods.")
            return

        order = config.load_order
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
            tk.END, "Detected conflicts where multiple mods write to same file(s):\n\n"
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
            enabled_now = config.enabled_mods
            for mod_name, var in mods_to_disable.items():
                if var.get() and mod_name in enabled_now:
                    enabled_now.remove(mod_name)
                    changed.append(mod_name)
            if changed:
                config.enabled_mods = enabled_now
                self._log(f"Disabled mods due to conflicts: {', '.join(changed)}")
                messagebox.showinfo("Conflicts", f"Disabled: {', '.join(changed)}")
                self.refresh_mod_list()
            win.destroy()

        bframe = ttk.Frame(win)
        bframe.pack(pady=(8, 8))
        ttk.Button(bframe, text="Disable Selected Mods", command=apply_disables).pack(side=tk.LEFT, padx=6)
        ttk.Button(bframe, text="Close", command=win.destroy).pack(side=tk.LEFT, padx=6)

        self._log(f"Opened conflict manager with {len(conflicts)} overlapping file path(s).")

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
                base = config.target_path
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
        t = config.target_path
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
            "Every mod must ship a manifest.json alongside its content.\n\n"
            "Example (FM data overrides):\n"
            "{\n"
            '  "name": "FM26 UI Pack",\n'
            '  "version": "1.0.0",\n'
            '  "type": "ui",\n'
            '  "files": [\n'
            '    { "source": "ui-panelids_mac.bundle", "target_subpath": "ui-panelids_assets_all.bundle", "platform": "mac" },\n'
            '    { "source": "ui-panelids_windows.bundle", "target_subpath": "ui-panelids_assets_all.bundle", "platform": "windows" }\n'
            "  ]\n"
            "}\n\n"
            "BepInEx plugin example:\n"
            "{\n"
            '  "name": "Camera POV",\n'
            '  "type": "misc",\n'
            '  "files": [\n'
            '    { "source": "plugins/YourMod.dll", "target_subpath": "BepInEx/plugins/YourMod.dll" }\n'
            "  ]\n"
            "}\n\n"
            "• When the store downloads a .zip, it is extracted before applying these rules.\n"
            "• For single files (e.g. DLLs), the manifest can be hosted separately and the manager stages the file into the mapped source path prior to install.\n"
            "• target_subpath is relative to the detected FM folder (or Documents tree for tactics/graphics).\n"
            "• Directories are created automatically; you can target files such as BepInEx/plugins/YourMod.dll or Documents/Sports Interactive/FM26/tactics/Name.fmf.\n"
            "• Load order is last-write-wins when multiple mods touch the same target file.\n"
            f"• Mods live in: {MODS_DIR}\n"
            f"• Logs live in: {LOGS_DIR}\n"
        )
        messagebox.showinfo("Manifest format", txt)

    def on_select_row(self, _event):
        sel = self.tree.selection()
        if not sel:
            self.details_text.delete("1.0", tk.END)
            self._selected_mod_homepage = ""
            self._selected_mod_readme = None
            self.open_homepage_btn.config(state=tk.DISABLED)
            self.open_readme_btn.config(state=tk.DISABLED)
            return
        name = self.tree.item(sel[0])["values"][0]
        try:
            mod_dir = MODS_DIR / name
            mf = read_manifest(mod_dir)
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
                        f"- {f.get('source','?')}  ->  {f.get('target_subpath','?')}"
                        for f in files
                    ]
                )
                or "-"
            )
            readme_path = None
            for candidate in mod_dir.iterdir():
                if candidate.is_file() and candidate.name.lower().startswith("readme"):
                    readme_path = candidate
                    break
            readme_preview = "Not found."
            if readme_path:
                try:
                    preview = readme_path.read_text(encoding="utf-8", errors="ignore").strip()
                    if len(preview) > 600:
                        preview = preview[:600].rstrip() + "..."
                    readme_preview = preview or "(Readme file is empty.)"
                except Exception as readme_err:
                    readme_preview = f"(Could not read {readme_path.name}: {readme_err})"
            text = (
                f"Name: {mf.get('name',name)}\nVersion: {mf.get('version','')}\n"
                f"Type: {typ} | Author: {auth} | License: {lic}\nHomepage: {hp or 'N/A'}\n"
                f"Compatibility: {comp_str}\nDependencies: {deps}\nConflicts: {conf}\n\n"
                f"Description:\n{desc}\n\nFiles:\n{file_list}\n\n"
                f"Readme Preview ({readme_path.name if readme_path else 'not available'}):\n{readme_preview}\n"
            )
            self.details_text.delete("1.0", tk.END)
            self.details_text.insert(tk.END, text)
            self._selected_mod_homepage = hp.strip()
            self._selected_mod_readme = readme_path
            self.open_homepage_btn.config(
                state=tk.NORMAL if self._selected_mod_homepage else tk.DISABLED
            )
            self.open_readme_btn.config(
                state=tk.NORMAL if readme_path and readme_path.exists() else tk.DISABLED
            )
        except Exception as e:
            self.details_text.delete("1.0", tk.END)
            self.details_text.insert(tk.END, f"(error reading manifest) {e}")
            self._selected_mod_homepage = ""
            self._selected_mod_readme = None
            self.open_homepage_btn.config(state=tk.DISABLED)
            self.open_readme_btn.config(state=tk.DISABLED)

    def on_open_mod_homepage(self):
        url = (self._selected_mod_homepage or "").strip()
        if not url:
            messagebox.showinfo("Homepage", "No homepage URL provided for this mod.")
            return
        try:
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showerror("Homepage", f"Failed to open homepage:\n{exc}")

    def on_open_mod_readme(self):
        readme_path = self._selected_mod_readme
        if not readme_path or not readme_path.exists():
            messagebox.showinfo("Readme", "No readme file found for this mod.")
            return
        try:
            safe_open_path(readme_path)
        except Exception as exc:
            messagebox.showerror("Readme", f"Failed to open readme:\n{exc}")

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
            self._log(f"Found {len(mods)} mods matching '{query}'")
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
                raise ValueError(f"No download URL available for '{mod_name}'")

            temp_dir = Path(tempfile.mkdtemp(prefix="fm_store_"))
            downloaded = self.mod_store_api.download_mod(url, temp_dir)

            self.after(0, lambda: self._log(f"Downloaded {downloaded.name}, installing..."))

            # Import the downloaded mod
            src_folder: Optional[Path] = None
            if downloaded.suffix.lower() == ".zip":
                temp_extract = Path(tempfile.mkdtemp(prefix="fm_extract_"))
                safe_extract_zip(downloaded, temp_extract)

                # Find manifest
                candidates = [d for d in temp_extract.iterdir() if d.is_dir() and (d / "manifest.json").exists()]
                src_folder = candidates[0] if candidates else temp_extract
            else:
                if not manifest_url:
                    raise ValueError(
                        f"Store entry for '{mod_name}' requires a manifest_url when release asset is not a ZIP."
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
            order = config.load_order
            if newname not in order:
                order.append(newname)
                config.load_order = order

            self.after(0, lambda: self.refresh_mod_list())
            self.after(0, lambda: messagebox.showinfo("Install", f"Successfully installed '{newname}'!"))
            self.after(0, lambda: self._log(f"Successfully installed {newname} from store."))

            # Track download count (async, non-blocking, no tokens needed!)
            def track_download():
                try:
                    # No token needed - tracking API handles it securely
                    self.mod_store_api.increment_download_count(mod_name)
                    # Success is silent - tracking is non-critical
                except Exception:
                    # Fail silently - download tracking is non-critical
                    pass

            threading.Thread(target=track_download, daemon=True).start()

        except Exception as e:
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
            download = mod_data.get("download", {}) if isinstance(mod_data.get("download"), dict) else {}
            asset = download.get("asset")
            channel = (
                "latest"
                if download.get("latest")
                else download.get("tag")
                or download.get("tag_prefix", "v")
            )
            asset_line = f"Asset: {asset} (channel: {channel})\n" if asset else ""
            manifest_line = f"Manifest: {mod_data.get('manifest_url')}\n" if mod_data.get("manifest_url") else ""
            install_line = (
                f"\nInstall Notes:\n{mod_data.get('install_notes')}\n"
                if mod_data.get("install_notes")
                else ""
            )
            text = (
                f"Name: {mod_data.get('name', '?')}\n"
                f"Version: {mod_data.get('version', '?')}\n"
                f"Type: {mod_data.get('type', '?')}\n"
                f"Author: {mod_data.get('author', '?')}\n"
                f"Downloads: {mod_data.get('downloads', '-')}\n"
                f"{asset_line}"
                f"{manifest_line}\n"
                f"Description:\n{mod_data.get('description', 'No description available.')}\n\n"
                f"Homepage: {mod_data.get('homepage', '-')}\n"
                f"{install_line}"
            )
            self.store_details_text.insert(tk.END, text)

    def on_store_select_row(self, _event):
            """Handle store mod selection."""
            self.on_store_details()

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

    # ---- Enhanced feature handlers ----
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
        ttk.Label(win, text="Release Notes:", font=("", 10, "bold")).pack(padx=10, pady=(5, 0))
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
        btn_frame.pack(side=tk.BOTTOM, pady=(10, 0))
        ttk.Button(btn_frame, text="Download Update", command=open_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Later", command=win.destroy).pack(side=tk.LEFT, padx=5)

    # ---- main ----
    if __name__ == "__main__":
        # macOS may print "Secure coding is not enabled..." warning for Tk — harmless.
        app = App()
        app.mainloop()


# ---- main ----
if __name__ == "__main__":
    # macOS may print "Secure coding is not enabled..." warning for Tk — harmless.
    app = App()
    app.mainloop()
