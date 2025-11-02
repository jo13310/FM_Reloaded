"""
Mod Store API Module for FM Reloaded Mod Manager
Handles fetching, caching, and version comparison for the trusted mod store.
"""

import copy
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import tempfile
import shutil

# Default store configuration
DEFAULT_STORE_URL = "https://raw.githubusercontent.com/jo13310/FM_Reloaded_Trusted_Store/main/mods.json"
CACHE_DURATION_MINUTES = 1
DEFAULT_TAG_PREFIX = "v"


class ModStoreAPI:
    """Interface to the FM Reloaded trusted mod store on GitHub."""

    def __init__(self, store_url: str = DEFAULT_STORE_URL, cache_dir: Optional[Path] = None):
        """
        Initialize the mod store API.

        Args:
            store_url: URL to the mods.json index file
            cache_dir: Directory to cache store data (defaults to temp)
        """
        self.store_url = store_url
        self.cache_dir = cache_dir or Path(tempfile.gettempdir()) / "fm_reloaded_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "store_cache.json"
        self._cache: Optional[Dict] = None
        self._cache_timestamp: Optional[float] = None

    def set_store_url(self, url: str) -> None:
        """Update the store URL and invalidate cache."""
        self.store_url = url
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        """Clear the in-memory and file cache."""
        self._cache = None
        self._cache_timestamp = None
        if self.cache_file.exists():
            self.cache_file.unlink()

    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid based on TTL."""
        if self._cache_timestamp is None:
            return False

        age_minutes = (time.time() - self._cache_timestamp) / 60
        return age_minutes < CACHE_DURATION_MINUTES

    def _load_from_cache(self) -> Optional[Dict]:
        """Load store data from file cache if valid."""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check cache timestamp
            cache_time = cache_data.get('timestamp', 0)
            age_minutes = (time.time() - cache_time) / 60

            if age_minutes < CACHE_DURATION_MINUTES:
                self._cache = cache_data['data']
                self._cache_timestamp = cache_time
                return self._cache

        except (json.JSONDecodeError, KeyError, IOError) as e:
            print(f"Cache read error: {e}")

        return None

    def _save_to_cache(self, data: Dict) -> None:
        """Save store data to file cache."""
        try:
            cache_data = {
                'timestamp': time.time(),
                'data': data
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except IOError as e:
            print(f"Cache write error: {e}")

    def _build_request(self, force_refresh: bool) -> urllib.request.Request:
        """
        Build a request object, optionally appending a cache-busting query parameter
        and disabling client-side caching when a forced refresh is requested.
        """
        url = self.store_url
        if force_refresh:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}_ts={int(time.time())}"
        return urllib.request.Request(
            url,
            headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": "FMReloaded-ModManager/1.0",
            },
        )

    def fetch_store_index(self, force_refresh: bool = False) -> Dict:
        """
        Fetch the mod store index from GitHub.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            Dictionary with 'mods' list and metadata

        Raises:
            urllib.error.URLError: Network error
            json.JSONDecodeError: Invalid JSON response
        """
        # Return cached data if valid
        if not force_refresh and self._is_cache_valid() and self._cache:
            return self._cache

        # Try loading from file cache
        if not force_refresh:
            cached = self._load_from_cache()
            if cached:
                return cached

        # Fetch fresh data from GitHub
        try:
            request = self._build_request(force_refresh)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Validate structure
            if 'mods' not in data or not isinstance(data['mods'], list):
                raise ValueError("Invalid store format: missing 'mods' array")

            # Cache the result
            self._cache = data
            self._cache_timestamp = time.time()
            self._save_to_cache(data)

            return data

        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to fetch store index: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in store index: {e}")

    def get_all_mods(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get list of all mods in the store.

        Args:
            force_refresh: Bypass cache

        Returns:
            List of mod dictionaries
        """
        try:
            store_data = self.fetch_store_index(force_refresh)
            mods = store_data.get('mods', [])
            return [self._normalize_mod(m) for m in mods]
        except (ConnectionError, ValueError) as e:
            print(f"Error fetching mods: {e}")
            return []

    def search_mods(self, query: str = "", mod_type: str = "", author: str = "") -> List[Dict]:
        """
        Search for mods by name, type, or author.

        Args:
            query: Search term for name/description
            mod_type: Filter by mod type
            author: Filter by author name

        Returns:
            Filtered list of mods
        """
        all_mods = self.get_all_mods()
        results = []

        query_lower = query.lower()
        mod_type_lower = mod_type.lower()
        author_lower = author.lower()

        for mod in all_mods:
            # Type filter
            if mod_type_lower and mod.get('type', '').lower() != mod_type_lower:
                continue

            # Author filter
            if author_lower and author_lower not in mod.get('author', '').lower():
                continue

            # Query filter (search in name and description)
            if query_lower:
                name_match = query_lower in mod.get('name', '').lower()
                desc_match = query_lower in mod.get('description', '').lower()
                if not (name_match or desc_match):
                    continue

            results.append(mod)

        return results

    def get_mod_by_name(self, name: str) -> Optional[Dict]:
        """
        Find a specific mod by exact name match.

        Args:
            name: Mod name

        Returns:
            Mod dictionary or None if not found
        """
        for mod in self.get_all_mods():
            if mod.get('name', '').lower() == name.lower():
                return mod
        return None

    def download_mod(self, download_url: str, destination: Path, progress_callback=None) -> Path:
        """
        Download a mod file from the given URL.

        Args:
            download_url: Direct download URL (GitHub raw or release asset)
            destination: Directory to save the downloaded file
            progress_callback: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            Path to the downloaded file

        Raises:
            urllib.error.URLError: Download failed
        """
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        # Extract filename from URL
        filename = download_url.split('/')[-1]
        if '?' in filename:
            filename = filename.split('?')[0]

        output_path = destination / filename

        # Download with progress tracking
        def report_hook(block_num, block_size, total_size):
            if progress_callback and total_size > 0:
                downloaded = block_num * block_size
                progress_callback(min(downloaded, total_size), total_size)

        try:
            urllib.request.urlretrieve(download_url, output_path, reporthook=report_hook)
            return output_path
        except urllib.error.URLError as e:
            if output_path.exists():
                output_path.unlink()
            raise ConnectionError(f"Download failed: {e}")

    def fetch_manifest(self, manifest_url: str) -> Dict:
        """Fetch and parse a manifest.json file from a URL."""
        try:
            with urllib.request.urlopen(manifest_url, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to fetch manifest: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid manifest JSON at {manifest_url}: {e}")

    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """
        Compare two semantic version strings.

        Args:
            version1: First version (e.g., "1.2.3")
            version2: Second version (e.g., "1.2.4")

        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        def parse_version(v: str) -> Tuple[int, ...]:
            """Parse version string into tuple of integers."""
            # Remove 'v' prefix if present
            v = v.lstrip('vV')
            # Split by '.' and convert to integers
            try:
                return tuple(int(x) for x in v.split('.'))
            except ValueError:
                # Fallback for non-numeric versions
                return (0, 0, 0)

        v1_parts = parse_version(version1)
        v2_parts = parse_version(version2)

        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += (0,) * (max_len - len(v1_parts))
        v2_parts += (0,) * (max_len - len(v2_parts))

        # Compare
        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        else:
            return 0

    def check_for_updates(self, installed_mods: Dict[str, str]) -> Dict[str, Dict]:
        """
        Check for updates for installed mods.

        Args:
            installed_mods: Dict mapping mod name -> installed version

        Returns:
            Dict mapping mod name -> {'current': version, 'latest': version, 'mod_data': dict}
            Only includes mods with updates available
        """
        updates = {}
        all_mods = self.get_all_mods()

        for mod in all_mods:
            mod_name = mod.get('name')
            store_version = mod.get('version', '0.0.0')

            if mod_name in installed_mods:
                installed_version = installed_mods[mod_name]

                # Compare versions
                if self.compare_versions(installed_version, store_version) < 0:
                    updates[mod_name] = {
                        'current': installed_version,
                        'latest': store_version,
                        'mod_data': mod
                    }

        return updates

    def get_cache_info(self) -> Dict:
        """Get cache status information."""
        if self._cache_timestamp is None:
            return {'cached': False, 'age_minutes': None}

        age_minutes = (time.time() - self._cache_timestamp) / 60
        return {
            'cached': True,
            'age_minutes': round(age_minutes, 1),
            'valid': age_minutes < CACHE_DURATION_MINUTES,
            'cached_at': datetime.fromtimestamp(self._cache_timestamp).isoformat()
        }

    def _normalize_mod(self, mod: Dict) -> Dict:
        """Return a mod dict enriched with computed fields like download_url."""
        normalized = copy.deepcopy(mod)
        download_url = self._resolve_download_url(normalized)
        if download_url:
            normalized['download_url'] = download_url
        return normalized

    def _resolve_download_url(self, mod: Dict) -> Optional[str]:
        """Resolve the direct download URL from the download descriptor."""
        download = mod.get('download')
        if not isinstance(download, dict):
            return None

        dtype = download.get('type')
        if dtype == 'github_release':
            repo = download.get('repo')
            asset = download.get('asset')
            if not repo or not asset:
                return None

            if download.get('latest'):
                return f"https://github.com/{repo}/releases/latest/download/{asset}"

            tag = download.get('tag')
            if not tag:
                version = mod.get('version', '')
                prefix = download.get('tag_prefix', DEFAULT_TAG_PREFIX)
                prefix = prefix if isinstance(prefix, str) else DEFAULT_TAG_PREFIX
                if version:
                    tag = f"{prefix}{version}" if prefix else version
            if not tag:
                return None

            return f"https://github.com/{repo}/releases/download/{tag}/{asset}"

        if dtype == 'direct':
            url = download.get('url')
            if isinstance(url, str) and url.strip():
                return url.strip()

        return None


# Convenience functions for simple usage
def get_store_mods(force_refresh: bool = False) -> List[Dict]:
    """Quick access to get all store mods."""
    api = ModStoreAPI()
    return api.get_all_mods(force_refresh)


def check_mod_updates(installed_mods: Dict[str, str]) -> Dict[str, Dict]:
    """Quick access to check for updates."""
    api = ModStoreAPI()
    return api.check_for_updates(installed_mods)
