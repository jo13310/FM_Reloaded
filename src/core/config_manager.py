#!/usr/bin/env python3
"""
Configuration management for FM Reloaded.
Handles all config.json operations with caching.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConfigManager:
    """Manages application configuration with caching."""

    def __init__(self, config_path: Path):
        """
        Initialize config manager.

        Args:
            config_path: Path to config.json file
        """
        self.config_path = config_path
        self._cache: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load configuration from disk."""
        if self.config_path.exists():
            try:
                self._cache = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}
        else:
            self._cache = {}
        return self._cache

    def save(self):
        """Save current configuration to disk."""
        self.config_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value and save."""
        self._cache[key] = value
        self.save()

    # Target path property
    @property
    def target_path(self) -> Optional[Path]:
        """Get FM26 target installation path."""
        p = self._cache.get("target_path")
        return Path(p) if p else None

    @target_path.setter
    def target_path(self, path: Path):
        """Set FM26 target installation path."""
        self._cache["target_path"] = str(path)
        self.save()

    # Enabled mods property
    @property
    def enabled_mods(self) -> List[str]:
        """Get list of enabled mod names."""
        return self._cache.get("enabled_mods", [])

    @enabled_mods.setter
    def enabled_mods(self, mods: List[str]):
        """Set list of enabled mod names."""
        self._cache["enabled_mods"] = mods
        self.save()

    # Load order property
    @property
    def load_order(self) -> List[str]:
        """Get mod load order."""
        return self._cache.get("load_order", [])

    @load_order.setter
    def load_order(self, order: List[str]):
        """Set mod load order."""
        self._cache["load_order"] = order
        self.save()

    # Last applied mods property
    @property
    def last_applied_mods(self) -> List[str]:
        """Return list of mods that were last applied to the game files."""
        return self._cache.get("last_applied_mods", [])

    @last_applied_mods.setter
    def last_applied_mods(self, mods: List[str]):
        """Persist list of mods that were last applied to the game files."""
        self._cache["last_applied_mods"] = list(mods)
        self.save()

    # Store URL property
    @property
    def store_url(self) -> str:
        """Get mod store URL."""
        return self._cache.get(
            "store_url",
            "https://raw.githubusercontent.com/jo13310/FM_Reloaded_Trusted_Store/main/mods.json"
        )

    @store_url.setter
    def store_url(self, url: str):
        """Set mod store URL."""
        self._cache["store_url"] = url
        self.save()

    # Discord webhooks property
    @property
    def discord_webhooks(self) -> Dict[str, str]:
        """Get Discord webhook URLs."""
        return {
            'error': self._cache.get(
                "discord_error_webhook",
                "https://discord.com/api/webhooks/1434612338970857474/D0pdw_G1lltO3ylLJv5DFu6aMXAgTrdqzH8iH-KUsyDmiKLQ5YYBqFRvdhI0S62tBNPp"
            ),
            'mod_submission': self._cache.get(
                "discord_mod_webhook",
                "https://discord.com/api/webhooks/1434612412467904652/iF2wgQfFJoQRzXYzQZ-UtKfVDEWSF-V-OLqp0MWl1BOGvda2ue4-SFaPVXxt77Eirxe"
            )
        }

    def set_discord_webhooks(self, error_url: str, mod_url: str):
        """Set Discord webhook URLs."""
        self._cache["discord_error_webhook"] = error_url
        self._cache["discord_mod_webhook"] = mod_url
        self.save()


def asset_path(filename: str) -> Path:
    """
    Resolve an asset path bundled with the application.

    Checks multiple locations:
    1. PyInstaller _MEIPASS/assets/
    2. PyInstaller _MEIPASS/
    3. Script directory/assets/
    4. Script directory/

    Args:
        filename: Name of asset file

    Returns:
        Path to asset file (may not exist)
    """
    candidates = []

    # PyInstaller bundle location
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
        candidates.append(base / "assets" / filename)
        candidates.append(base / filename)

    # Script directory
    script_base = Path(__file__).resolve().parent.parent  # Go up from core/
    candidates.append(script_base / "assets" / filename)
    candidates.append(script_base / filename)

    for cand in candidates:
        if cand.exists():
            return cand

    # Fall back to script assets path even if it does not yet exist
    return script_base / "assets" / filename
