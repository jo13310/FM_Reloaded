#!/usr/bin/env python3
"""
Test script for manual installation functionality.
Tests the mod detection and wizard components.
"""

import sys
import tempfile
import zipfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from mod_detector import analyze_mod_source, generate_basic_manifest
    from platform_detector import detect_fm_installations, get_cache_dir
    print("✓ Successfully imported enhanced modules")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)


def create_test_mod():
    """Create a test mod without manifest for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_mod_"))
    
    # Create a simple BepInEx plugin structure
    plugin_dir = temp_dir / "plugins"
    plugin_dir.mkdir()
    
    # Create a dummy DLL file
    dummy_dll = plugin_dir / "TestMod.dll"
    dummy_dll.write_bytes(b"FAKE_DLL_CONTENT_FOR_TESTING")
    
    # Create a README
    readme = temp_dir / "README.txt"
    readme.write_text("Test Mod\nA simple test mod for BepInEx.\nVersion: 1.0.0\nAuthor: Test Author")
    
    print(f"Created test mod at: {temp_dir}")
    return temp_dir


def test_mod_detection():
    """Test the mod detection system."""
    print("\n=== Testing Mod Detection ===")
    
    # Create test mod
    test_mod_path = create_test_mod()
    
    try:
        # Analyze the mod
        analysis = analyze_mod_source(test_mod_path)
        
        print(f"Detected type: {analysis.detected_type}")
        print(f"Confidence: {analysis.confidence:.0%}")
        print(f"Suggested name: {analysis.suggested_name}")
        print(f"Suggested files: {len(analysis.suggested_files)}")
        
        if analysis.warnings:
            print("Warnings:")
            for warning in analysis.warnings:
                print(f"  - {warning}")
        
        if analysis.install_suggestions:
            print("Suggestions:")
            for suggestion in analysis.install_suggestions:
                print(f"  - {suggestion}")
        
        # Test manifest generation
        manifest = generate_basic_manifest(analysis)
        print(f"\nGenerated manifest keys: {list(manifest.keys())}")
        
        # Cleanup
        import shutil
        shutil.rmtree(test_mod_path, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"✗ Detection failed: {e}")
        return False


def test_platform_detection():
    """Test the platform detection system."""
    print("\n=== Testing Platform Detection ===")
    
    try:
        # Test cache directory detection
        cache_dir = get_cache_dir()
        print(f"Cache directory: {cache_dir}")
        
        # Test FM installation detection
        installations = detect_fm_installations()
        print(f"Found {len(installations)} FM installations:")
        
        for i, installation in enumerate(installations[:3]):  # Show first 3
            print(f"  {i+1}. {installation.get('source', 'Unknown')} at {installation.get('path', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"✗ Platform detection failed: {e}")
        return False


def test_zip_analysis():
    """Test zip file analysis."""
    print("\n=== Testing ZIP Analysis ===")
    
    try:
        # Create test ZIP
        temp_dir = Path(tempfile.mkdtemp(prefix="test_zip_"))
        zip_path = temp_dir / "test_mod.zip"
        
        # Create test files
        test_mod = create_test_mod()
        
        # Create ZIP
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for file_path in test_mod.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(test_mod))
        
        print(f"Created test ZIP: {zip_path}")
        
        # Analyze ZIP
        analysis = analyze_mod_source(zip_path)
        print(f"ZIP detected type: {analysis.detected_type}")
        print(f"ZIP confidence: {analysis.confidence:.0%}")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return True
        
    except Exception as e:
        print(f"✗ ZIP analysis failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Testing FM Reloaded Enhanced Features")
    print("=" * 50)
    
    tests = [
        ("Platform Detection", test_platform_detection),
        ("Mod Detection", test_mod_detection),
        ("ZIP Analysis", test_zip_analysis),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    passed = 0
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("✓ All tests passed! Enhanced features are working correctly.")
        return 0
    else:
        print("✗ Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
