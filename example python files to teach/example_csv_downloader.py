import time
import threading
import csv
from datetime import datetime, timedelta

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.utils import iswrapper

# --- Configuration Section ---
# --- PLEASE EDIT THESE VALUES ---

# Connection Parameters
HOST = '127.0.0.1'
PORT = 7497  # 7497 for TWS, 4002 for Gateway
CLIENT_ID = 10

# Contract Configuration (Example: NQ Futures)
CONTRACT_SYMBOL = 'NQ'
CONTRACT_SEC_TYPE = 'FUT'
CONTRACT_EXCHANGE = 'CME'
CONTRACT_CURRENCY = 'USD'
# Specify the contract month in YYYYMM format.
# NQ contracts expire quarterly (Mar, Jun, Sep, Dec).
# Let's use the December 2025 contract as an example.
CONTRACT_LAST_TRADE_DATE = '202512'

# Data Request Configuration
# How far back you want to attempt to download data. IB limits 1-sec bars to 6 months for TRADES.
# Format: 'YYYY-MM-DD HH:MM:SS'
EARLIEST_DATA_DATE = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')

# What data to request (e.g., TRADES, MIDPOINT, BID, ASK)
WHAT_TO_SHOW = 'TRADES'

# --- End of Configuration Section ---


class IBKRDownloader(EWrapper, EClient):
    """
    Handles connection, requests, and data processing for IBKR.
    """
    def __init__(self, host, port, client_id):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        
        # Threading event to signal completion of a historical data request
        self.hist_data_event = threading.Event()
        # List to store bar data from a single request
        self.bar_data_list = []

        # Connect to TWS/Gateway
        self.connect(host, port, client_id)
        
        # Start the message processing thread
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()
        time.sleep(1) # Allow time for connection to establish

    @iswrapper
    def error(self, reqId, errorCode, errorString):
        """Handles errors from the TWS/Gateway."""
        # Ignore informational messages
        if errorCode in [2104, 2106, 2158, 2107]:
            return
        print(f"Error - ReqId: {reqId}, Code: {errorCode}, Msg: {errorString}")
        # Error code 162 indicates no data for the query, a common occurrence when we've reached the end.
        if errorCode == 162:
            self.hist_data_event.set() # Signal completion to stop waiting

    @iswrapper
    def historicalData(self, reqId, bar):
        """Callback that receives historical bar data."""
        self.bar_data_list.append([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])

    @iswrapper
    def historicalDataEnd(self, reqId, start, end):
        """Called when a historical data request has finished."""
        print(f"Finished historical data request {reqId} for period: {start} - {end}")
        self.hist_data_event.set() # Signal that this request is done

    def write_data_to_csv(self, csv_writer):
        """Appends the collected bar data to the CSV file."""
        if not self.bar_data_list:
            return
        
        try:
            csv_writer.writerows(self.bar_data_list)
            print(f"Successfully wrote {len(self.bar_data_list)} new rows to CSV.")
        except Exception as e:
            print(f"Error writing data to CSV: {e}")

    def download_data(self, contract, earliest_date, what_to_show):
        """
        Main method to orchestrate the data download loop.
        It requests data in chunks and writes to a CSV file.
        """
        # Create a descriptive CSV filename based on the contract
        csv_filename = f"bars_1s_{contract.symbol}_{contract.lastTradeDateOrContractMonth}.csv"
        
        try:
            # Open the file in append mode
            with open(csv_filename, 'a', newline='') as f:
                csv_writer = csv.writer(f)

                # Write a header row if the file is new/empty
                if f.tell() == 0:
                    csv_writer.writerow(['datetime', 'open', 'high', 'low', 'close', 'volume'])
                
                print(f"Data will be saved to '{csv_filename}'")
                
                # Start with the current time for the first request
                end_datetime_str = datetime.now().strftime('%Y%m%d %H:%M:%S')
                req_id_counter = 0

                while True:
                    self.bar_data_list.clear()
                    self.hist_data_event.clear()
                    
                    print(f"\nRequesting data ending: {end_datetime_str}")
                    
                    # Make the historical data request
                    self.reqHistoricalData(
                        reqId=req_id_counter,
                        contract=contract,
                        endDateTime=end_datetime_str,
                        durationStr='1800 S',  # Request 30 minutes of data per chunk
                        barSizeSetting='1 secs',
                        whatToShow=what_to_show,
                        useRTH=0, # 0 = data outside RTH, 1 = RTH only
                        formatDate=1, # 1 for yyyyMMdd hh:mm:ss, 2 for epoch time
                        keepUpToDate=False,
                        chartOptions=[]
                    )
                    req_id_counter += 1

                    # Wait for the request to complete (or timeout after 30 seconds)
                    request_completed = self.hist_data_event.wait(timeout=30)
                    
                    if not request_completed:
                        print("Request timed out. Cancelling and exiting.")
                        self.cancelHistoricalData(req_id_counter -1)
                        break
                    
                    if not self.bar_data_list:
                        print("No more historical data available for this contract. Download complete.")
                        break
                        
                    # Write the chunk of data to the CSV file
                    self.write_data_to_csv(csv_writer)

                    # Determine the end time for the next request
                    self.bar_data_list.sort(key=lambda x: x[0])
                    earliest_bar_time_str = self.bar_data_list[0][0]
                    earliest_bar_datetime = datetime.strptime(earliest_bar_time_str, '%Y%m%d  %H:%M:%S')
                    
                    if earliest_bar_datetime < datetime.strptime(earliest_date, '%Y-%m-%d %H:%M:%S'):
                        print(f"Reached the target earliest date of {earliest_date}. Download complete.")
                        break
                        
                    end_datetime_str = earliest_bar_datetime.strftime('%Y%m%d %H:%M:%S')
                    
                    # --- IB Pacing Rule ---
                    print("Waiting 11 seconds to respect IB pacing rules...")
                    time.sleep(11)

        except IOError as e:
            print(f"Error opening or writing to file {csv_filename}: {e}")
            
    def close(self):
        """Disconnects from IB."""
        self.disconnect()
        print("Disconnected from IBKR.")


def main():
    """Main function to run the downloader."""
    app = IBKRDownloader(HOST, PORT, CLIENT_ID)
    
    # Define the contract object
    contract = Contract()
    contract.symbol = CONTRACT_SYMBOL
    contract.secType = CONTRACT_SEC_TYPE
    contract.exchange = CONTRACT_EXCHANGE
    contract.currency = CONTRACT_CURRENCY
    contract.lastTradeDateOrContractMonth = CONTRACT_LAST_TRADE_DATE
    
    try:
        app.download_data(contract, EARLIEST_DATA_DATE, WHAT_TO_SHOW)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        app.close()
        

if __name__ == "__main__":
    main()

