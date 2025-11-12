"""
Test script to verify MES configuration
This demonstrates that MES support is properly implemented
"""

import sys
sys.path.insert(0, 'D:\\Dropbox\\VRB Share\\IBKR XSP Option Trader1 (PyQt6) - Dev')

from config import parse_futures_contract, MES_FRONT_MONTH, ES_FRONT_MONTH

def test_mes_configuration():
    """Test MES futures contract parsing"""
    
    print("=" * 60)
    print("MES CONFIGURATION TEST")
    print("=" * 60)
    
    # Test MES contract parsing
    print("\n1. Testing MES Contract Parsing:")
    print(f"   MES_FRONT_MONTH = '{MES_FRONT_MONTH}'")
    
    try:
        mes_info = parse_futures_contract(MES_FRONT_MONTH)
        print(f"   ✅ Successfully parsed MES contract")
        print(f"   Root: {mes_info['root']}")
        print(f"   Month: {mes_info['month_name']} {mes_info['full_year']}")
        print(f"   Expiry: {mes_info['expiry_date']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test ES contract parsing (for comparison)
    print("\n2. Testing ES Contract Parsing:")
    print(f"   ES_FRONT_MONTH = '{ES_FRONT_MONTH}'")
    
    try:
        es_info = parse_futures_contract(ES_FRONT_MONTH)
        print(f"   ✅ Successfully parsed ES contract")
        print(f"   Root: {es_info['root']}")
        print(f"   Month: {es_info['month_name']} {es_info['full_year']}")
        print(f"   Expiry: {es_info['expiry_date']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test instrument configurations
    print("\n3. Testing Instrument Configurations:")
    
    # Import main to access INSTRUMENT_CONFIG
    from main import INSTRUMENT_CONFIG
    
    # Check MES_FOP config
    if 'MES_FOP' in INSTRUMENT_CONFIG:
        mes_config = INSTRUMENT_CONFIG['MES_FOP']
        print(f"   ✅ MES_FOP configuration found")
        print(f"   Name: {mes_config['name']}")
        print(f"   Multiplier: ${mes_config['multiplier']}/point")
        print(f"   Strike Increment: {mes_config['strike_increment']}")
        print(f"   Tick Size ≥$3: ${mes_config['tick_size_above_3']}")
        print(f"   Tick Size <$3: ${mes_config['tick_size_below_3']}")
        print(f"   Description: {mes_config['description']}")
        
        # Verify multiplier is correct
        if mes_config['multiplier'] == '5':
            print(f"   ✅ Multiplier is correct ($5/point)")
        else:
            print(f"   ❌ Multiplier incorrect: {mes_config['multiplier']}")
            return False
    else:
        print(f"   ❌ MES_FOP configuration not found")
        return False
    
    # Compare with ES_FOP
    print("\n4. Comparison: MES vs ES:")
    es_config = INSTRUMENT_CONFIG['ES_FOP']
    
    print(f"   ES Multiplier:  ${es_config['multiplier']}/point")
    print(f"   MES Multiplier: ${mes_config['multiplier']}/point")
    print(f"   Ratio: ES is {int(es_config['multiplier']) / int(mes_config['multiplier'])}x MES")
    
    # Calculate example contract values
    example_price = 20.0
    es_value = example_price * int(es_config['multiplier'])
    mes_value = example_price * int(mes_config['multiplier'])
    
    print(f"\n5. Example Contract Value (${example_price} option):")
    print(f"   ES Contract:  ${example_price} × {es_config['multiplier']} = ${es_value:.2f}")
    print(f"   MES Contract: ${example_price} × {mes_config['multiplier']} = ${mes_value:.2f}")
    print(f"   Difference: ${es_value - mes_value:.2f} ({(es_value/mes_value):.1f}x)")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - MES SUPPORT VERIFIED")
    print("=" * 60)
    
    print("\nTo use MES trading:")
    print("1. Edit config.py")
    print("2. Set: SELECTED_INSTRUMENT = 'MES'")
    print("3. Save and run: python main.py")
    
    return True

if __name__ == "__main__":
    success = test_mes_configuration()
    sys.exit(0 if success else 1)
