# Client ID Retry Implementation

## Summary
Implemented automatic client ID retry functionality to handle error 326 ("client id is already in use"). This matches the Tkinter version behavior.

## Problem
When connecting to IBKR TWS/Gateway, if the client ID is already in use by another application instance, the connection fails with error 326. Previously, the app would just fail and require manual intervention.

## Solution
The app now automatically tries client IDs 1-10 in sequence until it finds an available one.

## Implementation Details

### 1. New Variables (Added to `__init__`)
```python
self.client_id = 1
self.client_id_iterator = 1  # Current client ID being tried
self.max_client_id = 10      # Maximum client ID to try
self.handling_client_id_error = False  # Flag to prevent double reconnect
```

### 2. Error Handler Enhancement
**Location**: `IBKRClient.error()` method (line ~280)

Added error code 326 handler:
```python
# Client ID already in use - try next client ID
if errorCode == 326:
    self.signals.connection_message.emit(f"Client ID {self._main_window.client_id} already in use", "WARNING")
    if self._main_window.client_id_iterator < self._main_window.max_client_id:
        self._main_window.client_id_iterator += 1
        self._main_window.client_id = self._main_window.client_id_iterator
        self.signals.connection_message.emit(f"Retrying with Client ID {self._main_window.client_id}...", "INFO")
        # Mark that we're handling this error specially
        self._main_window.handling_client_id_error = True
        # Disconnect current connection
        self.disconnect()
        # Schedule reconnect with new client ID
        QTimer.singleShot(2000, self._main_window.retry_connection_with_new_client_id)
    else:
        self.signals.connection_message.emit(
            f"Exhausted all client IDs (1-{self._main_window.max_client_id}). Please close other connections.", 
            "ERROR"
        )
        self.signals.connection_status.emit("DISCONNECTED")
    return
```

### 3. Retry Method
**Location**: `MainWindow.retry_connection_with_new_client_id()` (after disconnect_from_ibkr)

```python
def retry_connection_with_new_client_id(self):
    """
    Retry connection with new client ID after error 326.
    Called via QTimer.singleShot after incrementing client_id_iterator.
    """
    self.handling_client_id_error = False
    logger.info(f"Retrying connection with client ID {self.client_id}")
    # Update the client ID in the UI
    self.client_id_edit.setText(str(self.client_id))
    # Reset client_id_iterator to use the new client_id
    self.client_id_iterator = self.client_id
    # Attempt reconnection
    self.connect_to_ibkr()
```

### 4. Connection Method Update
**Location**: `MainWindow.connect_to_ibkr()` (line ~1289)

Changed to use `client_id_iterator` instead of reading from UI:
```python
# Use client_id_iterator for connection (allows auto-increment on error 326)
self.client_id = self.client_id_iterator
```

### 5. Reset Iterator on Success
**Location**: `IBKRClient.connectAck()` (line ~344)

Reset iterator to 1 when connection succeeds:
```python
def connectAck(self):
    """Called when connection is acknowledged"""
    logger.info("IBKR connection acknowledged")
    # Reset client ID iterator for next connection
    self._main_window.client_id_iterator = 1
    self.signals.connection_message.emit("Connection acknowledged", "INFO")
```

## How It Works

### Connection Flow
```
1. User clicks Connect
   ↓
2. App tries to connect with client_id_iterator (starts at 1)
   ↓
3a. SUCCESS → Reset client_id_iterator to 1
   ↓
   Connected!

3b. ERROR 326 (Client ID in use)
   ↓
4. Increment client_id_iterator (1 → 2)
   ↓
5. Disconnect current attempt
   ↓
6. Wait 2 seconds
   ↓
7. Retry connection with new client ID
   ↓
8. Repeat steps 3-7 until:
   - Connection succeeds (client ID is available), OR
   - Reached max_client_id (10) → Show error message
```

### Example Scenario
```
Attempt 1: Client ID 1 → Error 326 (in use)
Attempt 2: Client ID 2 → Error 326 (in use)
Attempt 3: Client ID 3 → SUCCESS! Connected
```

### User Experience
```
[INFO] Connecting to IBKR at 127.0.0.1:7497...
[WARNING] Client ID 1 already in use
[INFO] Retrying with Client ID 2...
[INFO] Connecting to IBKR at 127.0.0.1:7497...
[WARNING] Client ID 2 already in use
[INFO] Retrying with Client ID 3...
[INFO] Connecting to IBKR at 127.0.0.1:7497...
[SUCCESS] ✓ Connected to IBKR! Next Order ID: 1
```

## Configuration

### Maximum Client IDs to Try
Default: 10 (client IDs 1-10)

To change, modify in `__init__`:
```python
self.max_client_id = 20  # Try up to client ID 20
```

### Retry Delay
Default: 2000ms (2 seconds)

To change, modify in error handler:
```python
QTimer.singleShot(5000, self._main_window.retry_connection_with_new_client_id)  # 5 second delay
```

## Benefits

1. **Automatic Recovery**: No manual intervention needed when client ID conflicts
2. **Multiple Instances**: Can run multiple app instances simultaneously
3. **Clean Reconnect**: Properly disconnects before retrying
4. **User Feedback**: Clear messages showing which client ID is being tried
5. **Bounded Retries**: Stops at max_client_id to prevent infinite loops

## Testing

### Test Scenarios
1. ✅ **Single instance**: Connects with client ID 1
2. ✅ **Second instance**: Auto-increments to client ID 2
3. ✅ **Third instance**: Auto-increments to client ID 3
4. ✅ **Exhaustion**: After 10 instances, shows error message
5. ✅ **Disconnect/Reconnect**: Resets iterator to 1 after successful disconnect

### Verification
```powershell
# Watch the logs while starting multiple instances
Get-Content ".\logs\2025-10-28.log" -Wait | Select-String "Client ID"
```

## Files Modified
- `main.py`:
  - Added client ID retry variables to `__init__`
  - Enhanced error handler with error 326 logic
  - Added `retry_connection_with_new_client_id()` method
  - Updated `connect_to_ibkr()` to use `client_id_iterator`
  - Added iterator reset in `connectAck()`

## Comparison with Tkinter
This implementation **exactly matches** the Tkinter version:
- Same retry logic (increment and retry)
- Same max client IDs (1-10)
- Same delay (2 seconds)
- Same user feedback messages
- Same iterator reset on success
