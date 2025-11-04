#!/usr/bin/env python3
"""
Enhanced platform detection for FM Reloaded.
Handles detection of FM26 installations across different platforms and sources.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json


def _platform_tag() -> str:
    """Get platform identifier for current OS."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "other"


def get_cache_dir() -> Path:
    """
    Get platform-appropriate cache directory.
    
    Returns:
        Platform-specific cache directory path
    """
    if sys.platform.startswith("win"):
        # Windows: %LOCALAPPDATA%/fm_reloaded/cache
        base = os.getenv("LOCALAPPDATA")
        if base:
            return Path(base) / "fm_reloaded" / "cache"
        # Fallback
        return Path.home() / "AppData" / "Local" / "fm_reloaded" / "cache"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Caches/fm_reloaded
        return Path.home() / "Library" / "Caches" / "fm_reloaded"
    else:
        # Linux: ~/.cache/fm_reloaded
        return Path.home() / ".cache" / "fm_reloaded"


def enhanced_default_candidates() -> List[Dict[str, str]]:
    """
    Enhanced FM26 installation detection with source identification.
    
    Returns:
        List of candidate dictionaries with path, source, and platform info
    """
    home = Path.home()
    candidates = []

    if sys.platform.startswith("win"):
        # Windows installations
        steam_base = Path(os.getenv("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Steam/steamapps/common/Football Manager 26"
        epic_base = Path(os.getenv("PROGRAMFILES", "C:/Program Files")) / "Epic Games/Football Manager 26"
        
        # Steam candidates
        for sub in [
            "fm_Data/StreamingAssets/aa/StandaloneWindows64",
            "data/StreamingAssets/aa/StandaloneWindows64",
        ]:
            path = steam_base / sub
            if path.exists():
                candidates.append({
                    "path": path,
                    "source": "Steam",
                    "platform": "Windows",
                    "base_path": steam_base
                })
        
        # Epic candidates
        for sub in [
            "fm_Data/StreamingAssets/aa/StandaloneWindows64",
            "data/StreamingAssets/aa/StandaloneWindows64",
        ]:
            path = epic_base / sub
            if path.exists():
                candidates.append({
                    "path": path,
                    "source": "Epic Games",
                    "platform": "Windows",
                    "base_path": epic_base
                })
                
    elif sys.platform == "darwin":
        # macOS installations
        steam_library = home / "Library/Application Support/Steam/steamapps/common/Football Manager 26"
        epic_library = home / "Library/Application Support/Epic/Football Manager 26"
        
        # Steam candidates
        for sub in [
            "fm.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX",
            "fm_Data/StreamingAssets/aa/StandaloneOSXUniversal",
        ]:
            path = steam_library / sub
            if path.exists():
                candidates.append({
                    "path": path,
                    "source": "Steam",
                    "platform": "macOS",
                    "base_path": steam_library
                })
        
        # Epic candidates
        for sub in [
            "fm_Data/StreamingAssets/aa/StandaloneOSXUniversal",
        ]:
            path = epic_library / sub
            if path.exists():
                candidates.append({
                    "path": path,
                    "source": "Epic Games",
                    "platform": "macOS",
                    "base_path": epic_library
                })
    
    # Custom installations - scan common locations
    custom_paths = _find_custom_installations()
    for custom_path in custom_paths:
        candidates.append({
            "path": custom_path,
            "source": "Custom",
            "platform": _platform_tag().capitalize(),
            "base_path": custom_path.parent
        })
    
    return candidates


def _find_custom_installations() -> List[Path]:
    """
    Find custom FM26 installations by searching for typical file patterns.
    
    Returns:
        List of custom installation paths
    """
    search_locations = []
    found_paths = []
    
    # Common game directories
    if sys.platform.startswith("win"):
        search_locations = [
            Path("C:/Games"),
            Path("D:/Games"),
            Path.home() / "Games",
        ]
    elif sys.platform == "darwin":
        search_locations = [
            Path.home() / "Applications",
            Path.home() / "Games",
        ]
    else:
        search_locations = [
            Path.home() / "Games",
            Path("/opt"),
            Path("/usr/local/games"),
        ]
    
    # Search for FM26 executables or bundles
    for search_path in search_locations:
        if not search_path.exists():
            continue
            
        try:
            # Look for FM26 executables or app bundles
            for pattern in ["**/fm.exe", "**/fm.app", "**/Football Manager 26*", "**/fm26*"]:
                for found in search_path.glob(pattern):
                    if found.is_file() or (found.is_dir() and found.name.endswith(".app")):
                        # Navigate to the correct data directory
                        data_path = _extract_data_path(found)
                        if data_path and data_path.exists():
                            found_paths.append(data_path)
        except (PermissionError, OSError):
            # Skip directories we can't access
            continue
    
    return list(set(found_paths))  # Remove duplicates


def _extract_data_path(executable_path: Path) -> Optional[Path]:
    """
    Extract the data path from an FM26 executable or app bundle.
    
    Args:
        executable_path: Path to fm.exe or fm.app
        
    Returns:
        Path to the Standalone data directory
    """
    if executable_path.name == "fm.exe":
        # Windows - look in parent directories for data
        current = executable_path.parent
        for _ in range(5):  # Search up to 5 levels up
            data_path = current / "fm_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"
            if data_path.exists():
                return data_path
            current = current.parent
    
    elif executable_path.name == "fm.app":
        # macOS - look inside app bundle
        data_path = executable_path / "Contents" / "Resources" / "Data" / "StreamingAssets" / "aa" / "StandaloneOSX"
        if data_path.exists():
            return data_path
        # Try alternative path
        alt_path = executable_path.parent / "fm_Data" / "StreamingAssets" / "aa" / "StandaloneOSXUniversal"
        if alt_path.exists():
            return alt_path
    
    return None


def detect_fm_installations() -> List[Dict[str, str]]:
    """
    Detect all available FM26 installations.
    
    Returns:
        List of installation dictionaries with detailed information
    """
    candidates = enhanced_default_candidates()
    
    # Add metadata and validate each candidate
    valid_installations = []
    for candidate in candidates:
        path = candidate["path"]
        if not path.exists():
            continue
            
        # Validate installation
        if _validate_fm_installation(path):
            candidate["valid"] = True
            candidate["size_gb"] = _calculate_directory_size(path) / (1024**3)
            candidate["last_modified"] = path.stat().st_mtime
            valid_installations.append(candidate)
        else:
            candidate["valid"] = False
            valid_installations.append(candidate)
    
    # Sort by source priority (Steam > Epic > Custom) then by name
    source_priority = {"Steam": 1, "Epic Games": 2, "Custom": 3}
    valid_installations.sort(key=lambda x: (source_priority.get(x["source"], 4), x["path"].name))
    
    return valid_installations


def _validate_fm_installation(path: Path) -> bool:
    """
    Validate that a path contains a proper FM26 installation.
    
    Args:
        path: Path to validate
        
    Returns:
        True if valid FM26 installation
    """
    if not path.exists():
        return False
    
    # Look for key FM26 files/folders
    required_patterns = [
        "**/*.bundle",  # Bundle files
        "**/Data/**",  # Data directory
        "**/StreamingAssets/**",  # Streaming assets
    ]
    
    matches = 0
    for pattern in required_patterns:
        try:
            if any(path.glob(pattern)):
                matches += 1
        except (PermissionError, OSError):
            continue
    
    return matches >= 2  # Require at least 2 matches


def _calculate_directory_size(path: Path) -> int:
    """
    Calculate directory size in bytes.
    
    Args:
        path: Directory to measure
        
    Returns:
        Size in bytes
    """
    try:
        total_size = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    except (PermissionError, OSError):
        return 0


def get_best_installation(installations: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """
    Select the best FM26 installation from available options.
    
    Args:
        installations: List of installation dictionaries
        
    Returns:
        Best installation dictionary or None
    """
    valid_installations = [inst for inst in installations if inst.get("valid", False)]
    if not valid_installations:
        return None
    
    # Prioritize by source, then by size (larger is likely more complete)
    source_priority = {"Steam": 1, "Epic Games": 2, "Custom": 3}
    
    def sort_key(inst):
        return (
            source_priority.get(inst["source"], 4),
            inst.get("size_gb", 0),
            -inst.get("last_modified", 0)  # More recent first
        )
    
    return min(valid_installations, key=sort_key)


def save_installation_preference(installation: Dict[str, str], config_path: Path):
    """
    Save user's installation preference.
    
    Args:
        installation: Selected installation dictionary
        config_path: Path to config file
    """
    try:
        config = {}
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
        
        config["preferred_installation"] = {
            "path": str(installation["path"]),
            "source": installation["source"],
            "platform": installation["platform"],
            "base_path": str(installation["base_path"])
        }
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Failed to save installation preference: {e}")


def load_installation_preference(config_path: Path) -> Optional[Dict[str, str]]:
    """
    Load user's installation preference.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Installation preference dictionary or None
    """
    try:
        if not config_path.exists():
            return None
        
        config = json.loads(config_path.read_text(encoding="utf-8"))
        pref = config.get("preferred_installation")
        if pref and Path(pref["path"]).exists():
            return pref
    except Exception as e:
        print(f"Warning: Failed to load installation preference: {e}")
    
    return None
