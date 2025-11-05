# TradeStation Integration - Complete Documentation

## Overview

This application integrates with TradeStation 10 using the GlobalDictionary COM interface for bidirectional communication. TradeStation EasyLanguage indicators can send entry/exit signals to Python, which executes trades via the Interactive Brokers API.

## Architecture

```
TradeStation 10 (EasyLanguage Indicator)
     (COM Interface)
GlobalDictionary "IBKR_TRADER"
     (pywin32 COM)
TradeStationManager (Python QThread)
     (PyQt Signals)
MainWindow (GUI Thread)
     (IBKR API)
Interactive Brokers TWS/Gateway
    
Market Execution
```

## Quick Start

1. **Enable TradeStation Tab**: Go to TradeStation tab (5th tab)  Click "Enable TS"
2. **Apply Indicator**: Import _PYTHON GLOBALDICTIONARY.ELD to TradeStation
3. **Send Signals**: Use dict() format to send BUY_CALL, BUY_PUT, CLOSE_ALL signals
4. **Monitor**: Watch Signal History table in TradeStation tab

## Signal Format

### Entry Signals
```easylanguage
GD.SetValue("ENTRY_" + NumToStr(signalID, 0), 
    dict("action", "BUY_CALL", "symbol", "XSP", "quantity", 1)
);
```

### Exit Signals
```easylanguage
GD.SetValue("EXIT_" + NumToStr(signalID, 0), 
    dict("action", "CLOSE_ALL", "symbol", "XSP")
);
```

See **TRADESTATION_QUICK_REFERENCE.md** for complete signal reference.
See **TradeStation_Example_Indicator.txt** for working EasyLanguage code.

