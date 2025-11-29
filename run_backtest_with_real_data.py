"""
Run Backtests with Real Historical Data

This script runs backtests using real historical data either from:
1. Saved CSV files (faster, recommended)
2. Direct broker API (requires authentication)
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import yaml
from logger import logger
import logging

logger.setLevel(logging.INFO)

from backtesting.survivor_backtest import SurvivorBacktest
from backtesting.wave_backtest import WaveBacktest
from backtesting.weekly_analysis import WeeklyAnalyzer
from brokers import BrokerGateway


def load_data_from_csv(filepath: str) -> pd.DataFrame:
    """
    Load historical data from CSV file

    Args:
        filepath: Path to CSV file

    Returns:
        DataFrame with OHLC data
    """
    try:
        logger.info(f"Loading data from: {filepath}")
        df = pd.read_csv(filepath, parse_dates=['timestamp'])

        logger.info(f"Loaded {len(df)} data points")
        logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        logger.info(f"Price range: ₹{df['close'].min():.2f} to ₹{df['close'].max():.2f}")

        return df

    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        return pd.DataFrame()


def load_data_from_broker(symbol: str, start_date: str, end_date: str, interval: str = "5minute") -> pd.DataFrame:
    """
    Load historical data directly from broker API

    Args:
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Data interval

    Returns:
        DataFrame with OHLC data
    """
    try:
        broker_name = os.getenv("BROKER_NAME", "zerodha")
        logger.info(f"Fetching data from broker: {broker_name}")
        logger.info(f"Symbol: {symbol}, Interval: {interval}")

        broker = BrokerGateway.from_name(broker_name)
        data = broker.get_history(symbol, interval, start_date, end_date)

        if not data:
            logger.error("No data returned from broker")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Ensure timestamp column
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        elif 'ts' in df.columns:
            df['timestamp'] = pd.to_datetime(df['ts'], unit='s', errors='coerce')
            df = df.drop('ts', axis=1)

        df = df.sort_values('timestamp')

        logger.info(f"Fetched {len(df)} data points")
        logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

        return df

    except Exception as e:
        logger.error(f"Error fetching from broker: {e}", exc_info=True)
        return pd.DataFrame()


def run_survivor_backtest_with_real_data(
    data_source: str = "csv",
    csv_file: str = None,
    start_date: str = "2024-09-01",
    end_date: str = "2024-11-29"
):
    """
    Run Survivor strategy backtest with real data

    Args:
        data_source: "csv" or "broker"
        csv_file: Path to CSV file (if using CSV)
        start_date: Start date for backtest
        end_date: End date for backtest
    """
    logger.info("\n" + "="*80)
    logger.info("SURVIVOR STRATEGY BACKTEST - REAL DATA")
    logger.info("="*80)

    # Load configuration
    config_file = "strategy/configs/survivor.yml"
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['default']

    # Adjust for backtest
    config['pe_gap'] = 25
    config['ce_gap'] = 25
    config['pe_quantity'] = 50
    config['ce_quantity'] = 50

    logger.info(f"Configuration: PE Gap={config['pe_gap']}, CE Gap={config['ce_gap']}")

    # Data fetcher function
    def data_fetcher(sym, start, end):
        if data_source == "csv":
            if csv_file and os.path.exists(csv_file):
                df = load_data_from_csv(csv_file)
                # Filter by date range
                df = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]
                return df
            else:
                logger.error(f"CSV file not found: {csv_file}")
                return pd.DataFrame()
        else:  # broker
            return load_data_from_broker(sym, start, end, interval="5minute")

    # Create backtester
    backtester = SurvivorBacktest(
        config=config,
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000000,
        index_data_source=data_fetcher
    )

    # Run backtest
    logger.info("\nExecuting backtest...")
    results = backtester.run()

    if not results or results.get('trades') is None:
        logger.error("Backtest failed or produced no results")
        return None

    # Generate reports
    logger.info("\nGenerating reports...")
    os.makedirs('backtest_results/survivor_real', exist_ok=True)
    backtester.generate_report(save_dir='backtest_results/survivor_real')

    # Weekly analysis
    if len(backtester.broker.trades) > 0:
        logger.info("\nGenerating weekly analysis...")
        trades_df = pd.DataFrame(backtester.broker.trades)
        equity_df = pd.DataFrame(backtester.equity_curve)

        analyzer = WeeklyAnalyzer(trades_df, equity_df)
        weekly_metrics = analyzer.calculate_weekly_metrics()

        # Save weekly report
        weekly_report = analyzer.generate_weekly_report(
            save_path='backtest_results/survivor_real/survivor_weekly_report.txt'
        )
        print(weekly_report)

        # Generate weekly plots
        analyzer.plot_weekly_analysis(
            weekly_metrics,
            save_path='backtest_results/survivor_real/survivor_weekly_analysis.png'
        )

    return results


def run_wave_backtest_with_real_data(
    data_source: str = "csv",
    csv_file: str = None,
    start_date: str = "2024-10-01",
    end_date: str = "2024-11-29"
):
    """
    Run Wave strategy backtest with real data

    Args:
        data_source: "csv" or "broker"
        csv_file: Path to CSV file (if using CSV)
        start_date: Start date for backtest
        end_date: End date for backtest
    """
    logger.info("\n" + "="*80)
    logger.info("WAVE STRATEGY BACKTEST - REAL DATA")
    logger.info("="*80)

    # Load configuration
    config_file = "strategy/configs/wave.yml"
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['default']

    # Adjust for backtest
    config['buy_gap'] = 30
    config['sell_gap'] = 30
    config['buy_quantity'] = 50
    config['sell_quantity'] = 50

    logger.info(f"Configuration: Buy Gap={config['buy_gap']}, Sell Gap={config['sell_gap']}")

    # Data fetcher function
    def data_fetcher(sym, start, end):
        if data_source == "csv":
            if csv_file and os.path.exists(csv_file):
                df = load_data_from_csv(csv_file)
                # Filter by date range
                df = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]
                return df
            else:
                logger.error(f"CSV file not found: {csv_file}")
                return pd.DataFrame()
        else:  # broker
            return load_data_from_broker(sym, start, end, interval="1minute")

    # Create backtester
    backtester = WaveBacktest(
        config=config,
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000000,
        futures_data_source=data_fetcher
    )

    # Run backtest
    logger.info("\nExecuting backtest...")
    results = backtester.run()

    if not results or results.get('trades') is None:
        logger.error("Backtest failed or produced no results")
        return None

    # Generate reports
    logger.info("\nGenerating reports...")
    os.makedirs('backtest_results/wave_real', exist_ok=True)
    backtester.generate_report(save_dir='backtest_results/wave_real')

    # Weekly analysis
    if len(backtester.broker.trades) > 0:
        logger.info("\nGenerating weekly analysis...")
        trades_df = pd.DataFrame(backtester.broker.trades)
        equity_df = pd.DataFrame(backtester.equity_curve)

        analyzer = WeeklyAnalyzer(trades_df, equity_df)
        weekly_metrics = analyzer.calculate_weekly_metrics()

        # Save weekly report
        weekly_report = analyzer.generate_weekly_report(
            save_path='backtest_results/wave_real/wave_weekly_report.txt'
        )
        print(weekly_report)

        # Generate weekly plots
        analyzer.plot_weekly_analysis(
            weekly_metrics,
            save_path='backtest_results/wave_real/wave_weekly_analysis.png'
        )

    return results


def main():
    """Main execution"""

    logger.info("="*80)
    logger.info("BACKTEST WITH REAL HISTORICAL DATA")
    logger.info("="*80)

    # Check for data sources
    use_csv = False
    survivor_csv = "historical_data/NSE_NIFTY_50_5minute_2024-09-01_to_2024-11-29.csv"
    wave_csv = "historical_data/NFO_NIFTY25DECFUT_1minute_2024-10-01_to_2024-11-29.csv"

    if os.path.exists(survivor_csv):
        logger.info(f"✅ Found CSV data for Survivor: {survivor_csv}")
        use_csv_survivor = True
    else:
        logger.info(f"⚠️  CSV not found for Survivor, will attempt broker API")
        use_csv_survivor = False

    if os.path.exists(wave_csv):
        logger.info(f"✅ Found CSV data for Wave: {wave_csv}")
        use_csv_wave = True
    else:
        logger.info(f"⚠️  CSV not found for Wave, will attempt broker API")
        use_csv_wave = False

    logger.info("\nTIP: Run download_historical_data.py first to download and save data")
    logger.info("")

    # Run Survivor backtest
    try:
        survivor_results = run_survivor_backtest_with_real_data(
            data_source="csv" if use_csv_survivor else "broker",
            csv_file=survivor_csv if use_csv_survivor else None,
            start_date="2024-09-01",
            end_date="2024-11-29"
        )
    except Exception as e:
        logger.error(f"Survivor backtest failed: {e}", exc_info=True)
        survivor_results = None

    # Run Wave backtest
    try:
        wave_results = run_wave_backtest_with_real_data(
            data_source="csv" if use_csv_wave else "broker",
            csv_file=wave_csv if use_csv_wave else None,
            start_date="2024-10-01",
            end_date="2024-11-29"
        )
    except Exception as e:
        logger.error(f"Wave backtest failed: {e}", exc_info=True)
        wave_results = None

    # Summary
    logger.info("\n" + "="*80)
    logger.info("BACKTEST COMPLETE")
    logger.info("="*80)
    logger.info("\nResults saved to:")
    logger.info("  📁 backtest_results/survivor_real/")
    logger.info("     - survivor_backtest_report.txt")
    logger.info("     - survivor_weekly_report.txt (NEW!)")
    logger.info("     - survivor_weekly_analysis.png (NEW!)")
    logger.info("     - survivor_metrics.json")
    logger.info("     - survivor_trades.csv")
    logger.info("     - survivor_analysis.png")
    logger.info("\n  📁 backtest_results/wave_real/")
    logger.info("     - wave_backtest_report.txt")
    logger.info("     - wave_weekly_report.txt (NEW!)")
    logger.info("     - wave_weekly_analysis.png (NEW!)")
    logger.info("     - wave_metrics.json")
    logger.info("     - wave_trades.csv")
    logger.info("     - wave_analysis.png")
    logger.info("="*80)


if __name__ == "__main__":
    main()
