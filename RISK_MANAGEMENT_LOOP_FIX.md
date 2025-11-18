# Risk Management Re-Triggering Loop Fix

## Problem Description

When a position hit profit target or stop loss, the system entered a re-triggering loop that:
- Placed multiple close orders for the same position (13 orders in 14 seconds)
- Created unwanted short positions
- Showed multiple popup dialogs
- Did not immediately stop checking the position

### Evidence from Logs (2025-11-18 14:25:58 - 14:26:10)

```
14:25:58 | WARNING | POSITION TARGET HIT: XSP_664.0_P_20251118 at 116.44% >= 60.0%
14:25:58 | INFO | Closing single position... PLACING ORDER #1889
14:25:59 | WARNING | POSITION TARGET HIT: XSP_664.0_P_20251118 at 118.67% >= 60.0%  ← SAME POSITION AGAIN
14:25:59 | INFO | Closing single position... PLACING ORDER #1890
14:26:00 | WARNING | POSITION TARGET HIT: XSP_664.0_P_20251118 at 118.67% >= 60.0%  ← AGAIN
14:26:00 | INFO | Closing single position... PLACING ORDER #1891
...
14:26:10 | INFO | PLACING ORDER #1901
```

**Result**: 13 close orders for ONE position in 14 seconds.

## Root Cause Analysis

### 1. Position Not Immediately Removed
```python
# In close_single_position()
self.place_order(contract_key, action, qty, mid_price)
# ↑ Order is placed but position stays in self.positions dict
# Position only gets removed when order fills (could be seconds later)
```

### 2. Timer Continues Checking
```python
# In check_profit_targets_and_stop_loss() - called every 1 second
for contract_key, pos in self.positions.items():
    if pnl_pct >= self.ts_position_profit_target_pct:
        self.close_single_position(contract_key, ...)  # Triggers AGAIN
```

### 3. No Protection Flag
Unlike session-level checks (which use `ts_profit_target_hit` flag), position-level checks had **no flag to prevent re-triggers**.

### 4. Lambda Capture Issue
```python
# WRONG - captures variable reference, not value
QTimer.singleShot(100, lambda: QMessageBox.information(
    f"Position: {contract_key}\n"  # ← contract_key could change!
))
```

## Solution Implemented

### 1. Added `is_closing` Flag
```python
if pnl_pct >= self.ts_position_profit_target_pct:
    # Mark position as closing to prevent re-triggers
    pos['is_closing'] = True  # ← NEW
    
    self.close_single_position(contract_key, ...)
```

### 2. Skip Closing Positions
```python
for contract_key, pos in self.positions.items():
    # Skip if position is already being closed
    if pos.get('is_closing', False):  # ← NEW
        continue
    
    # Check target/stop...
```

### 3. Fixed Lambda Capture
```python
# Capture values BEFORE they change
_contract_key = contract_key
_pnl_pct = pnl_pct
_pnl = pnl

# Use default arguments to capture values
QTimer.singleShot(100, lambda key=_contract_key, pct=_pnl_pct, p=_pnl: 
    QMessageBox.information(
        self,
        "💰 Position Profit Target Hit!",
        f"Position: {key}\n"  # ← Uses captured value
        f"Profit: {pct:+.2f}%\n"
        f"P&L: ${p:+,.2f}\n\n"
        f"Position has been closed."
    )
)
```

## Changes Made

### File: `main.py`

#### 1. Position Profit Target Check (Lines 11538-11580)
- Added `is_closing` flag check at start of loop
- Set `is_closing = True` when target hit
- Captured values before close for popup
- Fixed lambda with default arguments

#### 2. Position Stop Loss Check (Lines 11582-11630)
- Added `is_closing` flag check at start of loop
- Set `is_closing = True` when stop hit
- Captured values before close for popup
- Fixed lambda with default arguments

### Session-Level Checks (No Changes Needed)
Session profit/stop already had `ts_profit_target_hit` flag protection in `handle_profit_target_hit()`.

## Testing Verification

### Before Fix:
- Position hits target → 13 orders in 14 seconds
- User sees multiple popups
- Creates short position (unwanted)

### After Fix:
- Position hits target → 1 order placed
- Position marked `is_closing = True`
- Subsequent checks skip the position
- Single popup shows correct values
- No short position created

## Lifecycle Flow

```
Timer calls check_profit_targets_and_stop_loss()
    ↓
Loop through positions
    ↓
Position XYZ hits target
    ↓
pos['is_closing'] = True  ← PREVENTS RE-TRIGGERS
    ↓
close_single_position(XYZ)
    ↓
place_order() for exit
    ↓
QTimer.singleShot(100ms, show_popup)
    ↓
return (exit function)
    ↓
[1 second later]
    ↓
Timer calls check_profit_targets_and_stop_loss() again
    ↓
Loop through positions
    ↓
Position XYZ found, but is_closing=True → SKIP
    ↓
No re-trigger! ✅
    ↓
[Later when order fills]
    ↓
on_position_update() removes position from dict
```

## Key Principles

1. **Mark Before Action**: Set `is_closing = True` BEFORE calling `close_single_position()`
2. **Check Flag First**: Always check `is_closing` flag before processing position
3. **Capture Values**: Capture values in local variables before async operations
4. **Proper Lambda**: Use default arguments in lambda to capture values, not references

## Related Components

- `check_profit_targets_and_stop_loss()`: Position-level checks (FIXED)
- `handle_profit_target_hit()`: Session-level handler (already had flag)
- `close_single_position()`: Actual order placement
- `on_position_update()`: Final cleanup when order fills

## Commit
- **Commit ID**: c4a5aa0
- **Date**: 2025-11-18
- **Message**: "FIX CRITICAL: Prevent position risk management re-triggering loop"
