# Integration Guide: TradeStation to Interactive Brokers

This guide explains how to integrate the TradeStation GlobalDictionary interface with your custom Interactive Brokers API application.

## Architecture Overview

```
TradeStation 10 (EasyLanguage)
    ↓ (COM via GlobalDictionary)
Python GlobalDictionary Module
    ↓ (Your Integration Code)
Your IB Official API Application
    ↓ (Official IB API)
Interactive Brokers TWS/Gateway
```

## Integration Patterns

### Pattern 1: Event-Driven Signal Processing

TradeStation signals trigger IB trades through event handlers:

```python
import GlobalDictionary
import pythoncom
import time
# Your IB API imports here
# from ibapi.client import EClient
# from ibapi.wrapper import EWrapper

class TradingBridge:
    def __init__(self, ib_client):
        self.ib_client = ib_client
        self.gd = GlobalDictionary.create(
            "TRADING_SIGNALS",
            add=self.on_signal_add,
            change=self.on_signal_change
        )
    
    def on_signal_add(self, gd, key, value, size):
        """Handle new trading signals from TradeStation"""
        if key.startswith("ORDER_"):
            self.process_trade_signal(key, value)
    
    def on_signal_change(self, gd, key, value, size):
        """Handle signal updates from TradeStation"""
        if key.startswith("ORDER_"):
            self.process_trade_signal(key, value)
    
    def process_trade_signal(self, signal_key, signal_data):
        """Convert TradeStation signal to IB order"""
        # Extract signal parameters
        # signal_data could be dict: {'symbol': 'NQ', 'action': 'BUY', 'qty': 1, 'type': 'MKT'}
        
        # Place order through IB API
        # self.ib_client.placeOrder(orderId, contract, order)
        
        # Optionally send confirmation back to TradeStation
        self.gd[f"STATUS_{signal_key}"] = "SUBMITTED"
    
    def run(self):
        """Main event loop pumping both COM and IB messages"""
        while True:
            # Pump TradeStation COM events
            pythoncom.PumpWaitingMessages()
            
            # Process IB API messages (your existing event loop)
            # self.ib_client.run()  # or your message processing
            
            time.sleep(0.001)  # Minimal sleep to prevent CPU spinning

# Usage:
# ib_client = YourIBClient()  # Your existing IB API client
# bridge = TradingBridge(ib_client)
# bridge.run()
```

### Pattern 2: Shared State Dictionary

Use GlobalDictionary for bidirectional communication:

```python
# TradeStation writes signals, reads order status
# Python reads signals, writes order status and position info

def setup_shared_state(ib_client):
    gd = GlobalDictionary.create("TRADING_STATE")
    
    # Initialize state
    gd.clear()
    gd["IB_CONNECTION"] = "CONNECTED"
    gd["POSITIONS"] = {}  # Will be updated with current IB positions
    gd["ACCOUNT_VALUE"] = 0.0
    
    return gd

def update_positions_from_ib(gd, positions_dict):
    """Push IB positions to TradeStation"""
    gd["POSITIONS"] = positions_dict
    gd["LAST_UPDATE"] = time.time()

def monitor_ts_signals(gd):
    """Check for new signals from TradeStation"""
    keys = gd.keys
    for key in keys:
        if key.startswith("SIGNAL_") and key.endswith("_NEW"):
            signal = gd[key]
            # Process signal...
            gd.remove(key)  # Mark as processed
```

### Pattern 3: Signal Queue with Acknowledgment

Reliable signal processing with confirmation:

```python
class SignalQueue:
    def __init__(self, gd_name="SIGNAL_QUEUE"):
        self.gd = GlobalDictionary.create(
            gd_name,
            add=self.on_signal_received
        )
        self.pending_signals = []
    
    def on_signal_received(self, gd, key, value, size):
        if key.startswith("SIG_"):
            signal_id = key.replace("SIG_", "")
            self.pending_signals.append({
                'id': signal_id,
                'data': value,
                'timestamp': time.time()
            })
            # Acknowledge receipt
            gd[f"ACK_{signal_id}"] = True
    
    def process_next_signal(self, ib_client):
        if self.pending_signals:
            signal = self.pending_signals.pop(0)
            try:
                # Execute trade through IB
                result = self.execute_ib_order(ib_client, signal['data'])
                # Report success
                self.gd[f"RESULT_{signal['id']}"] = {
                    'status': 'SUCCESS',
                    'order_id': result['order_id'],
                    'timestamp': time.time()
                }
            except Exception as e:
                # Report error
                self.gd[f"RESULT_{signal['id']}"] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
```

## Data Structure Guidelines

### TradeStation Signal Format (Recommended)

```python
# Simple order signal
order_signal = {
    'symbol': 'ES',           # Futures symbol
    'action': 'BUY',          # BUY or SELL
    'quantity': 1,
    'order_type': 'MKT',      # MKT, LMT, STP, etc.
    'limit_price': None,      # For limit orders
    'stop_price': None,       # For stop orders
    'timestamp': 1730000000,  # TS timestamp
    'strategy_id': 'TREND_1'  # Identify source strategy
}

# TradeStation writes:
GD["ORDER_12345"] = order_signal

# Python reads and processes:
signal = GD["ORDER_12345"]
# ... execute via IB API ...
GD["STATUS_12345"] = "FILLED"
GD["FILL_PRICE_12345"] = 6851.25
```

### Position Update Format

```python
# Python writes current positions for TradeStation monitoring
positions = {
    'ES': {'position': 2, 'avg_price': 6850.50},
    'NQ': {'position': -1, 'avg_price': 21450.00}
}
GD["CURRENT_POSITIONS"] = positions
GD["ACCOUNT_EQUITY"] = 125430.50
```

## Integration Checklist

- [ ] Copy `GlobalDictionary.py` to your IB API project
- [ ] Ensure TradeStation 10 is running with `_PYTHON GLOBALDICTIONARY.ELD` imported
- [ ] Decide on dictionary naming convention (e.g., "TS_TO_IB", "IB_TO_TS")
- [ ] Define signal data structure (use dicts for complex signals)
- [ ] Test COM connection with `test_connectivity.py`
- [ ] Implement event handlers for TradeStation signals
- [ ] Add GlobalDictionary event loop to your IB message processing
- [ ] Handle COM exceptions (TradeStation disconnect/restart)
- [ ] Add logging for signal processing and order execution
- [ ] Test with paper trading account first
- [ ] Implement signal acknowledgment/confirmation mechanism

## Threading Considerations

The IB API typically uses threading. Options:

1. **Single-threaded with message pumping**: Pump both COM and IB messages in one loop
2. **Separate thread for GlobalDictionary**: Run COM message pump in dedicated thread
3. **Queue-based**: Use `queue.Queue` to pass signals between COM thread and IB thread

Example multi-threaded approach:

```python
import threading
import queue

signal_queue = queue.Queue()

def gd_thread():
    """Dedicated thread for TradeStation COM events"""
    def on_signal(gd, key, value, size):
        signal_queue.put({'key': key, 'value': value})
    
    gd = GlobalDictionary.create("SIGNALS", add=on_signal)
    while True:
        pythoncom.PumpWaitingMessages()
        time.sleep(0.001)

def ib_thread():
    """Your existing IB API thread"""
    while True:
        # Check for signals from TradeStation
        try:
            signal = signal_queue.get_nowait()
            process_signal(signal)
        except queue.Empty:
            pass
        
        # Your existing IB message processing
        # ...

# Start both threads
threading.Thread(target=gd_thread, daemon=True).start()
threading.Thread(target=ib_thread, daemon=True).start()
```

## Error Handling

```python
try:
    gd = GlobalDictionary.create("TRADING")
except Exception as e:
    # TradeStation not running or ELD not loaded
    print(f"TradeStation connection failed: {e}")
    # Fall back to manual trading or exit

# Monitor connection health
def check_ts_connection(gd):
    try:
        gd["HEARTBEAT"] = time.time()
        return True
    except:
        return False
```

## Testing Workflow

1. Run `test_connectivity.py` to verify TradeStation connection
2. Run `Demo.py` to see live events from TradeStation
3. Create a test script that reads signals without executing trades
4. Add IB paper trading execution
5. Test with live TradeStation signals
6. Monitor for several hours/days before production use

## Next Steps

1. Review your existing IB API application architecture
2. Identify where to integrate GlobalDictionary event handling
3. Design your signal data structure based on your trading strategies
4. Implement skeleton integration with logging (no actual trades)
5. Test signal flow: TradeStation → Python → Logs
6. Add IB paper trading execution
7. Gradually move to live trading with position limits
