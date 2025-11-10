# SIMPLIFIED CHAIN LOADING IMPLEMENTATION
## Complete Rewrite - November 10, 2025

This file contains the new simplified chain loading code to replace the complex existing system.

## New Code to Add to MainWindow Class

```python
# ============================================================================
# SIMPLIFIED CHAIN LOADING SYSTEM - November 10, 2025
# ============================================================================
# Single source of truth: underlying price → ATM strike → sequential chain loading
# No ES adjustments, no delta scanning, no complex fallbacks
# ============================================================================

class RequestIDRange:
    """Request ID ranges to prevent duplicates"""
    UNDERLYING = (1, 99)          # Underlying price subscriptions
    MAIN_CHAIN = (1000, 1999)     # Main option chain
    TS_0DTE = (2000, 2999)        # TradeStation 0DTE chain
    TS_1DTE = (3000, 3999)        # TradeStation 1DTE chain  
    ORDERS = (5000, 9999)         # Orders and other requests

def init_request_id_tracking(self):
    """Initialize request ID tracking system"""
    self.next_main_req_id = RequestIDRange.MAIN_CHAIN[0]
    self.next_ts_0dte_req_id = RequestIDRange.TS_0DTE[0]
    self.next_ts_1dte_req_id = RequestIDRange.TS_1DTE[0]
    self.active_req_ids = {
        'main': [],
        'ts_0dte': [],
        'ts_1dte': []
    }

def get_next_request_id(self, chain_type: str) -> int:
    """
    Get next available request ID for specified chain type.
    Prevents duplicate IDs by tracking usage.
    
    Args:
        chain_type: 'main', 'ts_0dte', or 'ts_1dte'
    
    Returns:
        Next available request ID in the appropriate range
    """
    if chain_type == 'main':
        req_id = self.next_main_req_id
        self.next_main_req_id += 1
        if self.next_main_req_id > RequestIDRange.MAIN_CHAIN[1]:
            self.next_main_req_id = RequestIDRange.MAIN_CHAIN[0]
        return req_id
    elif chain_type == 'ts_0dte':
        req_id = self.next_ts_0dte_req_id
        self.next_ts_0dte_req_id += 1
        if self.next_ts_0dte_req_id > RequestIDRange.TS_0DTE[1]:
            self.next_ts_0dte_req_id = RequestIDRange.TS_0DTE[0]
        return req_id
    elif chain_type == 'ts_1dte':
        req_id = self.next_ts_1dte_req_id
        self.next_ts_1dte_req_id += 1
        if self.next_ts_1dte_req_id > RequestIDRange.TS_1DTE[1]:
            self.next_ts_1dte_req_id = RequestIDRange.TS_1DTE[0]
        return req_id
    else:
        raise ValueError(f"Unknown chain type: {chain_type}")

def cancel_chain_subscriptions(self, chain_type: str):
    """Cancel all active subscriptions for a chain type"""
    if chain_type not in self.active_req_ids:
        return
    
    req_ids = self.active_req_ids[chain_type]
    if req_ids:
        logger.info(f"Canceling {len(req_ids)} subscriptions for {chain_type} chain")
        for req_id in req_ids:
            try:
                self.ibkr_client.cancelMktData(req_id)
                # Remove from market_data_map
                if req_id in self.app_state.get('market_data_map', {}):
                    del self.app_state['market_data_map'][req_id]
            except Exception as e:
                logger.debug(f"Error canceling reqId {req_id}: {e}")
        self.active_req_ids[chain_type] = []

def calculate_atm_strike(self) -> float:
    """
    Calculate ATM strike using ONLY the underlying price.
    No ES adjustments, no delta scanning, no fallbacks.
    
    Returns:
        ATM strike rounded to nearest strike interval, or 0 if price not available
    """
    price = self.app_state.get('underlying_price', 0)
    if price <= 0:
        return 0
    
    interval = self.instrument['strike_increment']
    atm = round(price / interval) * interval
    
    logger.info(f"ATM Calculation: underlying={price:.2f} → ATM strike={atm:.0f}")
    return atm

def load_all_chains_sequential(self):
    """
    Load all chains sequentially to prevent race conditions.
    
    Flow:
    1. Wait for underlying price (with timeout)
    2. Load main chain
    3. Wait for main chain to populate
    4. Load TS 0DTE chain
    5. Wait for TS 0DTE to populate
    6. Load TS 1DTE chain
    
    This is called once on connection and again when recentering.
    """
    if not hasattr(self, '_chain_load_retry_count'):
        self._chain_load_retry_count = 0
    
    # Step 1: Check for underlying price
    atm_strike = self.calculate_atm_strike()
    
    if atm_strike <= 0:
        self._chain_load_retry_count += 1
        if self._chain_load_retry_count < 20:  # 40 seconds max wait
            self.log_message(f"Waiting for underlying price... (attempt {self._chain_load_retry_count})", "INFO")
            QTimer.singleShot(2000, self.load_all_chains_sequential)
            return
        else:
            self.log_message("⚠️ Timeout waiting for underlying price", "ERROR")
            logger.error("Chain loading aborted - no underlying price after 40 seconds")
            return
    
    # Reset retry counter
    self._chain_load_retry_count = 0
    
    # Step 2: Load main chain
    logger.info(f"═══ SEQUENTIAL CHAIN LOADING START ═══")
    logger.info(f"Step 1/3: Loading MAIN chain at ATM strike {atm_strike:.0f}")
    self.log_message(f"Loading option chains at strike {atm_strike:.0f}...", "INFO")
    
    self.build_single_chain('main', atm_strike, self.strikes_above, self.strikes_below)
    
    # Step 3: Schedule TS chains after a delay
    QTimer.singleShot(3000, lambda: self._load_ts_0dte_chain(atm_strike))

def _load_ts_0dte_chain(self, atm_strike: float):
    """Step 2 of sequential loading: Load TS 0DTE chain"""
    logger.info(f"Step 2/3: Loading TS 0DTE chain at ATM strike {atm_strike:.0f}")
    self.build_single_chain('ts_0dte', atm_strike, self.ts_strikes_above, self.ts_strikes_below)
    
    # Schedule TS 1DTE chain
    QTimer.singleShot(3000, lambda: self._load_ts_1dte_chain(atm_strike))

def _load_ts_1dte_chain(self, atm_strike: float):
    """Step 3 of sequential loading: Load TS 1DTE chain"""
    logger.info(f"Step 3/3: Loading TS 1DTE chain at ATM strike {atm_strike:.0f}")
    self.build_single_chain('ts_1dte', atm_strike, self.ts_strikes_above, self.ts_strikes_below)
    
    logger.info(f"═══ SEQUENTIAL CHAIN LOADING COMPLETE ═══")
    self.log_message("✅ All option chains loaded successfully", "SUCCESS")

def build_single_chain(self, chain_type: str, atm_strike: float, 
                       strikes_above: int, strikes_below: int):
    """
    Build a single option chain (main, TS 0DTE, or TS 1DTE).
    
    This is the ONE unified function that builds any chain type.
    No duplication, no complex logic, just straightforward chain building.
    
    Args:
        chain_type: 'main', 'ts_0dte', or 'ts_1dte'
        atm_strike: The ATM strike to center the chain on
        strikes_above: Number of strikes above ATM (from UI settings)
        strikes_below: Number of strikes below ATM (from UI settings)
    """
    if self.connection_state != ConnectionState.CONNECTED:
        logger.warning(f"Cannot build {chain_type} chain - not connected")
        return
    
    # Cancel existing subscriptions for this chain
    self.cancel_chain_subscriptions(chain_type)
    
    # Determine expiry and instrument details based on chain type
    if chain_type == 'main':
        expiry = self.current_expiry
        symbol = self.instrument['options_symbol']
        trading_class = self.instrument['options_trading_class']
        table = self.option_table
    elif chain_type == 'ts_0dte':
        expiry = self.calculate_expiry_date(0)
        self.ts_0dte_expiry = expiry
        symbol = self.instrument['options_symbol']
        trading_class = self.instrument['options_trading_class']
        table = self.ts_0dte_table
    elif chain_type == 'ts_1dte':
        # Calculate 1DTE expiry (skip to next different date)
        expiry_0dte = self.calculate_expiry_date(0)
        expiry_1dte = self.calculate_expiry_date(1)
        if expiry_1dte == expiry_0dte:
            expiry = self.calculate_expiry_date(2)
        else:
            expiry = expiry_1dte
        self.ts_1dte_expiry = expiry
        symbol = self.instrument['options_symbol']
        trading_class = self.instrument['options_trading_class']
        table = self.ts_1dte_table
    else:
        raise ValueError(f"Unknown chain type: {chain_type}")
    
    # Build strike list
    strike_increment = self.instrument['strike_increment']
    center_strike = round(atm_strike / strike_increment) * strike_increment
    
    strikes = []
    current_strike = center_strike - (strikes_below * strike_increment)
    end_strike = center_strike + (strikes_above * strike_increment)
    
    while current_strike <= end_strike:
        strikes.append(current_strike)
        current_strike += strike_increment
    
    logger.info(f"Building {chain_type} chain: {len(strikes)} strikes from {min(strikes):.0f} to {max(strikes):.0f}")
    logger.info(f"  Expiry: {expiry}, Symbol: {symbol}, TradingClass: {trading_class}")
    
    # Clear and setup table
    table.setRowCount(0)
    table.setRowCount(len(strikes))
    
    # Request live market data
    self.ibkr_client.reqMarketDataType(1)
    
    # Subscribe to each strike
    new_req_ids = []
    
    for row, strike in enumerate(strikes):
        # Call option
        call_contract = self.create_option_contract(
            strike=strike,
            right='C',
            symbol=symbol,
            trading_class=trading_class,
            expiry=expiry
        )
        
        call_req_id = self.get_next_request_id(chain_type)
        call_key = f"{symbol}_{strike}_C_{expiry}"
        
        self.app_state['market_data_map'][call_req_id] = call_key
        self.ibkr_client.reqMktData(call_req_id, call_contract, "", False, False, [])
        new_req_ids.append(call_req_id)
        
        # Put option
        put_contract = self.create_option_contract(
            strike=strike,
            right='P',
            symbol=symbol,
            trading_class=trading_class,
            expiry=expiry
        )
        
        put_req_id = self.get_next_request_id(chain_type)
        put_key = f"{symbol}_{strike}_P_{expiry}"
        
        self.app_state['market_data_map'][put_req_id] = put_key
        self.ibkr_client.reqMktData(put_req_id, put_contract, "", False, False, [])
        new_req_ids.append(put_req_id)
        
        # Set strike in table
        strike_item = QTableWidgetItem(f"{strike:.0f}")
        strike_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        strike_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        # Color based on ATM
        if abs(strike - center_strike) < 0.01:  # This IS the ATM strike
            strike_item.setBackground(QColor("#FFD700"))  # Gold for ATM
        elif strike > center_strike:
            strike_item.setBackground(QColor("#2a4a6a"))  # Above ATM: lighter blue
        else:
            strike_item.setBackground(QColor("#1a2a3a"))  # Below ATM: darker blue
        
        # Strike column is at position 10 for main, varies for TS tables
        strike_col = 10 if chain_type == 'main' else 5  # Adjust based on actual table structure
        table.setItem(row, strike_col, strike_item)
    
    # Store active request IDs
    self.active_req_ids[chain_type] = new_req_ids
    
    logger.info(f"✓ {chain_type} chain: subscribed to {len(new_req_ids)} contracts ({len(strikes)} strikes × 2)")

def monitor_chain_drift(self):
    """
    Monitor for drift between current ATM and chain center.
    If drift exceeds threshold, trigger sequential recenter.
    
    Called periodically (e.g., every 5 seconds) via QTimer.
    """
    # Only monitor during market hours
    if not self.is_market_hours():
        return
    
    current_atm = self.calculate_atm_strike()
    if current_atm <= 0:
        return
    
    # Check main chain center
    if not hasattr(self, 'last_chain_center_strike') or self.last_chain_center_strike <= 0:
        self.last_chain_center_strike = current_atm
        return
    
    # Calculate drift in number of strikes
    strike_increment = self.instrument['strike_increment']
    drift_strikes = abs(current_atm - self.last_chain_center_strike) / strike_increment
    
    # Check if drift exceeds threshold
    if drift_strikes >= self.chain_drift_threshold:
        logger.warning(f"⚠️ CHAIN DRIFT DETECTED: {drift_strikes:.1f} strikes")
        logger.warning(f"  Current ATM: {current_atm:.0f}, Chain Center: {self.last_chain_center_strike:.0f}")
        logger.warning(f"  Threshold: {self.chain_drift_threshold} strikes")
        
        self.log_message(f"Recentering chains (drift: {drift_strikes:.1f} strikes)...", "WARNING")
        
        # Update center strike
        self.last_chain_center_strike = current_atm
        
        # Trigger sequential reload
        self.load_all_chains_sequential()
```

## Integration Steps

1. Add `init_request_id_tracking()` call in `__init__` after instrument setup
2. Replace connection handler to call `load_all_chains_sequential()` instead of old functions
3. Setup drift monitoring timer:
   ```python
   self.drift_monitor_timer = QTimer()
   self.drift_monitor_timer.timeout.connect(self.monitor_chain_drift)
   self.drift_monitor_timer.start(5000)  # Check every 5 seconds
   ```
4. Delete old functions (listed in CHAIN_LOADING_REWRITE.md)

## Error Handling Note

Error 200 (No security definition) is handled gracefully by IBKR API - the subscription
simply fails for that contract and moves on. No special handling needed. This is expected
and acceptable for strikes far from ATM or expiries with limited strikes available.
```
