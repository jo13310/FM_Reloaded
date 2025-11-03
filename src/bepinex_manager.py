"""
BepInEx Manager Module for FM Reloaded Mod Manager
Handles BepInEx installation, configuration, and log management.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import zipfile
import rarfile  # Note: Requires rarfile package and WinRAR/UnRAR
import configparser
from datetime import datetime

# Import security utilities
try:
    from core.security_utils import (
        is_protected_system_directory,
        safe_delete_path,
        safe_delete_with_boundary_check
    )
except ImportError:
    # Fallback if module not available
    def is_protected_system_directory(path: Path) -> bool:
        """Fallback: basic system directory check."""
        path_resolved = path.resolve()
        # Protect exact matches
        protected_exact = [
            Path("C:\\Windows"), Path("C:\\Program Files"), Path("C:\\Program Files (x86)"),
            Path("/System"), Path("/usr"), Path("/bin"),
        ]
        for sys_dir in protected_exact:
            if sys_dir.exists() and path_resolved == sys_dir:
                return True
        # Allow deep subdirectories in Program Files (game installations)
        pf_roots = [Path("C:\\Program Files"), Path("C:\\Program Files (x86)")]
        for pf_root in pf_roots:
            if pf_root.exists():
                try:
                    relative = path_resolved.relative_to(pf_root)
                    if len(relative.parts) == 1:  # Direct child only
                        return True
                except ValueError:
                    pass
        return False

    def safe_delete_path(path: Path, allow_symlink_delete: bool = False) -> bool:
        """Fallback: basic safe delete."""
        if not path.exists():
            return False
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True

    def safe_delete_with_boundary_check(
        path: Path, allowed_root: Path, allow_symlink_delete: bool = False, require_whitelist: bool = True
    ) -> bool:
        """Fallback: basic boundary-checked delete."""
        # Simple validation
        path.resolve().relative_to(allowed_root.resolve())
        return safe_delete_path(path, allow_symlink_delete)


class BepInExManager:
    """Manages BepInEx installation and configuration for Football Manager 26."""

    def __init__(self, fm_install_dir: Path):
        """
        Initialize BepInEx manager with security validation.

        Args:
            fm_install_dir: Football Manager 26 installation directory

        Raises:
            ValueError: If fm_install_dir is invalid or in a protected system directory
        """
        fm_install_dir = Path(fm_install_dir).resolve()

        # SECURITY: Validate FM install directory exists
        if not fm_install_dir.exists():
            raise ValueError(
                f"FM install directory does not exist: {fm_install_dir}\n"
                f"Please verify the Football Manager 26 installation path."
            )

        if not fm_install_dir.is_dir():
            raise ValueError(f"FM install path is not a directory: {fm_install_dir}")

        # SECURITY: Prevent operations in system directories
        if is_protected_system_directory(fm_install_dir):
            raise ValueError(
                f"Security: FM install directory cannot be a protected system directory: {fm_install_dir}\n"
                f"This may indicate configuration file tampering or incorrect auto-detection."
            )

        self.fm_install_dir = fm_install_dir
        self.bepinex_dir = self.fm_install_dir / "BepInEx"
        self.config_file = self.bepinex_dir / "config" / "BepInEx.cfg"
        self.latest_log = self.bepinex_dir / "LogOutput.log"

    def is_installed(self) -> bool:
        """
        Check if BepInEx is already installed.

        Returns:
            True if BepInEx is installed
        """
        # Check for essential BepInEx files
        essential_files = [
            self.bepinex_dir / "core",
            self.fm_install_dir / "winhttp.dll",  # BepInEx loader
            self.fm_install_dir / "doorstop_config.ini"  # Doorstop config
        ]

        return all(f.exists() for f in essential_files)

    def get_version(self) -> Optional[str]:
        """
        Get installed BepInEx version.

        Returns:
            Version string or None if not installed
        """
        if not self.is_installed():
            return None

        # First try to read from LogOutput.log (most reliable source)
        log_path = self.get_latest_log_path()
        if log_path and log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline().strip()
                    if first_line and "BepInEx" in first_line:
                        # Extract version from line like "BepInEx 6.0.0.1234 - Football Manager 26"
                        parts = first_line.split()
                        for i, part in enumerate(parts):
                            if part == "BepInEx" and i + 1 < len(parts):
                                return parts[i + 1]
            except Exception:
                pass

        # Fallback: Try to read version from changelog or core files
        changelog = self.bepinex_dir / "changelog.txt"
        if changelog.exists():
            try:
                with open(changelog, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line:
                        return first_line
            except Exception:
                pass

        return "Unknown"

    def install_from_archive(self, archive_path: Path, progress_callback=None) -> bool:
        """
        Install BepInEx from a RAR or ZIP archive.

        Args:
            archive_path: Path to BepInEx_Patched_Win_*.rar or .zip
            progress_callback: Optional callback(message: str)

        Returns:
            True if installation successful

        Raises:
            FileNotFoundError: Archive not found
            Exception: Installation failed
        """
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        def log(msg: str):
            if progress_callback:
                progress_callback(msg)
            print(msg)

        try:
            log("Checking FM installation directory...")
            if not self.fm_install_dir.exists():
                raise ValueError(f"FM install directory not found: {self.fm_install_dir}")

            # Backup existing BepInEx if present
            if self.is_installed():
                log("Backing up existing BepInEx...")
                backup_dir = self.fm_install_dir / f"BepInEx_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.move(str(self.bepinex_dir), str(backup_dir))
                log(f"Backup created: {backup_dir.name}")

            # Extract archive
            log(f"Extracting {archive_path.name}...")
            temp_extract_dir = self.fm_install_dir / "_bepinex_temp"
            temp_extract_dir.mkdir(exist_ok=True)

            try:
                if archive_path.suffix.lower() == '.rar':
                    self._extract_rar(archive_path, temp_extract_dir, log)
                elif archive_path.suffix.lower() == '.zip':
                    self._extract_zip(archive_path, temp_extract_dir, log)
                else:
                    raise ValueError(f"Unsupported archive format: {archive_path.suffix}")

                # Find BepInEx root in extracted files
                bepinex_root = self._find_bepinex_root(temp_extract_dir)
                if not bepinex_root:
                    raise ValueError("BepInEx files not found in archive")

                log("Installing BepInEx files...")
                # Move files to FM directory
                for item in bepinex_root.iterdir():
                    dest = self.fm_install_dir / item.name
                    if dest.exists():
                        if dest.is_dir():
                            # SECURITY: Use safe delete with boundary check
                            safe_delete_with_boundary_check(
                                dest,
                                self.fm_install_dir,
                                allow_symlink_delete=False,
                                require_whitelist=False  # FM install dir not in whitelist
                            )
                        else:
                            dest.unlink()
                    shutil.move(str(item), str(dest))

                log("Cleaning up temporary files...")
                # SECURITY: Use safe delete for temp directory
                safe_delete_path(temp_extract_dir, allow_symlink_delete=False)

                # Set default config (console disabled)
                log("Configuring BepInEx...")
                self.set_console_enabled(False)

                log("BepInEx installation complete!")
                return True

            finally:
                # Clean up temp directory
                if temp_extract_dir.exists():
                    # SECURITY: Use safe delete for temp directory cleanup
                    try:
                        safe_delete_path(temp_extract_dir, allow_symlink_delete=False)
                    except Exception:
                        pass  # Ignore errors during cleanup

        except Exception as e:
            log(f"Installation failed: {e}")
            raise

    def _extract_rar(self, archive_path: Path, dest_dir: Path, log_func) -> None:
        """Extract RAR archive."""
        try:
            with rarfile.RarFile(archive_path) as rf:
                rf.extractall(dest_dir)
        except rarfile.Error as e:
            # Fallback to WinRAR command line
            log_func("Trying WinRAR command line...")
            winrar_paths = [
                Path(r"C:\Program Files\WinRAR\WinRAR.exe"),
                Path(r"C:\Program Files (x86)\WinRAR\WinRAR.exe")
            ]

            winrar = next((p for p in winrar_paths if p.exists()), None)
            if not winrar:
                raise Exception("WinRAR not found. Please install WinRAR or extract manually.")

            subprocess.run([
                str(winrar), "x", "-y", str(archive_path), str(dest_dir)
            ], check=True, capture_output=True)

    def _extract_zip(self, archive_path: Path, dest_dir: Path, log_func) -> None:
        """Extract ZIP archive."""
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extractall(dest_dir)

    def _find_bepinex_root(self, search_dir: Path) -> Optional[Path]:
        """
        Find BepInEx root directory in extracted files.

        Looks for directory containing 'BepInEx' folder and 'winhttp.dll'.
        """
        # Check if search_dir itself is the root
        if (search_dir / "BepInEx").exists() and (search_dir / "winhttp.dll").exists():
            return search_dir

        # Search subdirectories
        for subdir in search_dir.rglob("*"):
            if subdir.is_dir():
                if (subdir / "BepInEx").exists() and (subdir / "winhttp.dll").exists():
                    return subdir

        return None

    def uninstall(self, keep_plugins: bool = False) -> bool:
        """
        Uninstall BepInEx.

        Args:
            keep_plugins: If True, backup plugins folder

        Returns:
            True if successful
        """
        if not self.is_installed():
            return True

        try:
            # Backup plugins if requested
            if keep_plugins and (self.bepinex_dir / "plugins").exists():
                backup_dir = self.fm_install_dir / "BepInEx_plugins_backup"
                backup_dir.mkdir(exist_ok=True)
                shutil.copytree(
                    self.bepinex_dir / "plugins",
                    backup_dir / "plugins",
                    dirs_exist_ok=True
                )

            # Remove BepInEx files
            if self.bepinex_dir.exists():
                # SECURITY: Use safe delete with boundary check for uninstall
                safe_delete_with_boundary_check(
                    self.bepinex_dir,
                    self.fm_install_dir,
                    allow_symlink_delete=False,
                    require_whitelist=False  # FM install dir not in whitelist
                )

            # Remove loader files
            loader_files = [
                self.fm_install_dir / "winhttp.dll",
                self.fm_install_dir / "doorstop_config.ini",
                self.fm_install_dir / ".doorstop_version"
            ]

            for f in loader_files:
                if f.exists():
                    f.unlink()

            return True

        except Exception as e:
            print(f"Uninstall error: {e}")
            return False

    def is_console_enabled(self) -> bool:
        """
        Check if BepInEx console logging is enabled.

        Returns:
            True if console is enabled, False otherwise
        """
        if not self.config_file.exists():
            return False

        try:
            config = configparser.ConfigParser()
            config.read(self.config_file)

            enabled = config.get('Logging.Console', 'Enabled', fallback='false')
            return enabled.lower() in ['true', '1', 'yes']

        except Exception as e:
            print(f"Error reading config: {e}")
            return False

    def set_console_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable BepInEx console logging.

        Args:
            enabled: True to enable, False to disable

        Returns:
            True if successful
        """
        if not self.config_file.exists():
            # Create config directory if needed
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            # Create default config
            self._create_default_config()

        try:
            config = configparser.ConfigParser()
            config.read(self.config_file)

            # Ensure section exists
            if not config.has_section('Logging.Console'):
                config.add_section('Logging.Console')

            # Set value
            config.set('Logging.Console', 'Enabled', str(enabled).lower())

            # Write back
            with open(self.config_file, 'w', encoding='utf-8') as f:
                config.write(f)

            return True

        except Exception as e:
            print(f"Error updating config: {e}")
            return False

    def _create_default_config(self) -> None:
        """Create default BepInEx.cfg with console disabled."""
        default_config = """[Logging.Console]

## Enables showing a console for log output.
# Setting type: Boolean
# Default value: true
Enabled = false

[Logging.Disk]

## Enables writing log messages to disk.
# Setting type: Boolean
# Default value: true
Enabled = true
"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write(default_config)

    def open_config_in_editor(self) -> bool:
        """
        Open BepInEx.cfg in default text editor.

        Returns:
            True if successful
        """
        if not self.config_file.exists():
            return False

        try:
            if sys.platform == 'win32':
                os.startfile(self.config_file)
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(self.config_file)])
            else:
                subprocess.run(['xdg-open', str(self.config_file)])
            return True
        except Exception as e:
            print(f"Error opening config: {e}")
            return False

    def get_latest_log_path(self) -> Optional[Path]:
        """
        Get path to the latest BepInEx log file.

        Returns:
            Path to latest log or None if not found
        """
        # Check for LogOutput.log (standard location)
        if self.latest_log.exists():
            return self.latest_log

        # Check for timestamped logs in BepInEx folder
        if self.bepinex_dir.exists():
            log_files = sorted(
                self.bepinex_dir.glob("LogOutput.log*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            if log_files:
                return log_files[0]

        return None

    def get_error_log_path(self) -> Optional[Path]:
        """
        Get path to BepInEx error log.

        Returns:
            Path to error log or None if not found
        """
        error_log = self.bepinex_dir / "LogError.log"
        if error_log.exists():
            return error_log

        return None

    def get_log_files(self) -> List[Path]:
        """
        Get list of all BepInEx log files for error reporting.

        Returns:
            List of log file paths
        """
        logs = []

        # Latest log
        latest = self.get_latest_log_path()
        if latest:
            logs.append(latest)

        # Error log
        error = self.get_error_log_path()
        if error:
            logs.append(error)

        return logs

    def get_installed_plugins(self) -> List[Dict[str, str]]:
        """
        Get list of installed BepInEx plugins.

        Returns:
            List of plugin dictionaries with 'name' and 'path'
        """
        plugins = []
        plugins_dir = self.bepinex_dir / "plugins"

        if not plugins_dir.exists():
            return plugins

        for plugin_file in plugins_dir.rglob("*.dll"):
            plugins.append({
                'name': plugin_file.stem,
                'path': str(plugin_file.relative_to(plugins_dir))
            })

        return plugins


def find_fm_install_dir() -> Optional[Path]:
    """
    Auto-detect Football Manager 26 installation directory.

    Returns:
        Path to FM26 directory or None if not found
    """
    if sys.platform == 'win32':
        # Windows Steam default
        steam_paths = [
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26"),
            Path(r"D:\Steam\steamapps\common\Football Manager 26"),
            Path(r"E:\Steam\steamapps\common\Football Manager 26")
        ]

        for path in steam_paths:
            if path.exists():
                return path

    elif sys.platform == 'darwin':
        # macOS Steam default
        mac_path = Path.home() / "Library/Application Support/Steam/steamapps/common/Football Manager 2026"
        if mac_path.exists():
            return mac_path

    return None
