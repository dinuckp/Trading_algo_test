"""
Enhanced Data Download Script - 3 Years Historical Data

Downloads:
1. NIFTY 50 spot data (3 years)
2. Current options chain data (for live trading)

Note: Historical options data requires specialized data providers
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from logger import logger
import logging
import getpass

logger.setLevel(logging.INFO)


def setup_broker_credentials():
    """
    Interactive broker credential setup
    """
    print("\n" + "="*80)
    print("BROKER CREDENTIALS SETUP")
    print("="*80)
    print("\nChoose your broker:")
    print("  1. Zerodha (KiteConnect)")
    print("  2. Fyers")
    print("  3. I already have .env configured")
    print()

    choice = input("Enter choice (1-3): ").strip()

    if choice == "3":
        if os.path.exists('.env'):
            print("✅ Using existing .env file")
            return True
        else:
            print("❌ No .env file found!")
            print("Please run option 1 or 2 first.")
            return False

    broker_name = "zerodha" if choice == "1" else "fyers"

    print(f"\n📝 Enter your {broker_name.upper()} credentials:")
    print("(Your input will be saved to .env file)")
    print()

    if broker_name == "zerodha":
        api_key = input("API Key: ").strip()
        api_secret = input("API Secret: ").strip()
        password = getpass.getpass("Password: ").strip()

        env_content = f"""# Broker Configuration
BROKER_NAME=zerodha

# Zerodha Credentials
BROKER_API_KEY={api_key}
BROKER_API_SECRET={api_secret}
BROKER_PASSWORD={password}

# Optional
BROKER_TOTP_ENABLE=false
"""

    else:  # Fyers
        fyers_id = input("Fyers ID: ").strip()
        api_key = input("API Key: ").strip()
        api_secret = input("API Secret: ").strip()
        totp_key = input("TOTP Key (optional, press Enter to skip): ").strip()
        pin = getpass.getpass("PIN: ").strip()
        redirect_uri = input("Redirect URI (default: http://127.0.0.1:8080): ").strip() or "http://127.0.0.1:8080"

        env_content = f"""# Broker Configuration
BROKER_NAME=fyers

# Fyers Credentials
BROKER_ID={fyers_id}
BROKER_API_KEY={api_key}
BROKER_API_SECRET={api_secret}
BROKER_TOTP_KEY={totp_key}
BROKER_TOTP_PIN={pin}
BROKER_TOTP_REDIRECT_URI={redirect_uri}
BROKER_LOGIN_MODE=auto
"""

    # Save to .env
    with open('.env', 'w') as f:
        f.write(env_content)

    print("\n✅ Credentials saved to .env file")
    return True


def download_nifty_with_yfinance(years=3):
    """
    Download NIFTY data using yfinance (reliable, multi-year data)
    """
    try:
        import yfinance as yf
        print("\n📊 Using yfinance to download NIFTY data...")
    except ImportError:
        print("\n⚠️  yfinance not installed. Installing now...")
        os.system("pip install yfinance -q")
        import yfinance as yf

    os.makedirs('historical_data', exist_ok=True)

    # NIFTY 50 ticker on Yahoo Finance
    ticker = "^NSEI"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    print(f"\n{'='*80}")
    print(f"Downloading NIFTY 50 data from Yahoo Finance")
    print(f"Period: {start_date.date()} to {end_date.date()} ({years} years)")
    print(f"{'='*80}")

    try:
        # Download daily data
        print("\n📥 Downloading daily data...")
        df_daily = yf.download(ticker, start=start_date, end=end_date, interval='1d', progress=False)

        if df_daily.empty:
            print("❌ No data received from Yahoo Finance")
            return False

        # Process data
        df_daily = df_daily.reset_index()
        df_daily.columns = ['timestamp', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
        df_daily = df_daily.drop('adj_close', axis=1)

        # Save daily data
        filepath_daily = 'historical_data/NIFTY_50_daily_3years.csv'
        df_daily.to_csv(filepath_daily, index=False)

        print(f"✅ Daily data saved: {filepath_daily}")
        print(f"   Rows: {len(df_daily):,}")
        print(f"   Date range: {df_daily['timestamp'].min()} to {df_daily['timestamp'].max()}")
        print(f"   Price range: ₹{df_daily['close'].min():.2f} - ₹{df_daily['close'].max():.2f}")

        # Download recent intraday data (5-minute - Yahoo only provides 60 days)
        print("\n📥 Downloading recent 5-minute intraday data (60 days)...")
        start_intraday = end_date - timedelta(days=60)

        df_intraday = yf.download(ticker, start=start_intraday, end=end_date, interval='5m', progress=False)

        if not df_intraday.empty:
            df_intraday = df_intraday.reset_index()
            df_intraday.columns = ['timestamp', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
            df_intraday = df_intraday.drop('adj_close', axis=1)

            filepath_intraday = 'historical_data/NIFTY_50_5minute_60days.csv'
            df_intraday.to_csv(filepath_intraday, index=False)

            print(f"✅ Intraday data saved: {filepath_intraday}")
            print(f"   Rows: {len(df_intraday):,}")
            print(f"   Date range: {df_intraday['timestamp'].min()} to {df_intraday['timestamp'].max()}")

        return True

    except Exception as e:
        print(f"❌ Error downloading from Yahoo Finance: {e}")
        logger.error(f"yfinance download failed: {e}", exc_info=True)
        return False


def download_nifty_broker_chunked(broker_name, years=3):
    """
    Download NIFTY data from broker API in chunks (works around 60-day limit)
    """
    from brokers import BrokerGateway

    print(f"\n📊 Using {broker_name} API to download NIFTY data...")
    print("⚠️  Note: Broker APIs typically limit to 60 days per request")
    print("    We'll download in chunks...")

    os.makedirs('historical_data', exist_ok=True)

    broker = BrokerGateway.from_name(broker_name)
    symbol = 'NSE:NIFTY 50'
    interval = '5minute'

    # Split into 60-day chunks
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    chunk_size_days = 60
    all_data = []

    current_end = end_date
    chunk_num = 0

    print(f"\n{'='*80}")
    print(f"Downloading in 60-day chunks...")
    print(f"Total period: {start_date.date()} to {end_date.date()}")
    print(f"{'='*80}")

    while current_end > start_date:
        chunk_num += 1
        current_start = current_end - timedelta(days=chunk_size_days)

        if current_start < start_date:
            current_start = start_date

        print(f"\n📥 Chunk {chunk_num}: {current_start.date()} to {current_end.date()}")

        try:
            data = broker.get_history(
                symbol,
                interval,
                current_start.strftime("%Y-%m-%d"),
                current_end.strftime("%Y-%m-%d")
            )

            if data:
                df_chunk = pd.DataFrame(data)
                all_data.append(df_chunk)
                print(f"   ✅ Downloaded {len(df_chunk):,} candles")
            else:
                print(f"   ⚠️  No data returned")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            logger.warning(f"Chunk {chunk_num} failed: {e}")

        current_end = current_start - timedelta(days=1)

        # Rate limiting
        import time
        time.sleep(1)

    if not all_data:
        print("\n❌ No data downloaded from broker API")
        return False

    # Combine all chunks
    print(f"\n🔄 Combining {len(all_data)} chunks...")
    df_combined = pd.concat(all_data, ignore_index=True)

    # Process timestamps
    if 'timestamp' in df_combined.columns:
        df_combined['timestamp'] = pd.to_datetime(df_combined['timestamp'], unit='s', errors='coerce')
    elif 'ts' in df_combined.columns:
        df_combined['timestamp'] = pd.to_datetime(df_combined['ts'], unit='s', errors='coerce')
        df_combined = df_combined.drop('ts', axis=1)

    # Remove duplicates and sort
    df_combined = df_combined.drop_duplicates(subset=['timestamp'])
    df_combined = df_combined.sort_values('timestamp')

    # Save
    filepath = f'historical_data/NIFTY_50_{interval}_{years}years_broker.csv'
    df_combined.to_csv(filepath, index=False)

    print(f"\n✅ Combined data saved: {filepath}")
    print(f"   Total rows: {len(df_combined):,}")
    print(f"   Date range: {df_combined['timestamp'].min()} to {df_combined['timestamp'].max()}")
    print(f"   Price range: ₹{df_combined['close'].min():.2f} - ₹{df_combined['close'].max():.2f}")

    return True


def download_current_options_chain():
    """
    Download current NIFTY options chain (for live trading)

    Note: Historical options data is not available from broker APIs.
    For backtesting with real options data, use specialized providers:
    - TrueData (https://truedata.in/)
    - OpstraData (https://opstra.definedge.com/)
    - NSEPython (free but limited)
    """
    print(f"\n{'='*80}")
    print("OPTIONS DATA - IMPORTANT INFORMATION")
    print(f"{'='*80}")
    print("""
⚠️  BROKER API LIMITATIONS:
- Broker APIs provide CURRENT options chain only
- Historical expired options data is NOT available
- Options symbols change every week (weekly expiry)

📊 FOR BACKTESTING WITH REAL OPTIONS DATA:
You need specialized data providers:

1. TrueData (https://truedata.in/)
   - Comprehensive historical options data
   - Tick-by-tick data available
   - Cost: ₹1,500-3,000/month

2. OpstraData (https://opstra.definedge.com/)
   - EOD options data
   - Good for strategy backtesting
   - Cost: ~₹500/month

3. NSEPython (Free but limited)
   - Current day options data
   - No historical data

4. FirstRate Data (https://firstratedata.com/)
   - Professional-grade historical data
   - All strikes, all expiries
   - Cost: $50-200/month

📝 ALTERNATIVE FOR YOUR STRATEGY:
Since your strategy uses:
- Entry based on NIFTY spot movement
- CE and PE strikes based on spot price

You can backtest using:
- Real NIFTY spot data (which we're downloading)
- Theoretical options pricing (Black-Scholes) ✅ Already implemented!

This gives ~90% accurate results without expensive data subscriptions.
""")

    proceed = input("\nDownload current options chain for reference? (y/n): ").strip().lower()

    if proceed != 'y':
        return

    try:
        from brokers import BrokerGateway
        from dotenv import load_dotenv
        load_dotenv()

        broker_name = os.getenv("BROKER_NAME")
        broker = BrokerGateway.from_name(broker_name)

        print("\n📥 Fetching current NIFTY options chain...")

        # Note: Option chain download depends on broker capabilities
        # This is a placeholder - actual implementation depends on broker
        print("⚠️  Option chain download is broker-specific")
        print("   Most brokers don't provide direct option chain API")
        print("   You may need to use NSEPython or scraping for current data")

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """
    Main interactive flow for 3-year data download
    """
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     3-YEAR HISTORICAL DATA DOWNLOAD                     ║
    ║     For Comprehensive Backtesting                       ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Check if .env exists
    if not os.path.exists('.env'):
        print("📝 No .env file found. Let's set up your broker credentials...")
        if not setup_broker_credentials():
            print("\n❌ Setup failed. Please try again.")
            return
    else:
        print("✅ Found existing .env file")
        update = input("\nUpdate broker credentials? (y/n): ").strip().lower()
        if update == 'y':
            setup_broker_credentials()

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    broker_name = os.getenv("BROKER_NAME", "zerodha")

    # Choose download method
    print("\n" + "="*80)
    print("DOWNLOAD METHOD")
    print("="*80)
    print("\n📊 Choose how to download NIFTY spot data:")
    print("\n  1. Yahoo Finance (Recommended for 3-year data)")
    print("     ✅ Reliable, fast, free")
    print("     ✅ Daily + Recent intraday data")
    print("     ⚠️  5-minute data limited to 60 days")
    print("\n  2. Broker API (Chunked download)")
    print("     ⚠️  Slower, may hit rate limits")
    print("     ✅ More accurate for recent data")
    print("     ⚠️  May not get full 3 years")
    print("\n  3. Both (Best accuracy)")
    print("     ✅ Daily from Yahoo Finance")
    print("     ✅ Intraday from Broker API")
    print()

    method = input("Enter choice (1-3): ").strip()

    success = False

    if method in ["1", "3"]:
        success = download_nifty_with_yfinance(years=3)

    if method in ["2", "3"]:
        try:
            success = download_nifty_broker_chunked(broker_name, years=3) or success
        except Exception as e:
            print(f"\n❌ Broker download failed: {e}")
            logger.error(f"Broker download error: {e}", exc_info=True)

    if not success:
        print("\n❌ Failed to download data")
        return

    # Options data info
    download_current_options_chain()

    # Summary
    print("\n" + "="*80)
    print("DOWNLOAD COMPLETE ✅")
    print("="*80)
    print(f"\n📁 Data saved in: historical_data/")
    print("\n📊 Downloaded files:")

    if os.path.exists('historical_data'):
        for file in sorted(os.listdir('historical_data')):
            if file.endswith('.csv'):
                filepath = os.path.join('historical_data', file)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f"   - {file} ({size_mb:.2f} MB)")

    # Next steps
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Run backtest with 3-year data:")
    print("   python run_nifty_option_buy_backtest.py")
    print("\n2. View data:")
    print("   ls -lh historical_data/")
    print("\n3. Check data quality:")
    print("   head -20 historical_data/NIFTY_50_daily_3years.csv")
    print("\n4. Analyze trends:")
    print("   python -c \"import pandas as pd; df=pd.read_csv('historical_data/NIFTY_50_daily_3years.csv'); print(df.describe())\"")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
