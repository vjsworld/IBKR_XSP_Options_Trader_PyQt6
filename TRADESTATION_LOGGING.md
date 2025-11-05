# TradeStation Communication Logging

## Overview

The TradeStationManager now logs **ALL** incoming communications from TradeStation's GlobalDictionary in real-time. This provides full visibility into the data stream for debugging and monitoring.

## What Gets Logged

### 1. Initial Connection
When TradeStation connects, you'll see:
```
═══════════════════════════════════════════════════════
✅ TRADESTATION CONNECTED: GlobalDictionary 'IBKR_TRADER'
📡 Listening for TradeStation signals...
═══════════════════════════════════════════════════════
```

### 2. New Keys Added (on_signal_add)
When TradeStation adds a new key to the dictionary:
```
[TS→PYTHON] NEW KEY: 'ENTRY_12345' = {'action': 'BUY_CALL', 'symbol': 'XSP', 'quantity': 1}
```

**Also appears in GUI log window as:**
```
[TS] TS ADD: ENTRY_12345 = {'action': 'BUY_CALL', 'symbol': 'XSP', 'quantity': 1}
```

### 3. Keys Changed (on_signal_change)
When TradeStation changes an existing key:
```
[TS→PYTHON] CHANGED KEY: 'TS_STRATEGY_STATE' = LONG
```

**Also appears in GUI log window as:**
```
[TS] TS CHANGE: TS_STRATEGY_STATE = LONG
```

### 4. Acknowledgments Sent Back
When Python acknowledges receipt of a signal:
```
[PYTHON→TS] Sent acknowledgment: ACK_ENTRY_12345
```

### 5. Strategy State Changes
When strategy state updates:
```
[TS→PYTHON] Strategy state changed to: LONG
```

## Message Flow Example

**Complete interaction sequence:**

```
1. [TS→PYTHON] NEW KEY: 'ENTRY_001' = {'action': 'BUY_CALL', 'symbol': 'XSP', 'quantity': 1}
2. [PYTHON→TS] Sent acknowledgment: ACK_ENTRY_001
3. [Processing entry signal for BUY_CALL...]
4. [TS→PYTHON] CHANGED KEY: 'TS_STRATEGY_STATE' = LONG
5. [TS→PYTHON] Strategy state changed to: LONG
```

## Where to Find Logs

### 1. VS Code Output Panel
- All `[TS→PYTHON]` and `[PYTHON→TS]` messages appear in the terminal
- Real-time updates as TradeStation sends data

### 2. Log Files
- Location: `logs/YYYY-MM-DD.log`
- Full detail with timestamps
- Persists across sessions

### 3. In-App Log Window
- Bottom of the main trading tab
- Shows `[TS] TS ADD:` and `[TS] TS CHANGE:` messages
- Truncated to 200 characters for readability

## Testing the Connection

1. **Start the Python application**
   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

2. **Enable TradeStation integration**
   - Click the "TradeStation" tab
   - Click "Enable TS" button
   - Look for connection banner in logs

3. **Run your TradeStation indicator**
   - Apply indicator to a chart
   - Send test signals (see TradeStation_Example_Indicator.txt)

4. **Monitor the logs**
   - Watch for `[TS→PYTHON]` messages
   - Verify data is being received
   - Check acknowledgments are sent

## Signal Format Reference

### Entry Signal
```python
Key: "ENTRY_001"
Value: {
    'action': 'BUY_CALL',      # or 'BUY_PUT', 'BUY_STRADDLE'
    'symbol': 'XSP',            # or 'SPX'
    'quantity': 1,
    'delta_target': 30          # Optional
}
```

### Exit Signal
```python
Key: "EXIT_001"
Value: {
    'action': 'CLOSE_ALL',      # or 'CLOSE_CALLS', 'CLOSE_PUTS', 'CLOSE_POSITION'
    'symbol': 'XSP',
    'contract_key': 'XSP_535_P_20251103'  # Optional
}
```

### Strategy State
```python
Key: "TS_STRATEGY_STATE"
Value: "FLAT"  # or "LONG", "SHORT"
```

## Troubleshooting

### No Messages Appearing
1. Check TradeStation indicator is running
2. Verify dictionary name matches: "IBKR_TRADER"
3. Ensure indicator has access to GlobalDictionary
4. Check Windows COM permissions

### Messages Appearing But Not Processing
1. Check signal format matches expected structure
2. Verify key naming convention (ENTRY_, EXIT_, etc.)
3. Check Python log for parsing errors
4. Review signal_id extraction logic

### Connection Established But No Data
1. Verify TradeStation is sending data (check Print log in TS)
2. Confirm COM pump is running (should see in logs)
3. Check for COM errors in Python logs
4. Restart both applications

## Log Message Prefixes

- `[TS→PYTHON]` = Data coming FROM TradeStation TO Python
- `[PYTHON→TS]` = Data going FROM Python TO TradeStation
- `[TS]` = TradeStation-related message (in GUI log)
- `[INFO]` = General information
- `[SUCCESS]` = Operation succeeded
- `[WARNING]` = Potential issue
- `[ERROR]` = Something went wrong

---

**Last Updated**: November 5, 2025  
**Feature**: Comprehensive TradeStation communication logging  
**Location**: Lines 803-854 in main.py (TradeStationManager class)
