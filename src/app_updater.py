"""
App Updater Module for FM Reloaded Mod Manager
Checks for new releases on GitHub and notifies users.
"""

import json
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict
import re


class AppUpdater:
    """Checks for FM Reloaded updates on GitHub."""

    def __init__(self, current_version: str, github_repo: str = "jo13310/FM_Reloaded"):
        """
        Initialize the app updater.

        Args:
            current_version: Current app version (e.g., "0.5.0")
            github_repo: GitHub repository in format "owner/repo"
        """
        self.current_version = current_version
        self.github_repo = github_repo
        self.api_url = f"https://api.github.com/repos/{github_repo}/releases/latest"

    def check_for_updates(self) -> Tuple[bool, Optional[Dict]]:
        """
        Check if a newer version is available.

        Returns:
            Tuple of (update_available: bool, release_info: dict or None)
        """
        try:
            # Fetch latest release info from GitHub API
            request = urllib.request.Request(
                self.api_url,
                headers={'User-Agent': 'FM-Reloaded-Mod-Manager'}
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Extract version from tag_name
            tag_name = data.get('tag_name', '')
            latest_version = self._extract_version(tag_name)

            if not latest_version:
                return False, None

            # Compare versions
            if self._is_newer_version(latest_version, self.current_version):
                release_info = {
                    'version': latest_version,
                    'tag_name': tag_name,
                    'name': data.get('name', f'Version {latest_version}'),
                    'body': data.get('body', 'No release notes available.'),
                    'html_url': data.get('html_url', ''),
                    'download_url': self._find_download_url(data),
                    'published_at': data.get('published_at', '')
                }
                return True, release_info

            return False, None

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"Repository not found: {self.github_repo}")
            else:
                print(f"HTTP error checking for updates: {e.code}")
            return False, None
        except urllib.error.URLError as e:
            print(f"Network error checking for updates: {e}")
            return False, None
        except Exception as e:
            print(f"Error checking for updates: {e}")
            return False, None

    def _extract_version(self, tag_name: str) -> Optional[str]:
        """
        Extract version number from tag name.

        Args:
            tag_name: Git tag (e.g., "v0.5.0", "0.5.0", "v0.5.0-beta")

        Returns:
            Version string (e.g., "0.5.0") or None
        """
        # Remove 'v' prefix and any suffixes (-beta, -alpha, etc.)
        match = re.search(r'v?(\d+\.\d+\.\d+)', tag_name)
        if match:
            return match.group(1)
        return None

    def _is_newer_version(self, version1: str, version2: str) -> bool:
        """
        Compare two semantic version strings.

        Args:
            version1: Version to check (e.g., "1.0.0")
            version2: Current version (e.g., "0.5.0")

        Returns:
            True if version1 > version2
        """
        def parse_version(v: str) -> Tuple[int, ...]:
            """Parse version string into tuple of integers."""
            try:
                return tuple(int(x) for x in v.split('.'))
            except ValueError:
                return (0, 0, 0)

        v1_parts = parse_version(version1)
        v2_parts = parse_version(version2)

        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += (0,) * (max_len - len(v1_parts))
        v2_parts += (0,) * (max_len - len(v2_parts))

        return v1_parts > v2_parts

    def _find_download_url(self, release_data: Dict) -> Optional[str]:
        """
        Find the appropriate download URL from release assets.

        Args:
            release_data: GitHub release API response

        Returns:
            Download URL or release page URL
        """
        assets = release_data.get('assets', [])

        # Look for Windows executable
        for asset in assets:
            name = asset.get('name', '').lower()
            if name.endswith('.exe') or 'windows' in name:
                return asset.get('browser_download_url')

        # Look for any executable or archive
        for asset in assets:
            name = asset.get('name', '').lower()
            if any(ext in name for ext in ['.exe', '.zip', '.msi']):
                return asset.get('browser_download_url')

        # Fallback to release page
        return release_data.get('html_url')

    def get_current_version(self) -> str:
        """Get the current app version."""
        return self.current_version

    def get_changelog_url(self) -> str:
        """Get the URL to the changelog/releases page."""
        return f"https://github.com/{self.github_repo}/releases"


def check_for_app_updates(current_version: str, github_repo: str = "jo13310/FM_Reloaded") -> Tuple[bool, Optional[Dict]]:
    """
    Convenience function to check for updates.

    Args:
        current_version: Current app version
        github_repo: GitHub repository

    Returns:
        Tuple of (update_available: bool, release_info: dict or None)
    """
    updater = AppUpdater(current_version, github_repo)
    return updater.check_for_updates()
