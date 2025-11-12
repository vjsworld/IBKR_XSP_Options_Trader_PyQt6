from ibapi import wrapper  # type: ignore
from ibapi.client import EClient  # type: ignore
from ibapi.wrapper import EWrapper  # type: ignore
from ibapi.contract import Contract  # type: ignore
from ibapi.common import BarData  # type: ignore
from threading import Event
import time
import datetime as dt
from termcolor import colored
import pandas as pd
import os
import pickle


# --------- MOD --------- #
symbol_ = 'SPX'
last_trade_date_ = '20250925'
es_class = 'EW2' 

# ------ SYMBOL ------ #
currency_ = 'USD'

# --------------------- #
port_number = 7497
client_id = 234
working_dir = f'TV_Relay/backtest/backtest_data/{symbol_}_{last_trade_date_}'  # set to working directory
# set to working directory
symbol_ = symbol_.upper()
# create dir if not exists
if not os.path.exists(working_dir):
    os.makedirs(working_dir)
os.chdir(working_dir)


# --------------------- #
if symbol_ == 'SPX':
    secType_ = 'OPT'
    op_symbol = 'SPX'
    exchange_ = 'CBOE'
    instrument_class = 'SPXW'
    index_class = 'IND'
    index_type = 'IND'
    export_folder = 'op_data'
    base_price = 6550.0
    strike_range = 50
    strike_increment = 5
    index_date = last_trade_date_
elif symbol_ == 'NQ':
    secType_ = 'FOP'
    op_symbol = 'NQ'
    exchange_ = 'CME'
    instrument_class = 'Q1A'
    index_class = 'NQ'
    index_type = 'FUT'
    export_folder = 'fut_ops'
    base_price = 17650.0
    strike_range = 300
    strike_increment = 10
    index_date = '202403'
elif symbol_ == 'VIX':
    secType_ = 'OPT'
    op_symbol = 'VIX'
    exchange_ = 'CBOE'
    instrument_class = 'VIXW'
    index_class = 'IND'
    index_type = 'IND'
    export_folder = 'vix'
    base_price = 16.0
    strike_range = 10
    strike_increment = 1
    index_date = last_trade_date_
elif symbol_ == 'CL':
    secType_ = 'FOP'
    op_symbol = 'LO2'
    exchange_ = 'NYMEX'
    instrument_class = 'LO2'
    index_class = 'CL'
    index_type = 'FUT'
    export_folder = 'cl_ops'
    base_price = 70.0
    strike_range = 10
    strike_increment = 1
    index_date = '202402'
elif symbol_ == 'ES':
    secType_ = 'FOP'
    op_symbol = 'ES'
    exchange_ = 'CME'
    instrument_class = es_class
    index_class = 'ES'
    index_type = 'FUT'
    export_folder = 'es'
    base_price = 0.0
    strike_range = 150
    strike_increment = 5
    index_date = '202512'
elif symbol_ == 'SPY':
    secType_ = 'OPT'
    op_symbol = 'SPY'
    exchange_ = 'SMART'
    instrument_class = 'SPY'
    index_class = 'SPY'
    index_type = 'STK'
    export_folder = 'spy'
    base_price = 645.0
    strike_range = 40
    strike_increment = 1
    index_date = last_trade_date_
elif symbol_ == 'QQQ':
    secType_ = 'OPT'
    op_symbol = 'QQQ'
    exchange_ = 'SMART'
    instrument_class = 'QQQ'
    index_class = 'QQQ'
    index_type = 'STK'
    export_folder = 'qqq'
    base_price = 580.0
    strike_range = 15
    strike_increment = 1
    index_date = last_trade_date_
elif symbol_ == 'TSLA':
    secType_ = 'OPT'
    op_symbol = 'TSLA'
    exchange_ = 'SMART'
    instrument_class = 'TSLA'
    index_class = 'TSLA'
    index_type = 'STK'
    export_folder = 'tsla'
    base_price = 370
    strike_range = 40
    strike_increment = 5
    index_date = last_trade_date_
elif symbol_ == 'NVDA':
    secType_ = 'OPT'
    op_symbol = 'NVDA'
    exchange_ = 'SMART'
    instrument_class = 'NVDA'
    index_class = 'NVDA'
    index_type = 'STK'
    export_folder = 'nvda'
elif symbol_ == 'MSTR':
    secType_ = 'OPT'
    op_symbol = 'MSTR'
    exchange_ = 'SMART'
    instrument_class = 'MSTR'
    index_class = 'MSTR'
    index_type = 'STK'
    export_folder = 'mstr'
    base_price = 330
    strike_range = 40
    strike_increment = 5
    index_date = last_trade_date_
else:
    raise ValueError("Symbol not recognized")

# check if dir exists
if not os.path.exists(export_folder):
    os.makedirs(export_folder)


# -------------- #
# msg fn
# -------------- #
def msg(txt, color):
    print(colored(f" >> {txt}\n", color))

# function to serialize a Python object
def serialize_object(obj, file_name):
    with open(file_name, 'wb') as f:
        pickle.dump(obj, f)



# -------------- #
# IBapi
# -------------- #
class IBapi(EWrapper, EClient):
    def __init__(self):
        # self = IBapi()
        EClient.__init__(self, self)
        self.data = {} # Historical data will be stored here
        self.base_price = base_price
        self.id = 0
        self.req_ids = {}
        self.call_options = {}
        self.put_options = {}
        self.current_request_id = 0
        self.ticker = Contract()
        self.ticker.symbol = symbol_
        self.ticker.secType = index_type
        self.ticker.exchange = exchange_
        self.ticker.currency = currency_
        self.ticker.lastTradeDateOrContractMonth = index_date
        self.ticker_data = []
        self.ticker_req_id = 500

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson):
        if reqId != -1:
            print("Error: ", reqId, " ", errorCode, " ", errorString)
            total_requests = len(self.req_ids.keys())
            if self.current_request_id < total_requests:
                print("Unfinished requests, requesting new data...")
                self.current_request_id += 1
                self.fetch_historical_data(self.current_request_id)
        else:
            print("MSG: ", errorString)

    def build_contract(self, symbol, secType, exchange, currency, last_trade_date, strike, right):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        if symbol in ["NQ", "ES"] or symbol_ == "CL":
            contract.exchange = exchange
        else:
            contract.exchange = "SMART"
        contract.currency = currency
        contract.lastTradeDateOrContractMonth = last_trade_date
        contract.strike = strike
        contract.right = right
        contract.tradingClass = instrument_class
        return contract
    
    def build_chain(self):
        # calls in both directions
        call_strikes = [self.base_price + x for x in range(-strike_range, strike_range, strike_increment)]
        put_strikes = [self.base_price + x for x in range(-strike_range, strike_range, strike_increment)]
        for strike in call_strikes:
            self.req_ids[self.id] = {'strike': strike, 'right': 'C'}
            self.id += 1
        for strike in put_strikes:
            self.req_ids[self.id] = {'strike': strike, 'right': 'P'}
            self.id += 1
        msg(f"Call strikes: {call_strikes}", "green")
        msg(f"Put strikes: {put_strikes}", "green")
        for strike in call_strikes:
            contract = self.build_contract(op_symbol, secType_, exchange_, currency_, last_trade_date_, strike, 'C')
            self.call_options[strike]= contract
        for strike in put_strikes:
            contract = self.build_contract(op_symbol, secType_, exchange_, currency_, last_trade_date_, strike, 'P')
            self.put_options[strike] = contract
        self.fetch_historical_data(0)
        

    def historicalData(self, reqId, bar: BarData):
        if reqId == 500:
            self.ticker_data.append(bar)
            return None
        strike_ = self.req_ids[reqId]['strike']
        right_ = self.req_ids[reqId]['right']
        strike_right = f"{strike_}_{right_}"
        if self.data.get(strike_right):
            self.data[strike_right].append(bar)
        else:
            self.data[strike_right] = [bar]

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        if reqId == 500:
            msg(f"Finished fetching {symbol_} historical data", "green")
            self.export_df(self.ticker_data, symbol_, export_folder, last_trade_date_)
            # set base price to last close rounded to nearest 10
            self.base_price = round(self.ticker_data[-1].close / 10) * 10
            msg(f"Base price set to: {self.base_price}", "green")
            self.build_chain()
            return None
        strike_ = self.req_ids[reqId]['strike']
        right_ = self.req_ids[reqId]['right']
        strike_right = f"{strike_}_{right_}"
        msg(f"hist data end strike: {strike_} right: {right_}", "blue")
        # export
        self.export_df(self.data[strike_right], f"{strike_}_{right_}", export_folder, last_trade_date_)
        msg(f"exported df {strike_right}", "green")
        # next request
        self.current_request_id += 1
        if self.req_ids.get(self.current_request_id):
            msg(f'fetch new: {self.current_request_id}', "blue")
            self.fetch_historical_data(self.current_request_id)
        else:
            msg("No more requests", "green")
            self.disconnect()

    def fetch_historical_data(self, reqId):
        try:
            # Fetch historical data
            strike_ = self.req_ids[reqId]['strike']
            right_ = self.req_ids[reqId]['right']
            if right_ == 'C':
                option = self.call_options.get(strike_)
            elif right_ == 'P':
                option = self.put_options.get(strike_)
            msg(f"Fetching historical data for {strike_} : {right_}...", "green")
            self.reqHistoricalData(reqId, option, '', '1 D', '15 secs', 'MIDPOINT', 0, 1, False, [])
            time.sleep(1)
        except Exception as e:
            msg(e, "red")

    # -------------- #
    # export data
    # -------------- #
    def export_df(self, data_, key_, dir_=export_folder, 
        last_trade_date_=dt.datetime.now().strftime('%Y%m%d')):
        timestamp = []
        volume = []
        open_ = []
        high = []
        low = []
        close = []
        iv = []
        for row in data_:
            timestamp.append(row.date)
            volume.append(row.volume)
            open_.append(row.open)
            high.append(row.high)
            low.append(row.low)
            close.append(row.close)
        df = pd.DataFrame({'timestamp': timestamp, 'volume': volume, 'open': open_, 'high': high, 'low': low, 'close': close})
        df.to_csv(f'{dir_}/{key_}_{last_trade_date_}.csv', index=False)


# -------------- #
# main
# -------------- #
def main():
    app = IBapi()
    app.connect("localhost", port_number, client_id)
    time.sleep(1)
    msg("Fetching historical data...", "green")
    app.reqHistoricalData(500, app.ticker, '', '1 D', '15 secs', 'TRADES', 0, 1, False, [])
    time.sleep(2)
    #app.disconnect()
    serialize_object(app.data, f'{last_trade_date_}_data.pickle')
    app.run()
    time.sleep(2)


if __name__ == "__main__":
    main()