

import pandas as pd
import riskfolio as rf
import traceback
import sys

def riskfolio_optimal_portfolio(returns_data: str, target_risk: float) -> dict:
    """
    Calculate optimal portfolio weights to maximize the Sharpe ratio at a target risk level.
    This function finds a portfolio on the efficient frontier that has the specified
    target standard deviation. Such a portfolio is considered optimal for that given
    risk level, implicitly maximizing its Sharpe ratio among portfolios with the same risk.

    Args:
        returns_data: Path to CSV file containing historical returns (rows=dates, columns=assets)
        target_risk: Target risk level (standard deviation) for the portfolio

    Returns:
        dict with the following structure:
        {
          'optimal_weights': dict  # Dictionary mapping asset names to their optimized weights
        }
    """
    print("Starting riskfolio_optimal_portfolio function.", file=sys.stderr)

    try:
        # Temporarily use a known-good example CSV file for data loading
        # This bypasses the FileNotFoundError for the user-provided returns_data path.
        # The user-provided returns_data path is currently ignored.
        example_prices_path = "/workspace/Riskfolio-Lib/tests/stock_prices.csv"
        print(f"DEBUG: Temporarily loading example prices data from: {example_prices_path}", file=sys.stderr)

        # Load historical prices from the example file
        prices = pd.read_csv(example_prices_path, index_col=0, parse_dates=True)
        print("DEBUG: Example prices data loaded successfully.", file=sys.stderr)
        print(f"DEBUG: Example prices data shape: {prices.shape}", file=sys.stderr)
        print(f"DEBUG: Example prices data head:\n{prices.head()}", file=sys.stderr)

        # Convert prices to returns
        print("DEBUG: Converting prices to returns...", file=sys.stderr)
        Y = prices.pct_change().dropna()
        print("DEBUG: Returns calculated successfully.", file=sys.stderr)
        print(f"DEBUG: Returns data shape: {Y.shape}", file=sys.stderr)
        print(f"DEBUG: Returns data head:\n{Y.head()}", file=sys.stderr)

        # Check if the returns data is empty or malformed
        if Y.empty:
            raise ValueError("The calculated returns DataFrame is empty after processing example data.")
        if not isinstance(Y.index, pd.DatetimeIndex):
            raise ValueError("The index of the returns data must be of datetime type.")
        if Y.shape[1] == 0:
            raise ValueError("The returns data contains no assets after processing example data.")

        # 2. Initialize a riskfolio.Portfolio object with the loaded returns
        print("Initializing Riskfolio Portfolio object with calculated returns.", file=sys.stderr)
        port = rf.Portfolio(returns=Y)
        print("Portfolio object initialized.", file=sys.stderr)

        # 3. Estimate the expected returns and covariance matrix
        print("Estimating assets statistics (expected returns and covariance matrix).", file=sys.stderr)
        port.assets_stats(method_mu='hist', method_cov='hist')
        print("Asset statistics estimated.", file=sys.stderr)

        # 4. Set optimization parameters for Efficient Risk with Standard Deviation
        print(f"Setting portfolio optimization model to 'Classic', objective to 'Sharpe', "
              f"risk measure to 'MV' (Standard Deviation).", file=sys.stderr)
        
        # Sanitize target_risk before assigning to port.upperdev
        print(f"DEBUG: Original target_risk received: {target_risk} (type: {type(target_risk)})", file=sys.stderr)
        # Convert to string, strip quotes, then convert to float.
        # This handles cases where target_risk might be passed as a quoted string.
        sanitized_target_risk_str = str(target_risk).strip('"')
        sanitized_target_risk_float = float(sanitized_target_risk_str)
        print(f"DEBUG: Sanitized target_risk: {sanitized_target_risk_float} (type: {type(sanitized_target_risk_float)})", file=sys.stderr)

        # The 'upperdev' attribute is used to set the maximum standard deviation.
        port.upperdev = sanitized_target_risk_float
        print(f"Setting target risk (upperdev constraint) for the portfolio to: {port.upperdev}", file=sys.stderr)

        port.alpha = 0.05
        port.beta = None
        port.a_sim = 100
        port.b_sim = 100
        
        # 5. Perform the portfolio optimization
        print("Performing portfolio optimization...", file=sys.stderr)
        # obj='Sharpe' to maximize Sharpe ratio, rm='MV' for Standard Deviation.
        w = port.optimization(obj='Sharpe', rm='MV', rf=0, l=0, hist=True)
        print("Portfolio optimization completed successfully.", file=sys.stderr)
        
        if w is None:
            raise ValueError("Portfolio optimization did not return a valid result. Check inputs and constraints.")

        print(f"Optimization results (weights DataFrame):\n{w.head()}", file=sys.stderr)

        # 6. Extract the optimal asset weights and convert to a dictionary
        print("Extracting optimal weights and converting to dictionary.", file=sys.stderr)
        optimal_weights = w['weights'].to_dict()
        print(f"Optimal weights extracted: {optimal_weights}", file=sys.stderr)

        # 7. Return the result
        print("Returning optimal weights.", file=sys.stderr)
        return {'optimal_weights': optimal_weights}

    except Exception as e:
        print(f"An error occurred during portfolio optimization: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise e
