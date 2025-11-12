import time
import threading
import csv
import os
from datetime import datetime

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.utils import iswrapper

# --- Configuration Section ---
# --- PLEASE EDIT THESE VALUES ---

# Connection Parameters
HOST = '127.0.0.1'
PORT = 7497  # 7497 for TWS, 4002 for Gateway
CLIENT_ID = 12

# Underlying Contract Configuration (e.g., NQ Futures)
UNDERLYING_SYMBOL = 'NQ'
UNDERLYING_SEC_TYPE = 'FUT'
UNDERLYING_EXCHANGE = 'CME'
UNDERLYING_LAST_TRADE_DATE = '202509' # The underlying future for the options

# Option Chain Configuration
OPTION_EXPIRATION_DATE = '20250926' # Format: YYYYMMDD
DATA_DIR = 'option_data' # Directory to save the CSV files

# --- End of Configuration Section ---


class IBKROptionHistoryDownloader(EWrapper, EClient):
    """
    Handles fetching a full option chain and then downloading the
    complete 1-minute bar history for each contract in that chain.
    """
    def __init__(self, host, port, client_id):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        
        self.req_id_counter = 0
        self.underlying_conId = None
        self.option_contracts = []
        self.bar_data_list = []

        # Threading events to manage asynchronous API calls
        self.contract_details_event = threading.Event()
        self.option_chain_event = threading.Event()
        self.hist_data_event = threading.Event()

        self.connect(host, port, client_id)
        
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()
        time.sleep(1)

    @iswrapper
    def error(self, reqId, errorCode, errorString):
        if errorCode in [2104, 2106, 2158, 2107]: return
        print(f"Error - ReqId: {reqId}, Code: {errorCode}, Msg: {errorString}")
        # Error 162 signifies no more historical data is available for the request
        if errorCode == 162 and reqId > 1:
             self.hist_data_event.set()
        elif errorCode != 162 and reqId > 1: # Other errors during history download
            self.hist_data_event.set()


    @iswrapper
    def contractDetails(self, reqId, contractDetails):
        if reqId == 0:
            self.underlying_conId = contractDetails.contract.conId

    @iswrapper
    def contractDetailsEnd(self, reqId):
        if reqId == 0:
            self.contract_details_event.set()

    @iswrapper
    def securityDefinitionOptionParameter(self, reqId, exchange, underlyingConId, tradingClass, multiplier, expirations, strikes):
        if reqId == 1:
            if OPTION_EXPIRATION_DATE in expirations:
                for strike in strikes:
                    # Create Call contract
                    call_contract = Contract()
                    call_contract.symbol = UNDERLYING_SYMBOL
                    call_contract.secType = "OPT"
                    call_contract.exchange = "CME"
                    call_contract.currency = "USD"
                    call_contract.lastTradeDateOrContractMonth = OPTION_EXPIRATION_DATE
                    call_contract.strike = strike
                    call_contract.right = "C"
                    call_contract.multiplier = "20"
                    self.option_contracts.append(call_contract)
                    
                    # Create Put contract
                    put_contract = Contract()
                    put_contract.symbol = UNDERLYING_SYMBOL
                    put_contract.secType = "OPT"
                    put_contract.exchange = "CME"
                    put_contract.currency = "USD"
                    put_contract.lastTradeDateOrContractMonth = OPTION_EXPIRATION_DATE
                    put_contract.strike = strike
                    put_contract.right = "P"
                    put_contract.multiplier = "20"
                    self.option_contracts.append(put_contract)

    @iswrapper
    def securityDefinitionOptionParameterEnd(self, reqId):
        if reqId == 1:
            self.option_chain_event.set()

    @iswrapper
    def historicalData(self, reqId, bar):
        self.bar_data_list.append([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])

    @iswrapper
    def historicalDataEnd(self, reqId, start, end):
        self.hist_data_event.set()

    def fetch_option_chain(self, underlying_contract):
        """Fetches the full option chain and returns a list of Contract objects."""
        # --- Step 1: Find conId of the underlying ---
        print(f"Requesting contract details for {underlying_contract.symbol} {underlying_contract.lastTradeDateOrContractMonth}...")
        self.reqContractDetails(0, underlying_contract)
        if not self.contract_details_event.wait(timeout=15):
            print("Error: Timed out waiting for underlying contract details.")
            return False
        
        if not self.underlying_conId:
            print("Error: Could not find contract ID for the underlying.")
            return False
        print(f"Found underlying conId: {self.underlying_conId}")

        # --- Step 2: Request option chain parameters ---
        print("\nRequesting option chain parameters...")
        self.reqSecDefOptParams(1, underlying_contract.symbol, "", underlying_contract.secType, self.underlying_conId)
        if not self.option_chain_event.wait(timeout=60):
            print("Error: Timed out waiting for option chain parameters.")
            return False
            
        print(f"Found {len(self.option_contracts)} option contracts for expiration {OPTION_EXPIRATION_DATE}.")
        return True

    def download_history_for_contract(self, contract):
        """Downloads and saves the entire 1-min bar history for a single contract."""
        filename = f"{DATA_DIR}/{contract.symbol}_{contract.lastTradeDateOrContractMonth}_{int(contract.strike)}_{contract.right}_1min_bars.csv"
        print(f"\n--- Starting download for: {filename} ---")
        
        try:
            with open(filename, 'w', newline='') as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow(['datetime', 'open', 'high', 'low', 'close', 'volume'])
                
                end_datetime_str = datetime.now().strftime('%Y%m%d %H:%M:%S')
                
                while True:
                    self.bar_data_list.clear()
                    self.hist_data_event.clear()
                    self.req_id_counter += 1
                    
                    print(f"Requesting data ending: {end_datetime_str}")
                    self.reqHistoricalData(
                        self.req_id_counter, contract, end_datetime_str,
                        '1 W', '1 min', 'TRADES', 0, 1, False, [])

                    if not self.hist_data_event.wait(timeout=30):
                        print(f"Warning: Request timed out for {filename}.")
                        self.cancelHistoricalData(self.req_id_counter)
                        break

                    if not self.bar_data_list:
                        print("No more data available. Download complete for this contract.")
                        break
                    
                    csv_writer.writerows(self.bar_data_list)
                    
                    self.bar_data_list.sort(key=lambda x: x[0])
                    earliest_bar_time_str = self.bar_data_list[0][0]
                    earliest_datetime = datetime.strptime(earliest_bar_time_str, '%Y%m%d  %H:%M:%S')
                    end_datetime_str = earliest_datetime.strftime('%Y%m%d %H:%M:%S')
                    
                    print(f"Wrote {len(self.bar_data_list)} rows. Next request ends at {end_datetime_str}")
                    print("Waiting 11 seconds to respect API pacing rules...")
                    time.sleep(11)

        except IOError as e:
            print(f"Error writing to file {filename}: {e}")

    def close(self):
        self.disconnect()
        print("\nAll tasks complete. Disconnected from IBKR.")


def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created data directory: {DATA_DIR}")

    app = IBKROptionHistoryDownloader(HOST, PORT, CLIENT_ID)
    
    underlying_contract = Contract()
    underlying_contract.symbol = UNDERLYING_SYMBOL
    underlying_contract.secType = UNDERLYING_SEC_TYPE
    underlying_contract.exchange = UNDERLYING_EXCHANGE
    underlying_contract.currency = 'USD'
    underlying_contract.lastTradeDateOrContractMonth = UNDERLYING_LAST_TRADE_DATE
    
    try:
        # First, get the entire list of option contracts
        if app.fetch_option_chain(underlying_contract):
            # Now, iterate and download the history for each one
            for option_contract in app.option_contracts:
                app.download_history_for_contract(option_contract)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        app.close()
        
if __name__ == "__main__":
    main()

