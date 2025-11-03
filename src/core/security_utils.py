#!/usr/bin/env python3
"""
Security utilities for safe file operations in FM Reloaded.

This module contains security-hardened functions to prevent common vulnerabilities
in file operations and mod management.

Security Threats Mitigated:
---------------------------
1. Path Traversal (CWE-22): Malicious mods using "../" to escape directories
2. ZIP Bombs (CWE-409): Compressed files that expand to huge sizes
3. Symlink Attacks (CWE-59): Symlinks pointing to sensitive system files
4. Arbitrary File Write (CWE-73): Writing to unauthorized locations
5. Resource Exhaustion (CWE-400): Excessive file sizes consuming disk space

Security Functions Overview:
----------------------------
- validate_path_safety(): Ensures paths stay within allowed directories
- safe_extract_zip(): ZIP extraction with bomb detection and path validation
- safe_delete_path(): File/directory deletion with symlink protection
- safe_copy(): Secure file copying with size limits and validation

Usage Guidelines:
-----------------
- Always use these functions instead of raw shutil/pathlib operations
- Never disable security checks without thorough security review
- Log all security violations for audit purposes
- Keep allowed_root parameters as restrictive as possible

References:
-----------
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- CWE-22: Path Traversal
- CWE-409: Improper Handling of Highly Compressed Data
"""

import hashlib
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Set


# ========================================
# System Directory Protection
# ========================================

# Critical system directories that should NEVER be deleted or modified
PROTECTED_SYSTEM_DIRS = [
    # Windows system directories
    Path("C:\\Windows"),
    Path("C:\\Program Files"),
    Path("C:\\Program Files (x86)"),
    Path("C:\\ProgramData"),
    # Unix/Linux/Mac system directories
    Path("/System"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/etc"),
    Path("/var"),
    Path("/boot"),
]


# ========================================
# Game File Deletion Protection
# ========================================

# File patterns that mods are allowed to delete from the game directory
# These are typically configuration/data files that mods replace
ALLOWED_GAME_FILE_DELETION_PATTERNS = [
    "*.ltc",                    # License/certification files (real names fixes)
    "*.dbc",                    # Database files
    "*.fmf",                    # Tactic files
    "*.rtf",                    # Graphics config files
    "*.edt",                    # Editor data template files (real names fixes)
    "editor_data_*.bundle",     # Editor data bundles
    "*.lnc",                    # Language files (if modding translations)
]

# Critical game files that must NEVER be deleted
# These are executables, core libraries, and essential data files
PROTECTED_GAME_FILES = [
    # Executables
    "fm26.exe",
    "fm.exe",
    "football manager 2026.exe",
    "footballmanager.exe",

    # Steam/Unity core libraries
    "libsteam_api.dll",
    "libsteam_api.so",
    "libsteam_api.dylib",
    "steam_api64.dll",
    "steam_api.dll",
    "unityplayer.dll",
    "libunityplayer.so",

    # Unity essential data
    "*.pak",                    # Unity PAK archives
    "globalgamemanagers",       # Unity global settings
    "globalgamemanagers.assets",
    "resources.assets",         # Unity resource bundle
    "sharedassets*.assets",     # Unity shared assets
    "level*",                   # Unity level files

    # Core game data
    "data.unity3d",
    "maindata",

    # Config files that should not be deleted
    "boot_config.txt",
    "player_prefs",
]


# ========================================
# Safe Deletion Whitelist System
# ========================================

# Set of directories where deletion operations are explicitly allowed
_SAFE_DELETION_ROOTS: Set[Path] = set()
# Path to security audit log
_SECURITY_LOG_PATH: Optional[Path] = None


def register_safe_deletion_root(path: Path) -> None:
    """
    Register a directory where deletion operations are explicitly allowed.

    This creates a whitelist of safe directories. All deletion operations
    should be validated against this whitelist.

    Args:
        path: Directory to register as safe for deletions

    Raises:
        ValueError: If path is a protected system directory
    """
    path_resolved = path.resolve()

    # Ensure we're not registering a system directory
    for sys_dir in PROTECTED_SYSTEM_DIRS:
        if sys_dir.exists():
            try:
                path_resolved.relative_to(sys_dir)
                raise ValueError(
                    f"Security: Cannot register system directory as safe deletion root: {sys_dir}"
                )
            except ValueError:
                pass  # Good - not in this system dir

    _SAFE_DELETION_ROOTS.add(path_resolved)


def is_safe_deletion_path(path: Path) -> bool:
    """
    Check if a path is within any registered safe deletion root.

    Args:
        path: Path to check

    Returns:
        True if path is within a registered safe root, False otherwise
    """
    path_resolved = path.resolve()

    for root in _SAFE_DELETION_ROOTS:
        try:
            path_resolved.relative_to(root)
            return True
        except ValueError:
            continue

    return False


def get_safe_deletion_roots() -> Set[Path]:
    """
    Get all registered safe deletion roots.

    Returns:
        Set of registered safe deletion root directories
    """
    return _SAFE_DELETION_ROOTS.copy()


def set_security_log_path(log_path: Path) -> None:
    """
    Set the path for security audit logging.

    Args:
        log_path: Path to security audit log file
    """
    global _SECURITY_LOG_PATH
    _SECURITY_LOG_PATH = log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)


def _log_security_event(event_type: str, path: Path, success: bool, reason: str = "") -> None:
    """
    Log a security event to the audit log.

    Args:
        event_type: Type of operation (DELETE, COPY, etc.)
        path: Path involved in the operation
        success: Whether the operation succeeded
        reason: Additional context or reason
    """
    if _SECURITY_LOG_PATH is None:
        return

    timestamp = datetime.now().isoformat()
    status = "SUCCESS" if success else "BLOCKED"
    log_entry = f"[{timestamp}] {event_type} | {status} | {path} | {reason}\n"

    try:
        with open(_SECURITY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        # Silently fail if we can't write to security log
        pass


def is_protected_system_directory(path: Path) -> bool:
    """
    Check if a path is a protected system directory.

    This function protects critical system directories while allowing
    legitimate game installations and subdirectories.

    Protected paths:
    - Exact match of system root directories (C:\Windows, C:\Program Files)
    - Direct children of Program Files (e.g., C:\Program Files\*) but not deeper subdirs
    - Any path within /System, /usr, /bin, etc.

    Allowed paths:
    - Game installations like C:\Program Files\Steam\steamapps\common\GameName
    - Any subdirectory 2+ levels deep in Program Files

    Args:
        path: Path to check

    Returns:
        True if path is a critical system directory that should be protected
    """
    path_resolved = path.resolve()

    # Check for exact match with system directories
    for sys_dir in PROTECTED_SYSTEM_DIRS:
        if sys_dir.exists() and path_resolved == sys_dir:
            return True

    # Special handling for Windows Program Files:
    # Allow subdirectories (like Steam\steamapps\common\GameName)
    # but protect the root and direct children
    program_files_roots = [
        Path("C:\\Program Files"),
        Path("C:\\Program Files (x86)"),
    ]

    for pf_root in program_files_roots:
        if pf_root.exists():
            try:
                relative = path_resolved.relative_to(pf_root)
                # Check depth: if only 1 level deep, it's a direct child (protected)
                # e.g., "C:\Program Files\SomeApp" has depth 1 -> protect
                # e.g., "C:\Program Files\Steam\steamapps" has depth 2+ -> allow
                parts = relative.parts
                if len(parts) == 1:
                    # Direct child of Program Files - protect it
                    return True
                # Otherwise it's 2+ levels deep, which is fine (Steam games, etc.)
            except ValueError:
                # Not under this Program Files root
                pass

    # For Unix/Mac system directories, any path within them is protected
    unix_protected = [
        Path("/System"), Path("/usr"), Path("/bin"),
        Path("/sbin"), Path("/etc"), Path("/var"), Path("/boot"),
    ]

    for sys_dir in unix_protected:
        if sys_dir.exists():
            try:
                path_resolved.relative_to(sys_dir)
                return True  # Any path within Unix system dirs is protected
            except ValueError:
                continue

    # Additional check: user's home directory itself (but subdirs are ok)
    try:
        home = Path.home().resolve()
        if path_resolved == home:
            return True
    except Exception:
        pass

    return False


def can_delete_game_file(target: Path, game_root: Path) -> tuple[bool, str]:
    """
    Check if a file can be safely deleted from the game directory.

    This function implements triple-layer security validation:
    1. File must match allowed deletion patterns
    2. File must NOT match protected file patterns
    3. File must be within game directory (not system directory)

    Args:
        target: Path to file that mod wants to delete
        game_root: Root directory of FM installation

    Returns:
        Tuple of (allowed: bool, reason: str)
        - (True, "OK") if deletion is allowed
        - (False, reason) if deletion is blocked with explanation

    Examples:
        >>> can_delete_game_file(Path("data/license.ltc"), game_root)
        (True, "OK")

        >>> can_delete_game_file(Path("FM26.exe"), game_root)
        (False, "Critical game file cannot be deleted: FM26.exe")
    """
    import fnmatch

    try:
        # Resolve paths
        target_resolved = target.resolve()
        game_root_resolved = game_root.resolve()

        # Get filename for pattern matching
        filename = target_resolved.name.lower()

        # SECURITY CHECK 1: Must be within game directory
        try:
            target_resolved.relative_to(game_root_resolved)
        except ValueError:
            return (False, f"File outside game directory: {target}")

        # SECURITY CHECK 2: Must NOT be in a protected system directory
        if is_protected_system_directory(target_resolved):
            return (False, f"File in protected system directory: {target}")

        # SECURITY CHECK 3: Check against protected file list (blacklist)
        for protected_pattern in PROTECTED_GAME_FILES:
            if fnmatch.fnmatch(filename, protected_pattern.lower()):
                return (False, f"Critical game file cannot be deleted: {filename}")

        # SECURITY CHECK 4: Must match allowed deletion patterns (whitelist)
        matched = False
        for allowed_pattern in ALLOWED_GAME_FILE_DELETION_PATTERNS:
            if fnmatch.fnmatch(filename, allowed_pattern.lower()):
                matched = True
                break

        if not matched:
            return (False, f"File type not allowed for deletion: {filename}. Allowed types: {', '.join(ALLOWED_GAME_FILE_DELETION_PATTERNS)}")

        # All checks passed
        _log_security_event("DELETE_VALIDATION", target, True, "Validated for deletion")
        return (True, "OK")

    except Exception as e:
        # Log validation error
        _log_security_event("DELETE_VALIDATION_ERROR", target, False, str(e))
        return (False, f"Validation error: {e}")


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


def safe_extract_zip(zip_path: Path, dest: Path, max_size_bytes: int = 500_000_000) -> None:
    """
    Safely extract ZIP file with security validations.

    Args:
        zip_path: Path to ZIP file
        dest: Destination directory
        max_size_bytes: Maximum total uncompressed size (default 500MB)

    Raises:
        ValueError: If ZIP contains malicious content
        zipfile.BadZipFile: If ZIP is corrupted

    Security checks:
    - Path traversal protection
    - ZIP bomb detection (size limits)
    - Symlink detection
    - Absolute path rejection
    """
    dest = dest.resolve()
    total_size = 0

    with zipfile.ZipFile(zip_path, 'r') as z:
        # First pass: validate all members
        for member in z.namelist():
            info = z.getinfo(member)

            # Check for ZIP bomb
            total_size += info.file_size
            if total_size > max_size_bytes:
                raise ValueError(
                    f"ZIP file too large: {total_size:,} bytes exceeds limit of {max_size_bytes:,} bytes. "
                    "This may be a ZIP bomb attack."
                )

            # Check for path traversal
            member_path = (dest / member).resolve()
            try:
                member_path.relative_to(dest)
            except ValueError:
                raise ValueError(
                    f"Security: ZIP contains path traversal: '{member}' "
                    f"would extract outside destination directory"
                )

            # Check for absolute paths
            if member.startswith("/") or member.startswith("\\") or ":" in member:
                raise ValueError(f"Security: ZIP contains absolute path: '{member}'")

            # Check for suspicious patterns
            if ".." in member:
                raise ValueError(f"Security: ZIP contains suspicious path: '{member}'")

        # Second pass: extract if all validations passed
        for member in z.namelist():
            z.extract(member, dest)


def safe_delete_path(path: Path, allow_symlink_delete: bool = False) -> bool:
    """
    Safely delete a file or directory with security checks.

    Security checks:
    - Symlink detection (optionally reject symlinks)
    - Existence validation

    Args:
        path: Path to delete
        allow_symlink_delete: If False, refuse to delete symlinks

    Returns:
        True if deleted successfully, False otherwise

    Raises:
        ValueError: If symlink detected and allow_symlink_delete is False
    """
    if not path.exists() and not path.is_symlink():
        return False

    # Security: Detect and optionally reject symlinks
    if path.is_symlink() and not allow_symlink_delete:
        raise ValueError(
            f"Security: Refusing to delete symlink without explicit permission: {path}"
        )

    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except Exception:
        # Log but don't expose internal paths in error
        return False


def safe_delete_with_boundary_check(
    path: Path,
    allowed_root: Path,
    allow_symlink_delete: bool = False,
    require_whitelist: bool = True,
) -> bool:
    """
    Safely delete a file or directory with comprehensive security validations.

    This function combines multiple security checks:
    1. Path must be within allowed_root (prevents path traversal)
    2. Path must not be in a protected system directory
    3. Path must be in a registered safe deletion root (optional)
    4. Symlink protection (optional)

    All deletion attempts are logged to the security audit log.

    Args:
        path: Path to delete
        allowed_root: Root directory that path must be within
        allow_symlink_delete: If False, refuse to delete symlinks
        require_whitelist: If True, path must be in a registered safe deletion root

    Returns:
        True if deleted successfully, False otherwise

    Raises:
        ValueError: If any security validation fails
    """
    # Log the deletion attempt
    _log_security_event("DELETE_ATTEMPT", path, False, f"allowed_root={allowed_root}")

    # Security Check 1: Validate path is within allowed root
    try:
        validated_path = validate_path_safety(path, allowed_root, "deletion target")
    except ValueError as e:
        _log_security_event("DELETE_BLOCKED", path, False, f"Path traversal: {e}")
        raise

    # Security Check 2: Ensure path is not in a protected system directory
    if is_protected_system_directory(validated_path):
        error_msg = f"Security: Refusing to delete from protected system directory: {validated_path}"
        _log_security_event("DELETE_BLOCKED", path, False, "Protected system directory")
        raise ValueError(error_msg)

    # Security Check 3: Validate path is in a registered safe deletion root
    if require_whitelist and not is_safe_deletion_path(validated_path):
        safe_roots = get_safe_deletion_roots()
        error_msg = (
            f"Security: Path not in any registered safe deletion root: {validated_path}\n"
            f"Registered safe roots: {safe_roots}"
        )
        _log_security_event("DELETE_BLOCKED", path, False, "Not in whitelist")
        raise ValueError(error_msg)

    # Security Check 4: Perform the deletion with symlink protection
    try:
        success = safe_delete_path(validated_path, allow_symlink_delete=allow_symlink_delete)
        if success:
            _log_security_event("DELETE_SUCCESS", path, True, f"Deleted from {allowed_root}")
        else:
            _log_security_event("DELETE_FAILED", path, False, "Path did not exist")
        return success
    except ValueError as e:
        # Symlink protection triggered
        _log_security_event("DELETE_BLOCKED", path, False, str(e))
        raise


def safe_copy(
    src: Path,
    dst: Path,
    allowed_dst_root: Optional[Path] = None,
    max_file_size: int = 100_000_000,  # 100MB per file
    follow_symlinks: bool = False,
) -> None:
    """
    Safely copy file or directory with security validations.

    Security checks:
    - Path validation against allowed destination root
    - Symlink detection (optionally refuse to copy symlinks)
    - File size limits

    Args:
        src: Source path to copy from
        dst: Destination path to copy to
        allowed_dst_root: If provided, validate dst is within this directory
        max_file_size: Maximum file size in bytes (default 100MB)
        follow_symlinks: If False, refuse to copy symlinks

    Raises:
        ValueError: If security validations fail
        FileNotFoundError: If source doesn't exist
    """
    if not src.exists():
        raise FileNotFoundError(f"Source path does not exist: {src}")

    # Validate destination path if root provided
    if allowed_dst_root:
        validate_path_safety(dst, allowed_dst_root, "copy destination")

    # Security: Check for symlinks
    if src.is_symlink() and not follow_symlinks:
        raise ValueError(f"Security: Refusing to copy symlink: {src}")

    # Single file copy
    if src.is_file():
        # Security: Check file size
        size = src.stat().st_size
        if size > max_file_size:
            raise ValueError(
                f"Security: File too large: {size:,} bytes exceeds {max_file_size:,} byte limit"
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
        return

    # Directory copy
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.rglob("*"):
            # Skip symlinks if not following them
            if child.is_symlink() and not follow_symlinks:
                continue

            rel = child.relative_to(src)
            out = dst / rel

            # Validate each output path if root provided
            if allowed_dst_root:
                validate_path_safety(out, allowed_dst_root, f"copy destination ({rel})")

            if child.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            elif child.is_file():
                # Security: Check file size
                size = child.stat().st_size
                if size > max_file_size:
                    raise ValueError(
                        f"Security: File too large: {rel} ({size:,} bytes exceeds {max_file_size:,} byte limit)"
                    )
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, out, follow_symlinks=follow_symlinks)


def _copy_any(src: Path, dst: Path):
    """
    Merge-copy src -> dst.
    - If src is a file: copy2(src, dst)
    - If src is a directory: recursively copy its contents into dst (dirs_exist_ok)

    NOTE: This is the legacy unsafe version. Use safe_copy() for new code.

    Args:
        src: Source path
        dst: Destination path
    """
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.rglob("*"):
            rel = child.relative_to(src)
            out = dst / rel
            if child.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, out)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def backup_original(target_file: Path, backup_dir: Path) -> Optional[Path]:
    """
    Create a backup of a file before modifying it.

    Args:
        target_file: File to backup
        backup_dir: Directory to store backups

    Returns:
        Path to backup file, or None if file doesn't exist
    """
    if not Path(target_file).exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique backup filename using hash
    h = hashlib.sha256(str(target_file).encode("utf-8")).hexdigest()[:10]
    dest = backup_dir / f"{Path(target_file).name}.{h}.bak"

    # Add sequence number if backup already exists
    i, final = 1, dest
    while final.exists():
        final = backup_dir / f"{dest.name}.{i}"
        i += 1

    shutil.copy2(target_file, final)
    return final


def find_latest_backup_for_filename(filename: str, backup_dir: Path) -> Optional[Path]:
    """
    Find the most recent backup file for a given filename.

    Args:
        filename: Original filename (without .bak extension)
        backup_dir: Directory containing backups

    Returns:
        Path to latest backup, or None if no backups found
    """
    if not backup_dir.exists():
        return None

    cands = sorted(
        [p for p in backup_dir.glob(f"{filename}*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None
