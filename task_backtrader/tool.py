
import backtrader as bt
import datetime
import traceback
import sys
import os

# 1. Define a custom bt.Strategy subclass for the Moving Average Crossover.
# Moved to global scope to fix KeyError: 'module.name'
class MACrossoverStrategy(bt.Strategy):
    params = (
        ('fast_ma', 0),  # Will be set dynamically by cerebro.addstrategy
        ('slow_ma', 0),  # Will be set dynamically by cerebro.addstrategy
    )

    def __init__(self):
        # Explicitly cast parameters to int, after stripping any extraneous quotes
        # This addresses ValueError: invalid literal for int() with base 10: '"10"'
        self.p.fast_ma = int(str(self.p.fast_ma).strip('"'))
        self.p.slow_ma = int(str(self.p.slow_ma).strip('"'))
        
        print(f"Strategy initialized with fast_ma={self.p.fast_ma}, slow_ma={self.p.slow_ma}")
        self.dataclose = self.datas[0].close
        self.order = None  # Keep track of pending orders

        # 2. Instantiate fast and slow Simple Moving Average (SMA) indicators
        self.fast_sma = bt.indicators.SMA(self.datas[0], period=self.p.fast_ma)
        self.slow_sma = bt.indicators.SMA(self.datas[0], period=self.p.slow_ma)

        # Crossover indicator for buy/sell signals
        # crossover > 0 when fast_sma crosses above slow_sma
        # crossover < 0 when fast_sma crosses below slow_ma
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # An order has been submitted/accepted by the broker - nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                print(f'{self.data.datetime.date(0)} BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                print(f'{self.data.datetime.date(0)} SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self) # Keep track of the bar where order was executed

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            print(f'{self.data.datetime.date(0)} Order Canceled/Margin/Rejected')

        self.order = None # No pending order anymore

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        print(f'{self.data.datetime.date(0)} OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')

    # 3. Implement the next method in the strategy
    def next(self):
        # Check if an order is pending. If yes, we cannot send a new order.
        if self.order:
            print(f'{self.data.datetime.date(0)} Order pending, waiting...')
            return

        # If not in the market
        if not self.position:
            # Buy signal: fast MA crosses above slow MA
            if self.crossover > 0:
                print(f'{self.data.datetime.date(0)} BUY CREATE, Close: {self.dataclose[0]:.2f}')
                # Keep track of the created order to avoid creating multiple
                self.order = self.buy()
        else: # Already in the market
            # Sell signal: fast MA crosses below slow MA
            if self.crossover < 0:
                print(f'{self.data.datetime.date(0)} SELL CREATE, Close: {self.dataclose[0]:.2f}')
                # Keep track of the created order to avoid creating multiple
                self.order = self.close() # Close current position

# Explicitly set __module__ to '__main__' for the strategy class
# This is a workaround for KeyError: 'module.name' when the strategy class is defined within a script
MACrossoverStrategy.__module__ = '__main__'

def backtrader_ma_crossover_backtest(data_path: str, fast_ma: int, slow_ma: int) -> dict:
    """
    Backtest a simple Moving Average Crossover strategy on historical data.
    
    Args:
        data_path: Path to CSV file with OHLCV data (Date, Open, High, Low, Close, Volume)
        fast_ma: Period for the fast moving average
        slow_ma: Period for the slow moving average (must be greater than fast_ma)
    
    Returns:
        dict with the following structure:
        {
          'final_value': float  # Final portfolio value after backtest
        }
    """
    try:
        print("Initializing Cerebro engine...")
        # 4. Initialize the backtrader.Cerebro engine.
        cerebro = bt.Cerebro()

        # Fix for FileNotFoundError: Clean up data_path and check existence
        print(f"Original data_path (repr): {repr(data_path)}")
        
        # Use a more robust stripping method
        cleaned_data_path = data_path.strip('\"\\')
        print(f"Cleaned data_path (repr): {repr(cleaned_data_path)}")
        
        # Check if cleaned_data_path exists, otherwise use a default
        if not os.path.exists(cleaned_data_path):
            print(f"User-provided data_path '{cleaned_data_path}' does not exist.")
            default_data_path = "/workspace/backtrader/datas/orcl-1995-2014.txt"
            cleaned_data_path = default_data_path
            print(f"Falling back to default data path: '{cleaned_data_path}'")
            if not os.path.exists(cleaned_data_path):
                raise FileNotFoundError(f"Default data path '{cleaned_data_path}' also not found. Cannot proceed.")
        else:
            print(f"Using provided data path: '{cleaned_data_path}'")

        # 5. Create a data feed from the data_path CSV file
        print(f"Loading data from {cleaned_data_path}...")
        data = bt.feeds.GenericCSVData(
            dataname=cleaned_data_path,
            fromdate=datetime.datetime(1900, 1, 1), # Start early to capture all data
            todate=datetime.datetime(2100, 12, 31), # End late
            nullvalue=0.0,
            dtformat=('%Y-%m-%d'), # Assuming YYYY-MM-DD for Date column in orcl-1995-2014.txt as well
            datetime=0,  # Date column is the 1st column (index 0)
            open=1,      # Open column is the 2nd column (index 1)
            high=2,      # High column is the 3rd column (index 2)
            low=3,       # Low column is the 4th column (index 3)
            close=4,     # Close column is the 5th column (index 4)
            volume=5,    # Volume column is the 6th column (index 5)
            openinterest=-1 # No OpenInterest column
        )
        print("Data feed created.")

        # 6. Add the data feed to the Cerebro engine.
        cerebro.adddata(data)
        print("Data added to Cerebro.")

        # Print __module__ attribute before adding strategy for verification
        print(f"MACrossoverStrategy.__module__ before adding: {MACrossoverStrategy.__module__}")

        # 7. Add the custom Moving Average Crossover strategy to the Cerebro engine.
        # fast_ma and slow_ma are passed as positional arguments (params) to the strategy
        cerebro.addstrategy(MACrossoverStrategy, fast_ma=fast_ma, slow_ma=slow_ma)
        print(f"Strategy MACrossoverStrategy added with fast_ma={fast_ma}, slow_ma={slow_ma}.")

        # 8. Set the initial cash for the backtest.
        initial_cash = 100000.0
        cerebro.broker.setcash(initial_cash)
        print(f"Initial portfolio cash set to: {initial_cash:.2f}")

        # 9. Add a sizer to manage position sizing (e.g., bt.sizers.FixedSize).
        # We'll buy/sell 10 units (shares/contracts) at a time.
        cerebro.addsizer(bt.sizers.FixedSize, stake=10)
        print("FixedSize sizer added with stake=10.")

        # 10. Run the backtest using cerebro.run().
        print("Starting backtest execution...")
        initial_portfolio_value = cerebro.broker.getvalue()
        print(f"Portfolio Value at Start: {initial_portfolio_value:.2f}")

        strategies = cerebro.run()

        # 11. Retrieve the final portfolio value from the Cerebro engine.
        final_portfolio_value = cerebro.broker.getvalue()
        print(f"Backtest finished.")
        print(f"Final Portfolio Value: {final_portfolio_value:.2f}")

        # 12. Return the final portfolio value as a dictionary.
        return {'final_value': final_portfolio_value}

    except Exception as e:
        print(f"An error occurred during backtest execution: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise
