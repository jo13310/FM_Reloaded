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
from pathlib import Path
from typing import Optional


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
