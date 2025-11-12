# Trade Tracking and Analysis Feature

## Overview
Comprehensive tracking and visualization system to distinguish between Strategy (automated TradeStation) and Manual trades across all grids, CSV files, and new analysis windows.

## Features Implemented

### 1. Visual Indicators in Grids
**Positions Table:**
- Added "Source" column (before "Action" column)
- Color coding:
  - 🟢 **Strategy** trades: Green (#4CAF50)
  - 🟠 **Manual** trades: Orange (#FF9800)
- Table now has 12 columns total

**Orders Table:**
- Added "Source" column (before "Action" column)
- Same color coding as positions
- Table now has 8 columns total

### 2. CSV File Enhancements
**trade_log.csv:**
- Added "Source" column (Strategy/Manual)
- Updated header: `DateTime, OrderID, Action, Side, Qty, AvgFillPrc, Source`
- Tracks every filled order with source attribution

**PnL.csv:**
- Added "Source" column (Strategy/Manual)
- Updated header includes: `..., TradePnL$, TradePnL%, Source`
- Tracks completed round-trip trades with source attribution

### 3. New Viewer Windows

#### Trade Log Viewer
**Features:**
- Opens via "Show TradeLog" button (blue)
- Displays all trades from trade_log.csv in datagrid
- Newest trades shown at top (reversed order)
- Source column color-coded (Strategy=Green, Manual=Orange)
- Refresh button to reload data
- Auto-resizing columns
- Dark theme matching main application

#### P&L Analysis Viewer
**Features:**
- Opens via "Show PnL" button (orange)
- Comprehensive trade performance statistics:
  - Total trades, winning/losing breakdown
  - Win rate percentage
  - Total P&L with color coding
  - Average win/loss amounts
  - Largest win/loss tracking
  - Profit factor calculation
  - **Strategy vs Manual breakdown:**
    - Separate trade counts
    - Separate P&L totals
    - Color-coded display
- Full P&L data table (newest at top)
- **Equity Curve Chart:**
  - Running cumulative P&L graph
  - Green fill for profit zones
  - Red fill for loss zones
  - Trade-by-trade progression
  - Dark theme with grid
- Refresh button to reload data
- Split view: Stats/Table (top), Chart (bottom)

### 4. UI Updates
**New Buttons Added (in header):**
1. **Show Charts** (Green) - Existing
2. **Show TradeLog** (Blue) - NEW
3. **Show PnL** (Orange) - NEW

All buttons have consistent styling with hover effects.

## Technical Implementation

### Source Tracking
**Automated Detection:**
- `is_automated` flag tracked in:
  - `pending_orders` dictionary
  - `trade_entries` dictionary (for P&L matching)
  - Position data (via `is_automated` field)
- Set to `True` for TradeStation automation entries
- Set to `False` for all manual trades

**CSV Logging:**
- `log_trade_to_csv()` updated to accept `is_automated` parameter
- `log_pnl_to_csv()` reads `is_automated` from entry_data
- Source determined: `'Strategy' if is_automated else 'Manual'`

### Window Classes
**TradeLogWindow:**
- Inherits from QMainWindow
- CSV reading with error handling
- Table population with color coding
- Dark theme styling

**PnLWindow:**
- Inherits from QMainWindow
- CSV reading with DictReader
- Statistics calculation from P&L data
- Matplotlib integration for equity curve
- Comprehensive stat labels with color coding
- Splitter for stats/table and chart sections

### Column Index Updates
**Positions Table:**
- Close button moved from column 10 to column 11
- Updated `on_position_cell_clicked()` handler

**Orders Table:**
- Cancel button moved from column 6 to column 7
- Updated `on_order_cell_clicked()` handler

## Usage

### Viewing Trade History
1. Click **"Show TradeLog"** button
2. Window opens showing all trades
3. Click **"Refresh"** to reload latest data
4. Scroll to see historical trades
5. Source column shows Strategy (green) vs Manual (orange)

### Analyzing Performance
1. Click **"Show PnL"** button
2. View comprehensive statistics at top:
   - Overall performance metrics
   - Strategy vs Manual breakdown
3. Review detailed trade table
4. Analyze equity curve chart showing cumulative P&L
5. Click **"Refresh"** to update with latest completed trades

### Grid Monitoring
**Real-Time Indicators:**
- Open positions show source in "Source" column
- Active orders show source in "Source" column
- Color coding makes it easy to distinguish:
  - Green = Automated strategy trades
  - Orange = Manual trades

## Data Files

### Environment-Specific Files
**Development:**
- `dev_trade_log.csv`
- `dev_PnL.csv`

**Production:**
- `prod_trade_log.csv`
- `prod_PnL.csv`

### File Creation
- Headers automatically created on first trade
- Files persist across sessions
- Located in workspace root directory

## Benefits

### For Strategy Development
- Track automated strategy performance separately
- Compare strategy vs manual trade results
- Identify which approach is more profitable
- Analyze win rates for each method

### For Risk Management
- Monitor all open positions with source attribution
- See pending orders by source
- Track real-time P&L by trade type
- Review historical performance metrics

### For Trade Analysis
- Complete trade log for auditing
- P&L breakdown by source
- Visual equity curve showing account growth
- Statistical metrics for performance evaluation

## Color Scheme
- 🟢 **Strategy/Automated**: #4CAF50 (Green)
- 🟠 **Manual**: #FF9800 (Orange)
- 🔵 **TradeLog Button**: #2196F3 (Blue)
- 🟠 **PnL Button**: #FF9800 (Orange)
- 🟢 **Charts Button**: #4CAF50 (Green)
- ✅ **Positive P&L**: #00ff00 (Bright Green)
- ❌ **Negative P&L**: #ff0000 (Red)

## Future Enhancements (Potential)
- Export functionality for analysis in Excel
- Date range filtering for historical analysis
- Additional performance metrics (Sharpe ratio, etc.)
- Comparison charts between Strategy and Manual performance
- Trade journal notes integration
- Alert system for performance thresholds
