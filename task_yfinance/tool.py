
import yfinance as yf
import pandas as pd
import sys
import traceback

def yfinance_fetch_prices(ticker: str, start_date: str, end_date: str) -> dict:
    """
    Fetch historical daily closing prices for a given stock ticker and date range.

    Args:
        ticker: Stock ticker symbol (e.g., AAPL, GOOGL)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        dict with the following structure:
        {
          'prices': dict  # Dictionary mapping dates to closing prices
        }
    """
    prices_dict = {}
    try:
        # Refined stripping logic for ticker, start_date, and end_date
        def deep_strip_quotes(s):
            # Continuously strip quotes and backslashes until no more are found
            while True:
                # Strip single quotes, double quotes, and backslashes from both ends
                new_s = s.strip('\"\'\\')
                if new_s == s:
                    break
                s = new_s
            return s

        cleaned_ticker = deep_strip_quotes(ticker)
        cleaned_start_date = deep_strip_quotes(start_date)
        cleaned_end_date = deep_strip_quotes(end_date)

        print(f"yfinance_fetch_prices: Starting data fetch for ticker: {cleaned_ticker}, from {cleaned_start_date} to {cleaned_end_date}", file=sys.stdout)

        # 2. Create a yfinance.Ticker object using the provided ticker symbol.
        ticker_obj = yf.Ticker(cleaned_ticker)

        # 3. Call the history() method on the Ticker object, passing start_date and end_date as arguments.
        # Interval is '1d' by default for daily data.
        hist_data = ticker_obj.history(start=cleaned_start_date, end=cleaned_end_date)

        print(f"yfinance_fetch_prices: Successfully fetched historical data for {cleaned_ticker}. Rows received: {len(hist_data)}", file=sys.stdout)

        # Check if historical data is empty
        if hist_data.empty:
            print(f"yfinance_fetch_prices: No historical data found for ticker: {cleaned_ticker} within the specified date range.", file=sys.stderr)
            return {"prices": {}}

        # 4. Extract the 'Close' column from the resulting pandas DataFrame.
        closing_prices = hist_data['Close']

        # 5. Convert the extracted 'Close' series into a dictionary where keys are dates (formatted as 'YYYY-MM-DD')
        # and values are the corresponding closing prices.
        # The index of the Series is a DatetimeIndex, so format it to string.
        prices_dict = closing_prices.rename(index=lambda x: x.strftime('%Y-%m-%d')).to_dict()

        print(f"yfinance_fetch_prices: Successfully processed closing prices for {cleaned_ticker}. Dates processed: {len(prices_dict)}", file=sys.stdout)

    except Exception as e:
        print(f"yfinance_fetch_prices: An error occurred while fetching prices for {ticker}: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        # Return an empty dictionary on error as per implicit requirement for robustness.
        return {"prices": {}}

    # 6. Return a dictionary with a single key 'prices' whose value is the dictionary of dates and closing prices.
    return {"prices": prices_dict}
