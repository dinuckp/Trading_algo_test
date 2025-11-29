"""
Run Backtests with Historical Data

This script runs backtests for both Survivor and Wave strategies using
real historical data from the broker.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml
from logger import logger
import logging

# Set logging level
logger.setLevel(logging.INFO)

from backtesting.survivor_backtest import SurvivorBacktest
from backtesting.wave_backtest import WaveBacktest
from brokers import BrokerGateway


def fetch_historical_data_from_broker(symbol: str, start_date: str, end_date: str, interval: str = "5minute"):
    """
    Fetch historical data from broker API

    Args:
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Data interval (1minute, 5minute, 15minute, 60minute, day)

    Returns:
        DataFrame with OHLC data
    """
    try:
        logger.info(f"Fetching historical data for {symbol} from {start_date} to {end_date}")

        # Initialize broker
        broker_name = os.getenv("BROKER_NAME", "zerodha")
        logger.info(f"Using broker: {broker_name}")

        broker = BrokerGateway.from_name(broker_name)

        # Fetch historical data
        data = broker.get_history(symbol, interval, start_date, end_date)

        if not data:
            logger.warning(f"No data returned from broker for {symbol}")
            return pd.DataFrame()

        # Convert to DataFrame if it's a list
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = data

        # Ensure required columns exist
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required columns. Available: {df.columns.tolist()}")
            return pd.DataFrame()

        # Convert timestamp to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        logger.info(f"Fetched {len(df)} data points for {symbol}")
        logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        logger.info(f"Price range: ₹{df['close'].min():.2f} to ₹{df['close'].max():.2f}")

        return df

    except Exception as e:
        logger.error(f"Error fetching historical data: {e}", exc_info=True)
        logger.warning("Falling back to synthetic data generation")
        return None


def generate_realistic_synthetic_data(symbol: str, start_date: str, end_date: str, base_price: float = 24500):
    """
    Generate realistic synthetic data as fallback

    This creates more realistic price movements than random walk.
    """
    logger.info(f"Generating realistic synthetic data for {symbol}")

    # Determine frequency based on date range
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    days_diff = (end - start).days

    if days_diff <= 7:
        freq = '1min'
    elif days_diff <= 30:
        freq = '5min'
    else:
        freq = '15min'

    dates = pd.date_range(start_date, end_date, freq=freq)

    # Filter to market hours (9:15 AM to 3:30 PM, weekdays only)
    dates = dates[dates.dayofweek < 5]  # Weekdays only
    dates = dates[(dates.hour >= 9) & (dates.hour < 16)]
    dates = dates[~((dates.hour == 9) & (dates.minute < 15))]  # After 9:15 AM
    dates = dates[~((dates.hour == 15) & (dates.minute > 30))]  # Before 3:30 PM

    n = len(dates)
    np.random.seed(42)

    # Generate realistic price movements
    # Combination of trend, mean reversion, and noise

    # 1. Long-term trend (slight upward bias)
    trend = np.linspace(0, 100, n)

    # 2. Mean reversion component (oscillation around base price)
    cycle_fast = np.sin(np.linspace(0, 20 * np.pi, n)) * 50
    cycle_slow = np.sin(np.linspace(0, 5 * np.pi, n)) * 100

    # 3. Random walk component
    random_walk = np.cumsum(np.random.normal(0, 15, n))

    # 4. Volatility clustering (GARCH-like)
    volatility = 1 + 0.5 * np.abs(np.sin(np.linspace(0, 10 * np.pi, n)))
    noise = np.random.normal(0, 10, n) * volatility

    # Combine components
    close_prices = base_price + trend + cycle_fast + cycle_slow + random_walk + noise

    # Generate OHLC from close prices
    high_low_range = np.random.uniform(10, 40, n) * volatility

    df = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices + np.random.normal(0, 5, n),
        'high': close_prices + high_low_range / 2,
        'low': close_prices - high_low_range / 2,
        'close': close_prices,
        'volume': np.random.randint(100000, 1000000, n)
    })

    # Ensure high >= low, high >= close, high >= open
    df['high'] = df[['high', 'low', 'close', 'open']].max(axis=1)
    df['low'] = df[['low', 'close', 'open']].min(axis=1)

    logger.info(f"Generated {len(df)} synthetic data points")
    logger.info(f"Price range: ₹{df['close'].min():.2f} to ₹{df['close'].max():.2f}")

    return df


def run_survivor_backtest():
    """
    Run Survivor strategy backtest
    """
    logger.info("\n" + "="*80)
    logger.info("RUNNING SURVIVOR STRATEGY BACKTEST")
    logger.info("="*80)

    # Load configuration
    config_file = "strategy/configs/survivor.yml"
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['default']

    # Adjust configuration for backtesting
    config['pe_gap'] = 25
    config['ce_gap'] = 25
    config['pe_quantity'] = 50
    config['ce_quantity'] = 50
    config['min_price_to_sell'] = 10

    logger.info(f"Configuration: PE Gap={config['pe_gap']}, CE Gap={config['ce_gap']}")

    # Define backtest period (last 3 months)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    logger.info(f"Backtest period: {start_str} to {end_str}")

    # Fetch historical data
    symbol = config.get('index_symbol', 'NSE:NIFTY 50')

    def data_fetcher(sym, start, end):
        # Try to fetch from broker
        df = fetch_historical_data_from_broker(sym, start, end, interval="5minute")

        # If broker fetch fails, use synthetic data
        if df is None or df.empty:
            logger.warning("Using synthetic data for Survivor backtest")
            df = generate_realistic_synthetic_data(sym, start, end, base_price=24500)

        return df

    # Create backtester
    backtester = SurvivorBacktest(
        config=config,
        start_date=start_str,
        end_date=end_str,
        initial_capital=1000000,
        index_data_source=data_fetcher
    )

    # Run backtest
    logger.info("\nExecuting backtest...")
    results = backtester.run()

    # Generate reports
    logger.info("\nGenerating reports...")
    os.makedirs('backtest_results/survivor', exist_ok=True)
    backtester.generate_report(save_dir='backtest_results/survivor')

    return results


def run_wave_backtest():
    """
    Run Wave strategy backtest
    """
    logger.info("\n" + "="*80)
    logger.info("RUNNING WAVE STRATEGY BACKTEST")
    logger.info("="*80)

    # Load configuration
    config_file = "strategy/configs/wave.yml"
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['default']

    # Adjust configuration for backtesting
    config['buy_gap'] = 30
    config['sell_gap'] = 30
    config['buy_quantity'] = 50
    config['sell_quantity'] = 50

    logger.info(f"Configuration: Buy Gap={config['buy_gap']}, Sell Gap={config['sell_gap']}")

    # Define backtest period (last month for faster execution)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    logger.info(f"Backtest period: {start_str} to {end_str}")

    # For Wave, we need futures data
    # Try NIFTY futures symbol - format varies by broker
    symbol = config.get('symbol_name', 'NIFTY25JANFUT')

    def data_fetcher(sym, start, end):
        # Try to fetch from broker
        df = fetch_historical_data_from_broker(sym, start, end, interval="1minute")

        # If broker fetch fails, use synthetic data
        if df is None or df.empty:
            logger.warning("Using synthetic data for Wave backtest")
            df = generate_realistic_synthetic_data(sym, start, end, base_price=24500)

        return df

    # Create backtester
    backtester = WaveBacktest(
        config=config,
        start_date=start_str,
        end_date=end_str,
        initial_capital=1000000,
        futures_data_source=data_fetcher
    )

    # Run backtest
    logger.info("\nExecuting backtest...")
    results = backtester.run()

    # Generate reports
    logger.info("\nGenerating reports...")
    os.makedirs('backtest_results/wave', exist_ok=True)
    backtester.generate_report(save_dir='backtest_results/wave')

    return results


def print_comparison(survivor_results, wave_results):
    """
    Print side-by-side comparison of both strategies
    """
    print("\n" + "="*100)
    print("STRATEGY COMPARISON")
    print("="*100)

    survivor_metrics = survivor_results.get('metrics', {})
    wave_metrics = wave_results.get('metrics', {})

    print(f"\n{'Metric':<30} {'Survivor':<30} {'Wave':<30}")
    print("-"*100)

    metrics_to_compare = [
        ('Initial Capital', 'initial_capital', '₹{:,.2f}'),
        ('Final Capital', 'final_capital', '₹{:,.2f}'),
        ('Total Return', 'total_return_pct', '{:.2f}%'),
        ('Max Drawdown', 'max_drawdown_pct', '{:.2f}%'),
        ('Sharpe Ratio', 'sharpe_ratio', '{:.2f}'),
        ('Total Trades', 'total_trades', '{:,}'),
        ('Win Rate', 'win_rate_pct', '{:.2f}%'),
        ('Profit Factor', 'profit_factor', '{:.2f}'),
    ]

    for label, key, fmt in metrics_to_compare:
        survivor_val = survivor_metrics.get(key, 0)
        wave_val = wave_metrics.get(key, 0)

        print(f"{label:<30} {fmt.format(survivor_val):<30} {fmt.format(wave_val):<30}")

    print("="*100)


def main():
    """
    Main execution function
    """
    logger.info("\n" + "="*100)
    logger.info("ALGORITHMIC TRADING BACKTEST - HISTORICAL DATA")
    logger.info("="*100)
    logger.info(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*100)

    # Check if .env file exists
    if not os.path.exists('.env'):
        logger.warning("No .env file found. Broker connection may fail.")
        logger.info("Will use synthetic data as fallback.")

    try:
        # Run Survivor backtest
        survivor_results = run_survivor_backtest()

        # Run Wave backtest
        wave_results = run_wave_backtest()

        # Print comparison
        print_comparison(survivor_results, wave_results)

        logger.info("\n" + "="*100)
        logger.info("BACKTEST EXECUTION COMPLETE")
        logger.info("="*100)
        logger.info("\nResults saved to:")
        logger.info("  📁 backtest_results/survivor/")
        logger.info("     - survivor_backtest_report.txt")
        logger.info("     - survivor_metrics.json")
        logger.info("     - survivor_trades.csv")
        logger.info("     - survivor_analysis.png")
        logger.info("\n  📁 backtest_results/wave/")
        logger.info("     - wave_backtest_report.txt")
        logger.info("     - wave_metrics.json")
        logger.info("     - wave_trades.csv")
        logger.info("     - wave_analysis.png")
        logger.info("="*100)

    except Exception as e:
        logger.error(f"\nBacktest execution failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
