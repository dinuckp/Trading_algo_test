"""
Example: Backtesting Survivor Strategy

This script demonstrates how to backtest the Survivor options trading strategy
using historical NIFTY data.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml
from logger import logger
from backtesting.survivor_backtest import SurvivorBacktest


def generate_synthetic_nifty_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Generate synthetic NIFTY index data for backtesting

    In production, replace this with actual historical data from your broker API.
    """
    logger.info("Generating synthetic NIFTY data for demonstration...")

    # Create date range (1-minute bars)
    dates = pd.date_range(start_date, end_date, freq='5min')

    # Generate realistic-looking NIFTY price movements
    np.random.seed(42)

    # Base price around 24,500
    base_price = 24500

    # Generate random walk with drift
    returns = np.random.normal(0.0001, 0.003, len(dates))  # Small drift, moderate volatility
    prices = base_price * np.exp(np.cumsum(returns))

    # Add some intraday patterns (higher volatility during market hours)
    hours = pd.Series([d.hour for d in dates])
    volatility_multiplier = 1 + 0.5 * ((hours >= 9) & (hours <= 15)).astype(float)
    prices = prices * (1 + np.random.normal(0, 0.001, len(dates)) * volatility_multiplier)

    # Create OHLC data
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices * (1 + np.abs(np.random.normal(0, 0.001, len(dates)))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.001, len(dates)))),
        'close': prices,
        'volume': np.random.randint(100000, 1000000, len(dates))
    })

    logger.info(f"Generated {len(df)} data points from {start_date} to {end_date}")
    return df


def fetch_historical_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch historical data for backtesting

    Args:
        symbol: Trading symbol (e.g., 'NSE:NIFTY 50')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLC data
    """
    # Option 1: Use broker API (recommended for production)
    # Example:
    # from brokers import BrokerGateway
    # broker = BrokerGateway.from_name("zerodha")
    # data = broker.get_history(symbol, "5minute", start_date, end_date)
    # return pd.DataFrame(data)

    # Option 2: Load from CSV file
    # return pd.read_csv('historical_nifty_data.csv', parse_dates=['timestamp'])

    # Option 3: Generate synthetic data (for demonstration)
    return generate_synthetic_nifty_data(start_date, end_date)


def main():
    """
    Main backtesting script
    """
    logger.info("="*80)
    logger.info("SURVIVOR STRATEGY BACKTEST")
    logger.info("="*80)

    # Configuration
    # Load from YAML or define here
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "strategy/configs/survivor.yml")

    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)['default']
        logger.info("Loaded configuration from survivor.yml")
    else:
        # Fallback configuration
        config = {
            'index_symbol': 'NSE:NIFTY 50',
            'symbol_initials': 'NIFTY25JAN',
            'pe_gap': 20,
            'ce_gap': 20,
            'pe_quantity': 75,
            'ce_quantity': 75,
            'pe_symbol_gap': 200,
            'ce_symbol_gap': 200,
            'min_price_to_sell': 15,
            'sell_multiplier_threshold': 5,
            'pe_reset_gap': 30,
            'ce_reset_gap': 30,
            'pe_start_point': 0,
            'ce_start_point': 0
        }
        logger.info("Using fallback configuration")

    # Backtest parameters
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    initial_capital = 1000000  # ₹10 lakhs

    logger.info(f"Backtest period: {start_date} to {end_date}")
    logger.info(f"Initial capital: ₹{initial_capital:,.2f}")

    # Create backtester
    backtester = SurvivorBacktest(
        config=config,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        index_data_source=fetch_historical_data
    )

    # Run backtest
    logger.info("\nRunning backtest...")
    results = backtester.run()

    # Generate and display results
    logger.info("\nGenerating reports...")
    backtester.generate_report(save_dir='backtest_results/survivor')

    logger.info("\n" + "="*80)
    logger.info("BACKTEST COMPLETE")
    logger.info("="*80)
    logger.info("Results saved to: backtest_results/survivor/")
    logger.info("  - survivor_backtest_report.txt (detailed report)")
    logger.info("  - survivor_metrics.json (metrics in JSON format)")
    logger.info("  - survivor_trades.csv (trade log)")
    logger.info("  - survivor_analysis.png (performance charts)")


if __name__ == "__main__":
    import logging
    logger.setLevel(logging.INFO)
    main()
