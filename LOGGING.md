# Daily Logging System Documentation

## Overview

The application now includes a comprehensive file-based logging system that creates daily log files with automatic rotation and detailed diagnostic information.

## Log File Location

All logs are stored in the `logs/` directory:
```
logs/
├── 2025-10-24.log
├── 2025-10-25.log
└── ...
```

Each log file is named with the date: `YYYY-MM-DD.log`

## Log File Format

Logs include detailed information for debugging:
```
2025-10-24 15:43:45 | INFO     | SPXTrader | setup_logging:80 | ======================================================================
2025-10-24 15:43:45 | INFO     | SPXTrader | <module>:93      | Loading PyQt6 modules...
```

**Format:** `TIMESTAMP | LEVEL | MODULE | FUNCTION:LINE | MESSAGE`

## Log Levels

The system uses standard Python logging levels:

1. **DEBUG** - Detailed diagnostic information (file only)
   - Market data ticks
   - Greeks calculations
   - IBKR API callbacks
   - Internal state changes

2. **INFO** - General informational messages (file + console)
   - Application startup/shutdown
   - Connection status
   - Module loading
   - User actions

3. **WARNING** - Warning messages for non-critical issues
   - Missing optional features
   - Retryable errors
   - Deprecated features

4. **ERROR** - Error messages for failures
   - Connection failures
   - API errors
   - Data processing errors

5. **CRITICAL** - Critical errors requiring immediate attention
   - Application crashes
   - Fatal initialization errors

## Console vs File Logging

- **Console Output**: INFO level and above (less verbose, cleaner)
- **Log Files**: DEBUG level and above (everything, maximum detail)

This design keeps your terminal clean while capturing complete diagnostic information in files.

## Log Rotation

- **Max File Size**: 10 MB per log file
- **Backup Count**: 30 files (approximately 30 days)
- **Old files are automatically deleted** when the limit is reached

## Viewing Logs

### PowerShell Commands

**View today's log:**
```powershell
Get-Content "logs\$(Get-Date -Format 'yyyy-MM-dd').log"
```

**View last 50 lines of today's log:**
```powershell
Get-Content "logs\$(Get-Date -Format 'yyyy-MM-dd').log" | Select-Object -Last 50
```

**Follow logs in real-time (tail -f):**
```powershell
Get-Content "logs\$(Get-Date -Format 'yyyy-MM-dd').log" -Wait
```

**Search for errors:**
```powershell
Select-String -Path "logs\*.log" -Pattern "ERROR|CRITICAL"
```

**View specific date:**
```powershell
Get-Content "logs\2025-10-24.log"
```

### What Gets Logged

#### Application Lifecycle
- ✅ Startup and initialization
- ✅ Module loading (PyQt6, pandas, numpy, scipy, IBKR API)
- ✅ Main window creation
- ✅ Shutdown and exit codes

#### IBKR Connection
- ✅ Connection attempts (host, port, client ID)
- ✅ Connection acknowledgment
- ✅ Authentication success
- ✅ Data server confirmation
- ✅ Disconnection events
- ✅ Connection errors with full details

#### Market Data
- ✅ SPX price updates
- ✅ Option chain data requests
- ✅ Market data tick updates (bid, ask, last, volume)
- ✅ Greeks calculations (delta, gamma, theta, vega)

#### Trading
- ✅ Order placement
- ✅ Order status changes
- ✅ Position updates
- ✅ Manual trading actions

#### Errors
- ✅ All exceptions with full stack traces (`exc_info=True`)
- ✅ IBKR API error codes and messages
- ✅ Import failures
- ✅ Calculation errors

## Example Log Entries

### Successful Startup
```log
2025-10-24 15:43:45 | INFO     | SPXTrader | setup_logging:80 | ======================================================================
2025-10-24 15:43:45 | INFO     | SPXTrader | setup_logging:81 | SPX 0DTE Options Trading Application - PyQt6 Edition
2025-10-24 15:43:45 | INFO     | SPXTrader | setup_logging:83 | Log file: logs\2025-10-24.log
2025-10-24 15:43:45 | INFO     | SPXTrader | <module>:93      | Loading PyQt6 modules...
2025-10-24 15:43:45 | INFO     | SPXTrader | <module>:107     | PyQt6 loaded successfully
```

### Connection Event
```log
2025-10-24 16:30:12 | INFO     | SPXTrader | connect_to_ibkr:1005 | Initiating IBKR connection...
2025-10-24 16:30:12 | INFO     | SPXTrader | connect_to_ibkr:1015 | Connecting to IBKR: 127.0.0.1:7497 (Client ID: 1)
2025-10-24 16:30:13 | INFO     | SPXTrader | nextValidId:307  | IBKR connected successfully! Next order ID: 123
```

### Error with Stack Trace
```log
2025-10-24 16:45:22 | ERROR    | SPXTrader | connect_to_ibkr:1025 | IBKR connection error: Connection refused
Traceback (most recent call last):
  File "main.py", line 1023, in connect_to_ibkr
    self.ibkr_client.connect(self.host, self.port, self.client_id)
  ...
ConnectionRefusedError: [WinError 10061] No connection could be made
```

### Greeks Calculation
```log
2025-10-24 17:15:33 | DEBUG    | SPXTrader | calculate_greeks:158 | Calculating greeks: C spot=5800.0 strike=5850.0 tte=0.0416 vol=0.18
```

## Debugging Workflow

1. **Reproduce the issue** - Run the application and perform the action
2. **Check the console** - Quick overview of INFO+ messages
3. **Open today's log file** - Full DEBUG details with timestamps
4. **Search for errors** - Use `Select-String` to find ERROR/CRITICAL
5. **Review stack traces** - Full exception details with `exc_info=True`
6. **Check timing** - Timestamps show sequence of events

## Benefits

✅ **Daily rotation** - One file per day, easy to find issues  
✅ **Detailed context** - Module, function, line number for every log  
✅ **Full stack traces** - Complete error details for debugging  
✅ **Thread-safe** - Safe to use from IBKR API thread and main GUI thread  
✅ **Automatic cleanup** - Old logs deleted automatically (30 day retention)  
✅ **Two-tier output** - Clean console + detailed file logs  

## Configuration

All logging configuration is in `main.py`, function `setup_logging()`:

```python
# File handler - DEBUG level (everything)
file_handler.setLevel(logging.DEBUG)

# Console handler - INFO level (less verbose)
console_handler.setLevel(logging.INFO)

# File rotation
maxBytes=10*1024*1024,  # 10MB per file
backupCount=30,         # Keep 30 days
```

## Tips

- **Performance**: Logging adds minimal overhead (~1-5ms per log entry)
- **Disk space**: ~1-5 MB per day typical usage, auto-cleaned at 30 days
- **Privacy**: Logs contain order IDs, account info - keep secure
- **Development**: Set console to DEBUG for more verbose output during testing

## Accessing Logger in Code

```python
# Logger is a global variable, available throughout main.py
logger.info("Information message")
logger.debug("Detailed diagnostic info")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)  # Include stack trace
logger.critical("Critical failure")
```

## Integration with IBKR API

The logger is thread-safe and works correctly with the IBKR API background thread:

```python
class IBKRWrapper(EWrapper):
    def error(self, reqId, errorCode, errorString):
        logger.debug(f"IBKR error: reqId={reqId}, code={errorCode}, msg={errorString}")
```

All IBKR callbacks log their activity for complete audit trail.
