# TradeStation GlobalDictionary Python Interface

A Python interface for TradeStation 10 EasyLanguage GlobalDictionary using COM objects. Enables bidirectional communication between TradeStation and Python applications.

## Quick Start

### Prerequisites
- Windows OS
- TradeStation 10 running
- Python 3.8+ with pywin32 installed

### Setup

1. **Install pywin32** (already done in this project):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m pip install pywin32
   python Scripts\pywin32_postinstall.py -install
   ```

2. **Import ELD file into TradeStation 10**:
   - Open TradeStation 10
   - File → Import → EasyLanguage
   - Select `_PYTHON GLOBALDICTIONARY.ELD`
   - Verify compilation succeeds

3. **Test the connection**:
   ```powershell
   .\.venv\Scripts\python.exe test_connectivity.py
   ```

4. **Run the demo**:
   ```powershell
   .\.venv\Scripts\python.exe Demo.py
   ```
   Press Ctrl+C to stop.

## Project Files

- **`GlobalDictionary.py`** - Core COM interface module
- **`Demo.py`** - Full demonstration with event handlers
- **`test_connectivity.py`** - Quick connection verification
- **`IB_INTEGRATION.md`** - Integration guide for IB API
- **`_PYTHON GLOBALDICTIONARY.ELD`** - TradeStation component (must be imported)
- **`.github/copilot-instructions.md`** - AI coding assistant guidance

## Basic Usage

```python
import GlobalDictionary
import pythoncom
import time

# Define event handlers
def on_add(self, key, value, size):
    print(f"Added: {key} = {value}")

def on_change(self, key, value, size):
    print(f"Changed: {key} = {value}")

# Create dictionary with events
GD = GlobalDictionary.create("MY_DICT", add=on_add, change=on_change)

# Write data (accessible from TradeStation)
GD["PRICE"] = 6851.25
GD["SIGNAL"] = {"action": "BUY", "qty": 1}

# Read data (written by TradeStation)
close_price = GD["CLOSE"]

# Event loop (required for receiving events)
while True:
    pythoncom.PumpWaitingMessages()
    time.sleep(0.01)
```

## Data Types

Automatic encoding/decoding between Python and EasyLanguage:
- Primitives: `bool`, `int`, `float`, `str`
- Collections: `list`, `dict` (including nested structures)

## Integration with Interactive Brokers

This project is designed to integrate with a custom IB Official API application (not ibsync/ibridgepy). See **`IB_INTEGRATION.md`** for:
- Event-driven signal processing patterns
- Shared state dictionary patterns  
- Signal queue with acknowledgment
- Threading considerations
- Error handling strategies

## Resources

- [TradeStation Forum Discussion](https://community.tradestation.com/Discussions/Topic.aspx?Topic_ID=175930)
- Module documentation: See docstrings in `GlobalDictionary.py`
- Integration guide: `IB_INTEGRATION.md`

## Status

✅ **SKELETON READY**: The interface is tested and operational. Ready for integration into your IB API application.

**Test Results (November 5, 2025)**:
- pywin32 installed and configured ✓
- TradeStation 10 COM connection verified ✓
- Real-time event handling tested ✓
- Complex data structures (nested lists/dicts) working ✓
- Event handlers (add/change/remove/clear) functional ✓

## Next Steps

1. Review `IB_INTEGRATION.md` for integration patterns
2. Design signal data structure for your trading strategies
3. Copy `GlobalDictionary.py` to your IB API project
4. Implement event handlers for TradeStation signals
5. Test with paper trading before going live

## Author

Original module by JohnR (v00.00.06, 2023)
