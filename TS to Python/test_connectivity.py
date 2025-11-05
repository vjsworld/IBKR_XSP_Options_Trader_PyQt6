"""
Simple connectivity test for TradeStation 10 GlobalDictionary COM interface.
Run this before the full Demo.py to verify TradeStation is accessible.
"""

import sys

try:
    from win32com import client
    print("✓ pywin32 imported successfully")
except ImportError as e:
    print(f"✗ Failed to import pywin32: {e}")
    print("\nInstall with:")
    print("  python -m pip install pywin32")
    print("  python Scripts\\pywin32_postinstall.py -install")
    sys.exit(1)

try:
    print("\n--- Testing TradeStation COM Connection ---")
    _GlobalDictionaries = client.gencache.EnsureDispatch("GSD.ELDictionaries")  # type: ignore
    print("✓ Successfully connected to TradeStation GlobalDictionaries COM object")
    
    # Try to create a test dictionary
    test_dict = _GlobalDictionaries.GetDictionary("CONNECTIVITY_TEST")
    print("✓ Successfully created/accessed test dictionary")
    
    # Try basic operations
    test_dict.Clear()
    test_dict.Add("test_key", "v\x03test_value")
    size = test_dict.size
    print(f"✓ Basic operations work (size: {size})")
    
    test_dict.Clear()
    print("✓ Cleanup successful")
    
    print("\n=== TradeStation Connection Test PASSED ===")
    print("\nYou can now run Demo.py for full functionality testing.")
    
except Exception as e:
    print(f"\n✗ TradeStation connection failed: {e}")
    print("\nTroubleshooting steps:")
    print("  1. Ensure TradeStation 10 is running")
    print("  2. Verify '_PYTHON GLOBALDICTIONARY.ELD' is imported and compiled in TradeStation")
    print("  3. Check Windows Event Viewer for COM errors")
    print("  4. Try restarting TradeStation")
    sys.exit(1)
