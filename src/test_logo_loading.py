#!/usr/bin/env python3
"""Test script to verify logo loading works correctly."""

import sys
import tkinter as tk
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import asset_path

def test_logo_loading():
    """Test that the logo can be loaded successfully."""
    print("Testing logo loading...")
    
    # Test asset path resolution
    png_path = asset_path("fm_reloaded.png")
    print(f"Logo path: {png_path}")
    print(f"File exists: {png_path.exists()}")
    
    if not png_path.exists():
        print("ERROR: Logo file does not exist!")
        return False
    
    # Test Tkinter PhotoImage loading
    try:
        # Create a root window first (required for PhotoImage)
        root = tk.Tk()
        root.withdraw()  # Hide the window
        
        # Try to create PhotoImage
        icon = tk.PhotoImage(file=str(png_path))
        print("PhotoImage created successfully")
        
        # Test window icon setting
        root.iconphoto(True, icon)
        print("Window icon set successfully")
        
        root.destroy()
        print("✓ Logo loading test PASSED")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to load logo: {e}")
        return False

if __name__ == "__main__":
    success = test_logo_loading()
    sys.exit(0 if success else 1)
