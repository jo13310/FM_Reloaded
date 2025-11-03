#!/usr/bin/env python3
"""
Test script to verify file deletion security validation.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.security_utils import can_delete_game_file

# Simulate game root
game_root = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Football Manager 26")

print("=" * 70)
print("Testing File Deletion Security Validation")
print("=" * 70)

# Test cases
test_cases = [
    # (file_path, expected_allowed, description)
    ("data/database/db/1800/english.ltc", True, "License file (.ltc) - SHOULD BE ALLOWED"),
    ("data/database/db/1800/test.dbc", True, "Database file (.dbc) - SHOULD BE ALLOWED"),
    ("data/database/db/2600/edt/permanent/fake.edt", True, "Editor data template (.edt) - SHOULD BE ALLOWED"),
    ("data/database/db/2600/lnc/all/test.lnc", True, "Language file (.lnc) - SHOULD BE ALLOWED"),
    ("tactics/my-tactic.fmf", True, "Tactic file (.fmf) - SHOULD BE ALLOWED"),
    ("fm26.exe", False, "Game executable - SHOULD BE BLOCKED"),
    ("FM26.exe", False, "Game executable (uppercase) - SHOULD BE BLOCKED"),
    ("winhttp.dll", False, "DLL file - SHOULD BE BLOCKED"),
    ("data/random.txt", False, "Text file (not in whitelist) - SHOULD BE BLOCKED"),
    ("UnityPlayer.dll", False, "Unity core file - SHOULD BE BLOCKED"),
    ("steam_api64.dll", False, "Steam library - SHOULD BE BLOCKED"),
]

print("\nRunning tests...\n")

passed = 0
failed = 0

for file_path, expected_allowed, description in test_cases:
    target = game_root / file_path
    allowed, reason = can_delete_game_file(target, game_root)

    # Check if result matches expectation
    test_passed = (allowed == expected_allowed)
    status = "[PASS]" if test_passed else "[FAIL]"

    if test_passed:
        passed += 1
    else:
        failed += 1

    print(f"{status} | {description}")
    print(f"       File: {file_path}")
    print(f"       Expected: {'ALLOW' if expected_allowed else 'BLOCK'}, Got: {'ALLOW' if allowed else 'BLOCK'}")
    if not allowed:
        print(f"       Reason: {reason}")
    print()

print("=" * 70)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 70)

if failed == 0:
    print("\n[SUCCESS] All security tests passed!")
    sys.exit(0)
else:
    print(f"\n[ERROR] {failed} test(s) failed!")
    sys.exit(1)
