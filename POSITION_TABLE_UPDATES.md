# Position Table Updates - Feature Parity with Tkinter

## Summary
Updated the position table to exactly match the Tkinter version functionality with enhanced features.

## Changes Made

### 1. Position Table Structure ✅
- **Already Implemented**: 9 columns (Contract, Qty, Entry, Current, P&L, P&L%, EntryTime, TimeSpan, Close)
- EntryTime displays in `HH:MM:SS` format
- TimeSpan displays elapsed time in `HH:MM:SS` format
- Close button styled with red background (#cc0000), white text

### 2. Close Button Functionality ✅ (UPDATED)
**Location**: `on_position_cell_clicked()` (line ~2913)

**New Features**:
- ✅ **Protection Check #1**: Validates position quantity is not zero before allowing close
- ✅ **Protection Check #2**: Detects pending exit orders and prevents duplicate close orders
- ✅ **Mid-Price Chasing**: Places exit order at mid-price with chasing enabled (was market order)
- ✅ **Better Confirmations**: Shows current P&L in confirmation dialog
- ✅ **Detailed Logging**: Logs all close actions with separator bars for visibility

**Behavior**:
- Checks if position size is 0 → Shows warning, cancels operation
- Checks for pending exit orders → Shows warning with order IDs, cancels operation
- Confirms with user → Shows position, quantity, and current P&L
- Places exit order at **mid-price** with **chasing enabled** (not market order)
- Logs all actions clearly for debugging

### 3. Position Persistence ✅ (NEW FEATURE)
**Goal**: Preserve `entryTime` across app restarts

**New Methods**:
- `save_positions()` - Saves positions to `positions.json` with entryTime as ISO string
- `load_positions()` - Loads positions on startup, parses ISO datetime back to datetime object
- `merge_saved_positions()` - Merges saved entryTime with IBKR position when callback arrives

**Integration Points**:
1. **Startup**: `load_positions()` called after `load_settings()` (line ~620)
2. **Auto-Save**: Timer saves every 60 seconds (line ~629)
3. **Position Callback**: `merge_saved_positions()` called in `on_position_update()` (line ~1509)
4. **App Close**: `save_positions()` called in `closeEvent()` (line ~3704)

**Data Format** (`positions.json`):
```json
{
  "SPX_6000.0_C_20250117": {
    "position": 2,
    "avgCost": 25.50,
    "entryTime": "2025-01-27T14:30:45.123456"
  }
}
```

### 4. Display Updates ✅ (ALREADY WORKING)
**Location**: `update_positions_display()` (line ~2852)

- Updates every 1 second via timer
- Calculates TimeSpan in real-time
- Formats EntryTime as `HH:MM:SS`
- Formats TimeSpan as `HH:MM:SS` (hours:minutes:seconds)
- P&L colored: green for profit, red for loss
- Close button: red background, white text

## How It Works

### Entry Time Tracking Flow
```
1. Position Created by IBKR
   ↓
2. on_position_update() receives callback
   ↓
3. Sets entryTime = datetime.now() (if new position)
   ↓
4. Calls merge_saved_positions() to restore old entryTime if available
   ↓
5. Position displayed with preserved entryTime
   ↓
6. Auto-save timer saves to positions.json every 60 seconds
   ↓
7. App closes → save_positions() called one final time
   ↓
8. App restarts → load_positions() reads JSON
   ↓
9. IBKR sends position → merge restores original entryTime
```

### Close Button Flow (Enhanced)
```
1. User clicks Close button (column 8)
   ↓
2. Check: Is position size zero? → Abort with warning
   ↓
3. Check: Are there pending exit orders? → Abort with warning
   ↓
4. Show confirmation: Position, Qty, P&L
   ↓
5. User confirms → Calculate mid-price
   ↓
6. Place exit order with mid-price chasing enabled
   ↓
7. Order chases mid-price every 10 seconds (gives in)
   ↓
8. Order fills → Remove from manual_orders (stops chasing)
```

## Differences from Tkinter

### Same as Tkinter ✅
- 9 columns with EntryTime and TimeSpan
- Close button styling (red background)
- Mid-price chasing for exit orders
- Protection checks (zero position, duplicate orders)
- Confirmation dialog before close

### Enhancements Beyond Tkinter 🚀
- **Position Persistence**: Tkinter does NOT save positions to file
  - PyQt6 version saves `entryTime` across app restarts
  - Allows tracking true position holding time (even after app restart)
  - Auto-saves every 60 seconds + on close
- **Better Logging**: Detailed logs with separator bars
- **Real-time Updates**: 1-second timer for TimeSpan updates

## Testing Checklist

- [ ] EntryTime displays correctly when position opens
- [ ] TimeSpan increments every second
- [ ] Close button shows red background
- [ ] Clicking Close shows confirmation with P&L
- [ ] Close button validates position is not zero
- [ ] Close button detects duplicate exit orders
- [ ] Exit order chases mid-price (shows "Chasing Mid" / "Giving In x1")
- [ ] Position saves to `positions.json` every 60 seconds
- [ ] Position saves on app close
- [ ] EntryTime preserved after app restart (if position still exists in IBKR)
- [ ] TimeSpan continues from original entryTime after restart

## Files Modified
- `main.py`:
  - Updated `on_position_cell_clicked()` - Enhanced Close button logic
  - Added `save_positions()` - Position persistence
  - Added `load_positions()` - Load saved positions
  - Added `merge_saved_positions()` - Merge entryTime on IBKR callback
  - Updated `__init__()` - Initialize `saved_positions` dict
  - Updated startup - Call `load_positions()` and start auto-save timer
  - Updated `on_position_update()` - Call `merge_saved_positions()`
  - Updated `closeEvent()` - Call `save_positions()` before close

## Files Created
- `positions.json` - Auto-created on first save, stores position entryTime
