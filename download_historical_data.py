"""
Download Historical Data from Broker

This script downloads real historical data from your broker and saves it
to CSV files for backtesting.
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from logger import logger
import logging
from brokers import BrokerGateway

logger.setLevel(logging.INFO)


def download_and_save_data(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "5minute",
    broker_name: str = None,
    save_dir: str = "historical_data"
):
    """
    Download historical data and save to CSV

    Args:
        symbol: Trading symbol (e.g., "NSE:NIFTY 50", "NFO:NIFTY25JANFUT")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        interval: Data interval (1minute, 5minute, 15minute, 60minute, day)
        broker_name: Broker to use (default from .env)
        save_dir: Directory to save CSV files
    """
    try:
        # Get broker name from environment if not provided
        if broker_name is None:
            broker_name = os.getenv("BROKER_NAME", "zerodha")

        logger.info(f"Downloading data for {symbol} from {start_date} to {end_date}")
        logger.info(f"Using broker: {broker_name}")
        logger.info(f"Interval: {interval}")

        # Initialize broker
        broker = BrokerGateway.from_name(broker_name)

        # Download data
        logger.info("Fetching data from broker...")
        data = broker.get_history(symbol, interval, start_date, end_date)

        if not data:
            logger.error(f"No data returned for {symbol}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(data)

        logger.info(f"Downloaded {len(df)} data points")

        # Ensure timestamp column
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        elif 'ts' in df.columns:
            df['timestamp'] = pd.to_datetime(df['ts'], unit='s', errors='coerce')
            df = df.drop('ts', axis=1)

        # Ensure required columns
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logger.warning(f"Missing columns: {missing_cols}")
            logger.info(f"Available columns: {df.columns.tolist()}")

        # Sort by timestamp
        df = df.sort_values('timestamp')

        # Create save directory
        os.makedirs(save_dir, exist_ok=True)

        # Create filename
        symbol_clean = symbol.replace(":", "_").replace(" ", "_")
        filename = f"{symbol_clean}_{interval}_{start_date}_to_{end_date}.csv"
        filepath = os.path.join(save_dir, filename)

        # Save to CSV
        df.to_csv(filepath, index=False)

        logger.info(f"✅ Data saved to: {filepath}")
        logger.info(f"   Rows: {len(df)}")
        logger.info(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        logger.info(f"   Price range: ₹{df['close'].min():.2f} to ₹{df['close'].max():.2f}")

        return filepath

    except Exception as e:
        logger.error(f"Error downloading data: {e}", exc_info=True)
        return None


def main():
    """Download data for common symbols"""

    logger.info("="*80)
    logger.info("HISTORICAL DATA DOWNLOAD")
    logger.info("="*80)

    # Check for .env file
    if not os.path.exists('.env'):
        logger.error("No .env file found! Please configure broker credentials.")
        logger.info("Copy .sample.env to .env and fill in your broker details.")
        return

    # Download configurations
    downloads = [
        {
            'symbol': 'NSE:NIFTY 50',
            'start_date': '2024-09-01',
            'end_date': '2024-11-29',
            'interval': '5minute',
            'description': 'NIFTY Index (for Survivor strategy)'
        },
        {
            'symbol': 'NSE:NIFTY BANK',
            'start_date': '2024-10-01',
            'end_date': '2024-11-29',
            'interval': '5minute',
            'description': 'Bank NIFTY Index'
        },
        # Add more as needed
    ]

    # Try to download futures data (symbol may vary by expiry)
    # You'll need to update this with the current month's contract
    logger.info("\n" + "="*80)
    logger.info("NOTE: For futures data, update the contract symbol to current month")
    logger.info("Example: NIFTY25DECFUT, NIFTY25JANFUT, etc.")
    logger.info("="*80 + "\n")

    successful = 0
    failed = 0

    for config in downloads:
        logger.info(f"\nDownloading: {config['description']}")
        logger.info("-"*80)

        result = download_and_save_data(
            symbol=config['symbol'],
            start_date=config['start_date'],
            end_date=config['end_date'],
            interval=config['interval']
        )

        if result:
            successful += 1
        else:
            failed += 1

        logger.info("")

    # Summary
    logger.info("="*80)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("="*80)
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"\nData saved to: historical_data/")
    logger.info("="*80)

    if successful > 0:
        logger.info("\n✅ You can now run backtests with real data!")
        logger.info("   Use: python run_backtest_with_real_data.py")


if __name__ == "__main__":
    main()
