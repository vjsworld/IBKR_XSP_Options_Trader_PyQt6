# Migration Guide: Tkinter → PyQt6

## Quick Comparison

| Feature | Tkinter Version | PyQt6 Version |
|---------|----------------|---------------|
| **GUI Framework** | tkinter + ttkbootstrap | PyQt6 (Qt6) |
| **Charting** | Matplotlib (static) | lightweight-charts (TradingView) |
| **Grid Display** | tksheet | QTableWidget |
| **Threading** | queue.Queue polling | PyQt signals/slots |
| **Theme** | ttkbootstrap "darkly" | QSS (Qt StyleSheet) |
| **Layout** | grid/pack | QVBoxLayout/QHBoxLayout/QSplitter |
| **File Size** | ~4300 lines | ~1300 lines |
| **Performance** | Good | Excellent |
| **Real-time Charts** | Limited (FuncAnimation) | Native (TradingView) |

## Architecture Changes

### Threading Model

**Tkinter (Old)**:
```python
# Polling with root.after()
def process_gui_queue(self):
    while not self.gui_queue.empty():
        message = self.gui_queue.get_nowait()
        # Process message
    self.root.after(100, self.process_gui_queue)

# In IBKR callback
def tickPrice(self, reqId, tickType, price, attrib):
    self.gui_queue.put(("update_price", price))
```

**PyQt6 (New)**:
```python
# Signal/slot mechanism
class IBKRSignals(QObject):
    price_updated = pyqtSignal(float)

# In IBKR callback
def tickPrice(self, reqId, tickType, price, attrib):
    self.signals.price_updated.emit(price)

# In MainWindow
@pyqtSlot(float)
def on_price_updated(self, price):
    self.price_label.setText(f"SPX: {price:.2f}")
```

### Chart Integration

**Tkinter (Old)**:
```python
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

self.fig = Figure(figsize=(5, 4), dpi=80)
self.ax = self.fig.add_subplot(111)
self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
self.canvas.get_tk_widget().pack()

# Draw candlesticks manually
for i, bar in enumerate(bars):
    # Draw line, body, etc.
```

**PyQt6 (New)**:
```python
from lightweight_charts import Chart
from PyQt6.QtWebEngineWidgets import QWebEngineView

self.chart = Chart()
self.candlestick_series = self.chart.create_candlestick_series()
html = self.chart.get_webview_html()

self.web_view = QWebEngineView()
self.web_view.setHtml(html)

# Update with formatted data
self.candlestick_series.set(formatted_bars)
```

### Table Display

**Tkinter (Old)**:
```python
from tksheet import Sheet

self.option_sheet = Sheet(frame, headers=headers, theme="dark")
self.option_sheet.pack()

# Update cell
self.option_sheet.set_cell_data(row, col, value)
self.option_sheet.highlight_cells(row, col, fg=color, bg=bg)
```

**PyQt6 (New)**:
```python
self.option_table = QTableWidget()
self.option_table.setHorizontalHeaderLabels(headers)

# Update cell
item = QTableWidgetItem(value)
item.setForeground(QColor(color))
item.setBackground(QColor(bg))
self.option_table.setItem(row, col, item)
```

### Timers

**Tkinter (Old)**:
```python
# Periodic update
self.root.after(1000, self.update_positions)

# Debounced update
if self.update_timer_id:
    self.root.after_cancel(self.update_timer_id)
self.update_timer_id = self.root.after(100, self.do_update)
```

**PyQt6 (New)**:
```python
# Periodic update
self.timer = QTimer()
self.timer.timeout.connect(self.update_positions)
self.timer.start(1000)

# Debounced update (single-shot)
self.debounce_timer = QTimer()
self.debounce_timer.setSingleShot(True)
self.debounce_timer.timeout.connect(self.do_update)
self.debounce_timer.start(100)
```

## Code Size Reduction

### Why is PyQt6 version smaller?

1. **Native Widgets**: No need for custom rendering (tksheet → QTableWidget)
2. **Signal/Slot**: Eliminates queue management boilerplate
3. **Built-in Styling**: QSS replaces manual color management
4. **Chart Library**: lightweight-charts handles rendering automatically
5. **Layout Managers**: QVBoxLayout/QHBoxLayout more concise than grid/pack

### Feature Parity

Despite being smaller, PyQt6 version has **all features** of tkinter version:
- ✅ Real-time option chain
- ✅ Manual trading with mid-price chasing
- ✅ Position/order management
- ✅ Historical charts (calls/puts)
- ✅ IBKR TWS dark theme
- ✅ Settings persistence
- ✅ Auto-reconnection
- ✅ Greeks calculations
- ✅ Activity logging

## Key Benefits

### Performance
- **Faster rendering**: Native Qt widgets vs tkinter canvas
- **Smooth charts**: TradingView engine vs Matplotlib redrawing
- **No blocking**: Signal/slot is non-blocking, queue polling can block
- **Better memory**: Qt manages resources efficiently

### Developer Experience
- **Type safety**: PyQt6 has better type hints
- **Documentation**: Qt documentation is comprehensive
- **Debugging**: Qt Creator Designer for UI design
- **Cross-platform**: True native look on Windows/Mac/Linux

### User Experience
- **Responsive UI**: No lag during data updates
- **Professional charts**: TradingView quality
- **Native feel**: Uses platform widgets
- **Better scaling**: High DPI support built-in

## Migration Checklist

If migrating your own tkinter app to PyQt6:

- [ ] Replace `tkinter` imports with `PyQt6.QtWidgets`
- [ ] Convert `root.after()` to `QTimer`
- [ ] Replace queue polling with signals/slots
- [ ] Convert grid/pack layouts to QVBoxLayout/QHBoxLayout
- [ ] Replace Matplotlib with lightweight-charts or QChart
- [ ] Convert ttkbootstrap styling to QSS
- [ ] Update event bindings to signal/slot connections
- [ ] Test thread safety with QThread and signals
- [ ] Verify all callbacks use signals, not direct GUI updates
- [ ] Test on target platform(s)

## Running Both Versions

You can keep both versions installed:

**Tkinter version**:
```powershell
python main_tkinter.py
```

**PyQt6 version**:
```powershell
.\.venv\Scripts\python.exe main.py
```

They use separate dependencies and won't conflict.

## Recommendations

### When to use Tkinter
- Simple utilities
- Quick prototypes
- No threading complexity
- Minimal dependencies

### When to use PyQt6
- Professional applications ✅
- Real-time data visualization ✅
- Multi-threaded apps ✅
- Cross-platform deployment ✅
- Advanced UI requirements ✅

## Support

For the **PyQt6 version** (this project):
- See `README.md` for setup and usage
- See `copilot-instructions.md` for development guide
- Check Qt documentation: https://doc.qt.io/qtforpython-6/

For the **Tkinter version** (legacy):
- See `copilot-instructions-tkinter.md`
- Keep for reference but consider migrating to PyQt6
