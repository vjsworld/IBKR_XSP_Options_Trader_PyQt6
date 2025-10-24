# Dual-Instrument Refactoring Plan

## Overview
Refactor the application from hardcoded SPX references to support multiple instruments (SPX, XSP) through configuration.

## Key Changes Required

### 1. Rename All SPX-Specific Variables to Generic Names

**Current → New:**
- `spx_price` → `underlying_price`
- `spx_req_id` → `underlying_req_id`
- `spx_price_label` → `underlying_price_label`
- `spx_price_updated` (signal) → `underlying_price_updated`
- `subscribe_spx_price()` → `subscribe_underlying_price()`
- `update_spx_display()` → `update_underlying_display()`

### 2. Add Instrument Configuration to MainWindow

```python
def __init__(self):
    super().__init__()
    
    # Load instrument from settings (default: SPX)
    self.current_instrument = 'SPX'  # From settings.json or UI selector
    self.instrument = INSTRUMENT_CONFIG[self.current_instrument]
    
    # Extract for easy access
    self.underlying_symbol = self.instrument['underlying_symbol']
    self.options_symbol = self.instrument['options_symbol']
    self.trading_class = self.instrument['options_trading_class']
```

### 3. Update Window Title

```python
self.setWindowTitle(f"{self.instrument['name']} 0DTE Options Trader - PyQt6 Professional Edition")
```

### 4. Update UI Labels

```python
title_label = QLabel(f"{self.instrument['name']} Option Chain")
self.underlying_price_label = QLabel(f"{self.instrument['name']}: Loading...")
```

### 5. Genericize Contract Creation

```python
def subscribe_underlying_price(self):
    """Subscribe to underlying price (SPX, XSP, or any configured instrument)"""
    underlying_contract = Contract()
    underlying_contract.symbol = self.underlying_symbol
    underlying_contract.secType = self.instrument['underlying_type']
    underlying_contract.currency = "USD"
    underlying_contract.exchange = self.instrument['underlying_exchange']
    
    req_id = 1
    self.app_state['underlying_req_id'] = req_id
    self.ibkr_client.reqMktData(req_id, underlying_contract, "", False, False, [])
    logger.info(f"Subscribed to {self.underlying_symbol} underlying price")
```

### 6. Update Signals

In `IBKRSignals` class:
```python
# Market data signals
underlying_price_updated = pyqtSignal(float)  # Renamed from spx_price_updated
```

In `IBKRWrapper`:
```python
def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib):
    """Receives real-time price updates"""
    # Underlying price (SPX, XSP, etc.)
    if reqId == self.app.get('underlying_req_id'):
        if tickType == 4:  # LAST price
            self.app['underlying_price'] = price
            self.signals.underlying_price_updated.emit(price)
        return
```

### 7. Update App State Dictionary

```python
self.app_state = {
    'next_order_id': 1,
    'underlying_price': 0.0,        # Renamed from spx_price
    'underlying_req_id': None,      # Renamed from spx_req_id
    'data_server_ok': False,
    'managed_accounts': [],
    'account': '',
    'market_data_map': {},
    'historical_data_requests': {},
}
```

### 8. Update Signal Connections

```python
self.signals.underlying_price_updated.connect(self.update_underlying_display)
```

### 9. Update Display Methods

```python
@pyqtSlot(float)
def update_underlying_display(self, price: float):
    """Update underlying price display"""
    self.app_state['underlying_price'] = price
    self.underlying_price_label.setText(f"{self.instrument['name']}: {price:.2f}")
```

### 10. Update Settings UI

```python
strategy_layout.addRow(f"Strikes Above {self.instrument['name']}:", self.strikes_above_edit)
strategy_layout.addRow(f"Strikes Below {self.instrument['name']}:", self.strikes_below_edit)
```

### 11. Update Option Chain Generation

```python
def build_option_chain(self):
    """Build option chain around current underlying price"""
    if self.app_state['underlying_price'] == 0:
        self.log_message(f"Waiting for {self.underlying_symbol} price...", "INFO")
        return
    
    underlying_price = self.app_state['underlying_price']
    logger.info(f"Building option chain around {self.underlying_symbol} price: ${underlying_price:.2f}")
```

### 12. Add Instrument Selector to Settings Tab (Future Enhancement)

```python
# Instrument selection
instrument_group = QGroupBox("Trading Instrument")
instrument_layout = QFormLayout()

self.instrument_combo = QComboBox()
self.instrument_combo.addItems(list(INSTRUMENT_CONFIG.keys()))
self.instrument_combo.setCurrentText(self.current_instrument)
self.instrument_combo.currentTextChanged.connect(self.change_instrument)

instrument_layout.addRow("Select Instrument:", self.instrument_combo)
instrument_group.setLayout(instrument_layout)
```

## Benefits

1. ✅ **Symbol-Agnostic Code**: Works with any configured instrument
2. ✅ **Easy to Extend**: Add new instruments by updating `INSTRUMENT_CONFIG`
3. ✅ **Maintainable**: No hardcoded symbols scattered throughout codebase
4. ✅ **User-Friendly**: Clear indication of which instrument is being traded
5. ✅ **Flexible**: Switch between SPX and XSP (or future instruments) via settings

## Testing Checklist

- [ ] SPX mode works (default)
- [ ] XSP mode works (after switching instrument)
- [ ] Window title shows correct instrument
- [ ] Price display shows correct symbol and price
- [ ] Option chain builds correctly for each instrument
- [ ] Strike increments follow instrument config (SPX: $5, XSP: $1)
- [ ] Tick sizes apply correctly per instrument
- [ ] Settings save/load instrument selection
- [ ] Logs reference correct symbols

## Implementation Status

- [x] Added `INSTRUMENT_CONFIG` to main.py
- [x] Documented architecture in copilot-instructions.md
- [ ] Refactor MainWindow.__init__()
- [ ] Rename all spx_* variables to generic names
- [ ] Update all UI labels and titles
- [ ] Update signal definitions
- [ ] Update IBKRWrapper callbacks
- [ ] Test with SPX
- [ ] Test with XSP
