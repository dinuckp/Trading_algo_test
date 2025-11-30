"""
Quick Data Download Script - No Configuration Needed

This script downloads historical data with minimal setup.
Just provide your broker API credentials when prompted.
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


def download_sample_data():
    """
    Download commonly used data
    """
    from brokers import BrokerGateway

    print("\n" + "="*80)
    print("DOWNLOAD HISTORICAL DATA")
    print("="*80)

    broker_name = os.getenv("BROKER_NAME")
    print(f"\nUsing broker: {broker_name}")

    # Data configurations
    datasets = [
        {
            'name': 'NIFTY Index (3 months)',
            'symbol': 'NSE:NIFTY 50',
            'days': 90,
            'interval': '5minute',
            'required': True
        },
        {
            'name': 'Bank NIFTY Index (3 months)',
            'symbol': 'NSE:NIFTY BANK',
            'days': 90,
            'interval': '5minute',
            'required': False
        },
        {
            'name': 'NIFTY Index (6 months)',
            'symbol': 'NSE:NIFTY 50',
            'days': 180,
            'interval': '5minute',
            'required': False
        },
    ]

    print("\nAvailable datasets:")
    for i, ds in enumerate(datasets, 1):
        required = " [Required]" if ds['required'] else " [Optional]"
        print(f"  {i}. {ds['name']}{required}")

    print("\nChoose download option:")
    print("  1. Download only required data (fastest)")
    print("  2. Download all available data")
    print("  3. Custom selection")

    choice = input("\nEnter choice (1-3): ").strip()

    selected = []
    if choice == "1":
        selected = [ds for ds in datasets if ds['required']]
    elif choice == "2":
        selected = datasets
    else:
        print("\nSelect datasets to download (comma-separated, e.g., 1,2,3):")
        indices = input("Enter numbers: ").strip().split(',')
        selected = [datasets[int(i.strip())-1] for i in indices if i.strip().isdigit()]

    if not selected:
        print("❌ No datasets selected")
        return

    # Download
    broker = BrokerGateway.from_name(broker_name)
    os.makedirs('historical_data', exist_ok=True)

    successful = 0
    failed = 0

    for ds in selected:
        print(f"\n{'='*80}")
        print(f"Downloading: {ds['name']}")
        print(f"Symbol: {ds['symbol']}")
        print(f"Interval: {ds['interval']}")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=ds['days'])

        try:
            data = broker.get_history(
                ds['symbol'],
                ds['interval'],
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )

            if not data:
                print(f"❌ No data returned")
                failed += 1
                continue

            # Convert to DataFrame
            df = pd.DataFrame(data)

            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
            elif 'ts' in df.columns:
                df['timestamp'] = pd.to_datetime(df['ts'], unit='s', errors='coerce')
                df = df.drop('ts', axis=1)

            # Save to CSV
            symbol_clean = ds['symbol'].replace(":", "_").replace(" ", "_")
            filename = f"{symbol_clean}_{ds['interval']}_{ds['days']}days.csv"
            filepath = os.path.join('historical_data', filename)

            df.to_csv(filepath, index=False)

            print(f"✅ Saved: {filepath}")
            print(f"   Rows: {len(df):,}")
            print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            print(f"   Price range: ₹{df['close'].min():.2f} - ₹{df['close'].max():.2f}")

            successful += 1

        except Exception as e:
            print(f"❌ Error: {e}")
            logger.error(f"Download failed: {e}", exc_info=True)
            failed += 1

    # Summary
    print("\n" + "="*80)
    print("DOWNLOAD SUMMARY")
    print("="*80)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"\nData saved in: historical_data/")
    print("="*80)


def main():
    """
    Main interactive flow
    """
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     REAL DATA DOWNLOAD FOR BACKTESTING                  ║
    ║     Quick & Easy Setup                                  ║
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

    # Download data
    try:
        download_sample_data()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Failed to download: {e}", exc_info=True)
        print("\nTroubleshooting tips:")
        print("  1. Verify your broker credentials in .env")
        print("  2. Check your internet connection")
        print("  3. Ensure broker API is accessible")
        print("  4. Try again in a few minutes")
        return

    # Next steps
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Run backtest:")
    print("   python run_backtest_with_real_data.py")
    print("\n2. View downloaded data:")
    print("   ls -lh historical_data/")
    print("\n3. Check data quality:")
    print("   head historical_data/*.csv")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
