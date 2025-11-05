# TradeStation GlobalDictionary Python Interface

## Project Overview
This project provides a Python interface to TradeStation 10 EasyLanguage GlobalDictionary using COM objects. It enables bidirectional communication between Python applications and TradeStation trading platform through shared dictionaries.

**Current Use Case**: Skeleton interface for integration with a custom Python application that uses Interactive Brokers official API (not ibsync or ibridgepy) - allowing TradeStation signals/analysis to trigger IB trades.

## Core Architecture

### Key Components
- **`GlobalDictionary.py`**: Main module implementing the COM interface wrapper
- **`Demo.py`**: Usage demonstration with event handling examples
- **`_PYTHON GLOBALDICTIONARY.ELD`**: TradeStation EasyLanguage component (must be imported into TradeStation)

### Critical Dependencies
- **pywin32**: Essential for COM object interaction
- **Windows environment**: Required for TradeStation COM objects
- **TradeStation 10**: Must be running with the ELD file imported and compiled

## Development Patterns

### GlobalDictionary Creation
Always use the factory function `create()` instead of direct class instantiation:
```python
GD = GlobalDictionary.create("DEMO", add=GD_add, remove=GD_remove, change=GD_change, clear=GD_clear)
```

### Event Handler Signatures
Event handlers have specific signatures that must be followed:
- `add(self, key, value, size)` - triggered when items are added
- `remove(self, key, size)` - triggered when items are removed  
- `change(self, key, value, size)` - triggered when items are modified
- `clear(self)` - triggered when dictionary is cleared

### Data Type Encoding
The module automatically encodes/decodes between Python and EasyLanguage types:
- Python `bool/int/float/str` ↔ EasyLanguage primitives
- Python `list` ↔ EasyLanguage Vector (XML-based)
- Python `dict` ↔ EasyLanguage Dictionary (XML-based)

### Event Loop Pattern
Applications must pump COM messages to receive events:
```python
while True:
    pythoncom.PumpWaitingMessages()
    time.sleep(0.01)  # Prevents high CPU usage
```

## Development Workflow

### Environment Setup
1. Install pywin32: `python -m pip install pywin32` (as administrator)
2. Run post-install: `python pywin32_postinstall.py -install`
3. Import `_PYTHON GLOBALDICTIONARY.ELD` into TradeStation
4. Ensure TradeStation is running before testing Python code

### Testing Strategy
- Use `Demo.py` as the primary test harness
- Test with various data types: primitives, nested lists, complex dictionaries
- Verify event handlers trigger correctly for all operations
- Test graceful shutdown with Ctrl+C signal handling

### Debugging COM Issues
- Check TradeStation platform is running
- Verify ELD file is properly imported and compiled
- Use `_GlobalDictionaries.GetDictionary(name)` to test COM connectivity
- Monitor Windows Event Viewer for COM-related errors

## Integration Points

### TradeStation Interop
- Dictionary names must match between Python and EasyLanguage code
- Use the provided encoding/decoding functions for complex data structures
- Handle COM exceptions gracefully as TradeStation may disconnect

### XML Processing
Complex data types are serialized as XML-like strings with special character encoding. The `XML_Fix()` function handles character substitution for valid XML parsing.

## Key Files Reference
- `GlobalDictionary.py` lines 35-40: Type encoding constants
- `GlobalDictionary.py` lines 240-280: XML decoding logic for nested structures
- `Demo.py` lines 30-40: Event handler implementation examples
- TradeStation Forum: https://community.tradestation.com/Discussions/Topic.aspx?Topic_ID=175930