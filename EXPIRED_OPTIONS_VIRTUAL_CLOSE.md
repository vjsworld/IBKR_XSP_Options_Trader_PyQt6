# Expired Options Virtual Close Feature

## Overview
This feature automatically detects expired options that are still held 10+ minutes after expiration and prompts the user to virtually close them for proper P&L logging.

## Problem Statement
When 0DTE options expire, they often remain in the IBKR positions list temporarily. If these expired options have no value ($0), they represent a total loss, but if they still have some value, the P&L should be calculated from that exit price. Without proper tracking, these positions:
- Clutter the positions grid
- Lack proper P&L logging
- May trigger false risk management alerts
- Don't contribute to realized P&L calculations

## Solution Architecture

### Detection Logic
- Timer-based check runs every second via `check_expired_positions()`
- Instrument-specific expiration times:
  - **SPX/XSP options**: Expire at 3:00 PM CT → Check starts at 3:10 PM CT
  - **ES/MES options**: Expire at 4:00 PM CT → Check starts at 4:10 PM CT
- Continues checking until midnight CT
- Only checks contracts that expired **today** (compares system clock date with contract expiry date)
- Detects options held **10+ minutes** after expiration time

### User Interaction
- **One prompt per day**: `expired_positions_prompt_shown` flag prevents multiple popups
- **QMessageBox dialog** shows:
  - List of expired positions with quantities and current values
  - P&L calculation rules explanation
  - Yes/No choice with default to Yes
- User can decline to keep positions visible

### Virtual Close Process
1. **P&L Calculation**:
   - If `current_value ≤ 0`: **Total loss** → `pnl = -entry_cost`, `pnl_pct = -100%`
   - If `current_value > 0`: **Calculated P&L**:
     - LONG: `pnl = exit_value - entry_cost`
     - SHORT: `pnl = entry_cost - exit_value`

2. **CSV Logging**:
   - Uses `log_trade_to_csv()` with `action='VIRTUAL_CLOSE'`
   - Records: contract, quantity, entry cost, exit value, P&L, P&L%
   - Preserves entry time for accurate time-in-trade tracking

3. **Position Cleanup**:
   - Adds `contract_key` to `virtually_closed_positions` set
   - Adds `contract_key` to `ignored_expired_contracts` set
   - Removes from `self.positions` dict immediately
   - Cleans up `_position_source_map`
   - Updates positions display

4. **Grid Filtering**:
   - `update_positions_display()` filters out contracts in `ignored_expired_contracts`
   - Risk management checks (profit target, stop loss) skip ignored contracts
   - Prevents re-triggering on expired positions

## Implementation Details

### Instance Variables (lines 3187-3194)
```python
self.expired_positions_prompt_shown = False  # One prompt per day
self.virtually_closed_positions = set()      # Tracks virtually closed contracts
self.ignored_expired_contracts = set()       # Contracts to hide from grid
```

### Key Functions

#### `check_expired_positions()` (lines 11515-11593)
- **Called by**: `check_profit_targets_and_stop_loss()` timer (every second)
- **Purpose**: Detect expired options held 10+ minutes past expiration
- **Logic**:
  1. Check until midnight CT (24:00), then stop
  2. Parse contract_key expiry date (format: YYYYMMDD)
  3. Determine expiration time based on `self.selected_instrument`:
     - ES/MES: `expiry_date + 16:00 CT` (4:00 PM)
     - SPX/XSP: `expiry_date + 15:00 CT` (3:00 PM)
  4. Compare expiry date with today's date (system clock) - **only process if expired today**
  5. Check if `now > expiry_time + 10 minutes`
  6. Skip if in `virtually_closed_positions` or `ignored_expired_contracts`
  7. Get current market value from `self.market_data`
  8. Call `prompt_virtual_close_expired()` if positions found

#### `prompt_virtual_close_expired()` (lines 11579-11622)
- **Called by**: `check_expired_positions()`
- **Purpose**: Show user dialog asking about virtual close
- **Dialog Contents**:
  - "Expired Options Detected" title
  - List of positions: `{contract_key}: Qty {qty}, Current Value: ${value}`
  - P&L rules explanation
  - Yes/No buttons (default: Yes)
- **Actions**:
  - Set `expired_positions_prompt_shown = True` (one prompt per day)
  - Call `virtual_close_expired_positions()` on Yes

#### `virtual_close_expired_positions()` (lines 11624-11710)
- **Called by**: User clicking Yes in popup
- **Purpose**: Execute virtual close, calculate P&L, log to CSV
- **P&L Calculation**:
  ```python
  multiplier = int(self.instrument['multiplier'])  # 100 for SPX/XSP, 50 for ES
  entry_cost = avg_cost * abs(qty) * multiplier
  exit_value = current_price * abs(qty) * multiplier
  
  if current_price <= 0:
      pnl = -entry_cost
      pnl_pct = -100.0
  else:
      if qty > 0:  # LONG
          pnl = exit_value - entry_cost
      else:  # SHORT
          pnl = entry_cost - exit_value
      pnl_pct = (pnl / entry_cost * 100) if entry_cost > 0 else 0
  ```
- **CSV Logging**:
  ```python
  self.log_trade_to_csv(
      contract_key=contract_key,
      action='VIRTUAL_CLOSE',
      quantity=abs(qty),
      entry_time=entry_time,
      exit_time=now,
      entry_cost=avg_cost,
      exit_price=current_price,
      pnl=pnl,
      pnl_percent=pnl_pct,
      is_automated=is_automated
  )
  ```
- **Position Removal**:
  - Add to `virtually_closed_positions` and `ignored_expired_contracts` sets
  - Delete from `self.positions` dict
  - Remove from `_position_source_map`
  - Call `update_positions_display()`

### Grid Filtering (line 11405-11408)
```python
# Filter out virtually closed expired positions
visible_positions = {k: v for k, v in self.positions.items() 
                   if k not in self.ignored_expired_contracts}
```

### Risk Management Integration
- **Profit Target Check** (line 11751-11754): Skip `ignored_expired_contracts`
- **Stop Loss Check** (line 11807-11810): Skip `ignored_expired_contracts`
- Prevents false risk triggers on expired positions

### Daily Reset (line 12586-12588)
```python
# Reset expired positions prompt for new trading day
self.expired_positions_prompt_shown = False
```
- Resets on date change via existing `check_for_new_day_or_4pm()` logic
- Allows one prompt per trading day

## Edge Cases Handled

1. **No Market Data Available**:
   - If no bid/ask in `self.market_data`, treats as $0 value (total loss)
   
2. **Position Updates After Virtual Close**:
   - Contract remains in `ignored_expired_contracts` set
   - Grid filtering prevents reappearance
   - Risk checks skip the contract
   
3. **TWS Removes Position**:
   - `on_position_update()` with `qty=0` cleans up position
   - Sets will persist until app restart (no harm)
   
4. **Multiple Expired Positions**:
   - Single prompt lists all expired positions
   - Batch processes all virtual closes
   
5. **User Declines Virtual Close**:
   - Prompt flag still set (won't ask again today)
   - Positions remain visible and tracked normally
   
5. **After-Hours Operation**:
   - Check runs continuously from expiry+10min until midnight CT
   - SPX/XSP: 3:10 PM - 11:59 PM CT window
   - ES/MES: 4:10 PM - 11:59 PM CT window
   - Only processes contracts expired TODAY (prevents stale contract triggers)
   
6. **Next Day Handling**:
   - After midnight, check stops until next expiration
   - Expired contracts from previous days are ignored (date comparison filter)

## Testing Scenarios

### Test 1: Zero Value Expired Option
1. Hold 0DTE option to expiration
2. Wait 10+ minutes after 3:00 PM CT
3. Verify popup appears with correct position
4. Accept virtual close
5. Verify P&L = -100%, logged to CSV
6. Verify position removed from grid

### Test 2: Non-Zero Value Expired Option
1. Hold 0DTE option past expiration with remaining value
2. Wait 10+ minutes after 3:00 PM CT
3. Verify popup shows current market value
4. Accept virtual close
5. Verify P&L calculated from exit value
6. Verify CSV entry shows correct exit price

### Test 3: Multiple Expired Positions
1. Hold multiple expired options 10+ minutes
2. Verify single popup lists all positions
3. Accept virtual close
4. Verify all positions logged and removed

### Test 4: Decline Virtual Close
1. Wait for expired options prompt
2. Click "No"
3. Verify positions remain visible
4. Verify no second prompt appears same day

### Test 5: New Day Reset
1. Decline virtual close on Day 1
2. Let app run to next trading day
3. Verify prompt appears again if positions still held

### Test 6: Risk Management Integration
1. Have expired position with profit target enabled
2. Virtually close the position
3. Verify profit target check doesn't trigger on ignored contract

## Files Modified
- **main.py**: All implementation (lines 3187-3194, 11405-11408, 11509-11710, 11751-11754, 11807-11810, 12586-12588)

## Related Features
- Position Risk Management (profit target, stop loss)
- CSV Trade Logging
- Position Display Grid
- Timer-based Monitoring System

## Future Enhancements
1. Auto-virtual-close after 30 minutes (no prompt)
2. Settings option to disable virtual close feature
3. Notification when TWS removes positions from ignored set
4. Historical report of virtually closed positions
5. Option to manually trigger virtual close via context menu
