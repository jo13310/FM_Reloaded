#!/usr/bin/env python3
"""
Path resolution and validation for FM Reloaded.
Handles platform-specific path detection and special directory routing.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional


def _platform_tag() -> str:
    """Get platform identifier for current OS."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "other"


def default_candidates() -> List[Path]:
    """
    Try to discover FM26 'Standalone...' asset folder by platform.

    Returns:
        List of candidate paths (may be empty if FM26 not found)
    """
    home = Path.home()
    out = []

    if sys.platform.startswith("win"):
        # Windows: Steam + Epic Games
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
        # macOS: Steam + Epic Games
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


def detect_fm_path() -> Optional[Path]:
    """
    Auto-detect FM26 installation path.

    Returns:
        First found candidate path, or None if not found
    """
    candidates = default_candidates()
    if candidates:
        return candidates[0]
    return None


def fm_user_dir() -> Path:
    """
    Return FM user folder (for tactics, skins, graphics, etc.).

    Windows: Documents/Sports Interactive/Football Manager 26
    macOS: ~/Library/Application Support/Sports Interactive/Football Manager 26
    """
    if sys.platform.startswith("win"):
        return Path.home() / "Documents" / "Sports Interactive" / "Football Manager 26"
    else:
        # macOS
        return (
            Path.home()
            / "Library/Application Support/Sports Interactive/Football Manager 26"
        )


def _game_root_from_target(base: Path) -> Path:
    """
    Walk up from target (e.g., StandaloneWindows64) to FM game root.

    Removes common subdirectory names like 'StandaloneWindows64', 'aa',
    'StreamingAssets', 'fm_Data', 'data' from the path.

    Args:
        base: Target path to traverse up from

    Returns:
        FM game root directory
    """
    base_path = Path(base).resolve()
    removable = {
        "standalonewindows64",
        "standaloneosx",
        "standalonelinux64",
        "aa",
        "streamingassets",
        "fm_data",
        "data",
    }
    current = base_path
    while current.name.lower() in removable and current.parent != current:
        current = current.parent
    return current


def validate_path_safety(target: Path, allowed_root: Path, description: str = "path") -> Path:
    """
    Validate that target path is within allowed root directory.
    Prevents path traversal attacks.

    Args:
        target: The path to validate
        allowed_root: The root directory that target must be within
        description: Description for error messages

    Returns:
        Resolved target path if valid

    Raises:
        ValueError: If path escapes allowed_root (security violation)
    """
    try:
        target_resolved = target.resolve()
        allowed_resolved = allowed_root.resolve()
        target_resolved.relative_to(allowed_resolved)
        return target_resolved
    except ValueError:
        raise ValueError(
            f"Security: {description} escapes allowed directory. "
            f"Target: {target}, Allowed root: {allowed_root}"
        )


def resolve_target(base: Path, sub: str, config_target: Optional[Path] = None) -> Path:
    """
    Resolve target path handling special prefixes with security validation.

    Routing rules:
    - BepInEx/ → FM root/BepInEx/
    - data/ → FM root/data/
    - graphics/ → Documents/FM26/graphics/
    - tactics/ → Documents/FM26/tactics/
    - editor data/ → Documents/FM26/editor data/
    - Otherwise → relative to base

    Security: Validates paths don't escape their designated directories.

    Args:
        base: Base directory (usually StandaloneWindows64)
        sub: Subdirectory from manifest (e.g., "BepInEx/plugins/mod.dll")
        config_target: Optional stored target path from config

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path contains malicious patterns
    """
    base = Path(base)
    sub_path = Path(sub)
    normalized = str(sub_path.as_posix())

    # Check for obviously malicious patterns
    if ".." in normalized or normalized.startswith("/") or normalized.startswith("\\"):
        raise ValueError(f"Invalid path in manifest: {sub}")

    # BepInEx paths go to FM game root (from stored target)
    if normalized.startswith("BepInEx/") or normalized.startswith("BepInEx\\"):
        if config_target and config_target.exists():
            root = _game_root_from_target(config_target)
        else:
            # Fallback: try to traverse from base
            root = _game_root_from_target(base)

        target = root / Path(*normalized.split("/"))
        # Validate path stays within FM root
        return validate_path_safety(target, root, "BepInEx path")

    # data/ paths go to FM root
    if normalized.startswith("data/") or normalized.startswith("data\\"):
        if config_target and config_target.exists():
            root = _game_root_from_target(config_target)
        else:
            root = _game_root_from_target(base)

        target = root / Path(*normalized.split("/"))
        return validate_path_safety(target, root, "data path")

    # Documents-relative paths
    user_dir = fm_user_dir()
    if normalized.startswith("graphics/") or normalized.startswith("graphics\\"):
        target = user_dir / Path(*normalized.split("/"))
        return validate_path_safety(target, user_dir, "graphics path")
    if normalized.startswith("tactics/") or normalized.startswith("tactics\\"):
        target = user_dir / Path(*normalized.split("/"))
        return validate_path_safety(target, user_dir, "tactics path")
    if normalized.startswith("editor data/") or normalized.startswith("editor data\\"):
        target = user_dir / Path(*normalized.split("/"))
        return validate_path_safety(target, user_dir, "editor data path")

    # Default: relative to base
    target = base / sub_path
    return validate_path_safety(target, base, "target path")


def get_install_dir_for_type(mod_type: str, mod_name: str, config_target: Optional[Path]) -> Path:
    """
    Return the appropriate install directory depending on mod type and mod name.
    Auto-creates /graphics and its subfolders (kits, faces, logos) if missing.

    Args:
        mod_type: Type from manifest ("ui", "graphics", "tactics", etc.)
        mod_name: Name of the mod (used for graphics subtype detection)
        config_target: Stored FM26 target path from config

    Returns:
        Installation directory path
    """
    base = fm_user_dir()
    graphics_base = base / "graphics"
    mod_type = (mod_type or "").lower()
    mod_name = (mod_name or "").lower()

    # UI/bundle mods go to the main FM install location (StandaloneWindows64)
    if mod_type in ("ui", "bundle"):
        return config_target

    # Tactics mods go to the user's tactics folder
    if mod_type == "tactics":
        path = base / "tactics"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Graphics and its subtypes
    if mod_type == "graphics":
        graphics_base.mkdir(parents=True, exist_ok=True)
        if any(x in mod_name for x in ("kit", "kits")):
            path = graphics_base / "kits"
        elif any(x in mod_name for x in ("face", "faces", "portraits")):
            path = graphics_base / "faces"
        elif any(x in mod_name for x in ("logo", "logos", "badges")):
            path = graphics_base / "logos"
        else:
            path = graphics_base
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Database/editor mods
    if mod_type == "database":
        path = base / "editor data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Camera mods (BepInEx plugins)
    # Note: Camera mods should use BepInEx/plugins/ in manifest target_subpath
    # This routing provides a sensible base directory fallback
    if mod_type == "camera":
        if config_target:
            # Return game root (parent of StandaloneWindows64)
            game_root = config_target.parent.parent
            return game_root
        # Fallback to Documents if no target configured
        base.mkdir(parents=True, exist_ok=True)
        return base

    # Default fallback (misc mods)
    base.mkdir(parents=True, exist_ok=True)
    return base
