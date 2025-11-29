"""
Example: Backtesting Wave Strategy

This script demonstrates how to backtest the Wave market-making strategy
using historical futures data.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml
from logger import logger
from backtesting.wave_backtest import WaveBacktest


def generate_synthetic_futures_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Generate synthetic NIFTY futures data for backtesting

    In production, replace this with actual historical data from your broker API.
    """
    logger.info("Generating synthetic futures data for demonstration...")

    # Create date range (1-minute bars)
    dates = pd.date_range(start_date, end_date, freq='1min')

    # Generate realistic-looking futures price movements
    np.random.seed(42)

    # Base price around 24,500
    base_price = 24500

    # Generate mean-reverting price with oscillations (suitable for wave strategy)
    # This simulates a choppy market
    time_index = np.arange(len(dates))

    # Multiple oscillating components
    trend = np.sin(time_index / 1000) * 100  # Slow wave
    noise = np.random.normal(0, 10, len(dates))  # Random noise
    fast_oscillation = np.sin(time_index / 50) * 30  # Fast oscillations

    prices = base_price + trend + fast_oscillation + noise

    # Add some volatility clustering
    volatility = 1 + 0.5 * np.abs(np.sin(time_index / 500))
    prices = prices * volatility

    # Create OHLC data
    high_low_spread = np.random.uniform(5, 20, len(dates))

    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices + high_low_spread / 2,
        'low': prices - high_low_spread / 2,
        'close': prices + np.random.normal(0, 2, len(dates)),
        'volume': np.random.randint(50000, 500000, len(dates))
    })

    logger.info(f"Generated {len(df)} data points from {start_date} to {end_date}")
    return df


def fetch_futures_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch historical futures data for backtesting

    Args:
        symbol: Trading symbol (e.g., 'NIFTY25SEPFUT')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLC data
    """
    # Option 1: Use broker API (recommended for production)
    # Example:
    # from brokers import BrokerGateway
    # broker = BrokerGateway.from_name("zerodha")
    # data = broker.get_history(symbol, "1minute", start_date, end_date)
    # return pd.DataFrame(data)

    # Option 2: Load from CSV file
    # return pd.read_csv('historical_futures_data.csv', parse_dates=['timestamp'])

    # Option 3: Generate synthetic data (for demonstration)
    return generate_synthetic_futures_data(start_date, end_date)


def main():
    """
    Main backtesting script
    """
    logger.info("="*80)
    logger.info("WAVE STRATEGY BACKTEST")
    logger.info("="*80)

    # Configuration
    # Load from YAML or define here
    config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "strategy/configs/wave.yml")

    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)['default']
        logger.info("Loaded configuration from wave.yml")
    else:
        # Fallback configuration
        config = {
            'symbol_name': 'NIFTY25SEPFUT',
            'exchange': 'NFO',
            'buy_gap': 25,
            'sell_gap': 25,
            'buy_quantity': 75,
            'sell_quantity': 75,
            'lot_size': 75,
            'cool_off_time': 10,
            'product_type': 'NRML',
            'order_type': 'LIMIT',
            'variety': 'REGULAR',
            'tag': 'WaveScraper'
        }
        logger.info("Using fallback configuration")

    # Backtest parameters
    start_date = "2024-09-01"
    end_date = "2024-09-30"
    initial_capital = 1000000  # ₹10 lakhs

    logger.info(f"Backtest period: {start_date} to {end_date}")
    logger.info(f"Initial capital: ₹{initial_capital:,.2f}")
    logger.info(f"Symbol: {config['symbol_name']}")
    logger.info(f"Buy Gap: {config['buy_gap']}, Sell Gap: {config['sell_gap']}")

    # Create backtester
    backtester = WaveBacktest(
        config=config,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        futures_data_source=fetch_futures_data
    )

    # Run backtest
    logger.info("\nRunning backtest...")
    results = backtester.run()

    # Generate and display results
    logger.info("\nGenerating reports...")
    backtester.generate_report(save_dir='backtest_results/wave')

    logger.info("\n" + "="*80)
    logger.info("BACKTEST COMPLETE")
    logger.info("="*80)
    logger.info("Results saved to: backtest_results/wave/")
    logger.info("  - wave_backtest_report.txt (detailed report)")
    logger.info("  - wave_metrics.json (metrics in JSON format)")
    logger.info("  - wave_trades.csv (trade log)")
    logger.info("  - wave_analysis.png (performance charts)")


if __name__ == "__main__":
    import logging
    logger.setLevel(logging.INFO)
    main()
