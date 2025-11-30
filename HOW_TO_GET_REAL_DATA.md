# Complete Guide: Getting Real Data for Backtesting

This guide covers **ALL methods** to get real historical market data for your backtesting.

---

## 📋 **Table of Contents**

1. [Method 1: Broker API (FREE - Recommended)](#method-1-broker-api)
2. [Method 2: NSE Website (FREE - Limited)](#method-2-nse-website)
3. [Method 3: Yahoo Finance (FREE)](#method-3-yahoo-finance)
4. [Method 4: Paid Data Providers](#method-4-paid-data-providers)
5. [Method 5: Alternative Free Sources](#method-5-alternative-sources)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 **Method 1: Broker API (FREE - Recommended)**

### **Why This is Best:**
✅ Accurate, exchange-quality data
✅ Minute-level granularity
✅ Includes volume, OI data
✅ FREE with your trading account
✅ Same data you'll use for live trading

### **Quick Start (Easiest Way)**

```bash
# Just run this and follow prompts
python quick_download_data.py
```

This interactive script will:
1. Ask for your broker credentials
2. Save them to .env file
3. Download historical data automatically
4. Save to CSV files

### **Manual Setup (Step-by-Step)**

#### **Step 1: Get API Credentials**

**For Zerodha:**
1. Go to https://kite.trade
2. Sign up for Kite Connect
3. Create an app: https://developers.kite.trade/apps
4. Note down:
   - API Key
   - API Secret
   - Your Zerodha Password

**For Fyers:**
1. Go to https://myapi.fyers.in/
2. Create an app
3. Note down:
   - App ID
   - Secret Key
   - TOTP Key (optional)
   - Your PIN

#### **Step 2: Configure .env File**

```bash
# Copy sample file
cp .sample.env .env

# Edit the file
nano .env  # or use any text editor
```

**For Zerodha:**
```bash
BROKER_NAME=zerodha
BROKER_API_KEY=your_api_key_here
BROKER_API_SECRET=your_secret_here
BROKER_PASSWORD=your_password_here
```

**For Fyers:**
```bash
BROKER_NAME=fyers
BROKER_ID=your_fyers_id
BROKER_API_KEY=your_app_id
BROKER_API_SECRET=your_secret_key
BROKER_TOTP_KEY=your_totp_key
BROKER_TOTP_PIN=your_pin
BROKER_TOTP_REDIRECT_URI=http://127.0.0.1:8080
BROKER_LOGIN_MODE=auto
```

#### **Step 3: Download Data**

**Option A: Automated Download**
```bash
python download_historical_data.py
```

**Option B: Custom Python Script**
```python
from brokers import BrokerGateway
import pandas as pd
import os

# Initialize broker
broker = BrokerGateway.from_name("zerodha")  # or "fyers"

# Download NIFTY data
data = broker.get_history(
    symbol="NSE:NIFTY 50",
    interval="5minute",
    start="2024-09-01",
    end="2024-11-29"
)

# Convert to DataFrame
df = pd.DataFrame(data)
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

# Save to CSV
df.to_csv('nifty_data.csv', index=False)

print(f"Downloaded {len(df)} candles")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
```

#### **Step 4: Verify Downloaded Data**

```bash
# Check files
ls -lh historical_data/

# Preview data
head historical_data/NSE_NIFTY_50_*.csv

# Check data quality
python3 << EOF
import pandas as pd
df = pd.read_csv('historical_data/NSE_NIFTY_50_5minute_*.csv', parse_dates=['timestamp'])
print(f"Total rows: {len(df)}")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nSample data:")
print(df.head())
EOF
```

---

## 🌐 **Method 2: NSE Website (FREE - Limited)**

### **What You Can Get:**
- End-of-day (EOD) data only
- Daily, weekly, monthly data
- No intraday (minute-level) data
- Indices and stock data

### **How to Download:**

#### **Manual Download:**

1. **NIFTY Index Data:**
   - Go to: https://www.nseindia.com/
   - Click: Market Data → Index Data
   - Select: NIFTY 50
   - Download historical data (daily)

2. **Stock Data:**
   - Go to: https://www.nseindia.com/
   - Search for stock symbol
   - Download historical data

#### **Automated Download (Python):**

```python
import requests
import pandas as pd
from datetime import datetime

def download_nse_data(symbol="NIFTY", start_date="2024-01-01", end_date="2024-11-29"):
    """
    Download NSE index data
    Note: NSE website has anti-bot protection, may not always work
    """

    # NSE requires headers to mimic browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    url = f"https://www.nseindia.com/api/historical/cm/equity?symbol={symbol}"

    session = requests.Session()
    session.headers.update(headers)

    # Get cookies first
    session.get("https://www.nseindia.com/")

    # Download data
    response = session.get(url)
    data = response.json()

    # Convert to DataFrame
    df = pd.DataFrame(data['data'])
    df.to_csv(f'{symbol}_nse_data.csv', index=False)

    print(f"Downloaded {len(df)} rows")
    return df

# Usage
df = download_nse_data("NIFTY")
```

**Limitations:**
- ❌ Only daily data (no intraday)
- ❌ Anti-bot protection (may fail)
- ❌ Limited history
- ❌ Not suitable for minute-level backtesting

---

## 📊 **Method 3: Yahoo Finance (FREE)**

### **What You Can Get:**
- Historical stock data
- Daily data (not minute-level)
- Indian and international stocks
- Indices data

### **Installation:**

```bash
pip install yfinance
```

### **Download Data:**

```python
import yfinance as yf
import pandas as pd

# Download NIFTY 50 data
nifty = yf.download(
    "^NSEI",  # NIFTY 50 symbol on Yahoo
    start="2024-01-01",
    end="2024-11-29",
    interval="1d"  # Can be: 1m, 5m, 15m, 1h, 1d
)

# Save to CSV
nifty.to_csv('nifty_yahoo.csv')

print(f"Downloaded {len(nifty)} days of data")
print(nifty.head())

# For Bank NIFTY
banknifty = yf.download("^NSEBANK", start="2024-01-01", end="2024-11-29")
banknifty.to_csv('banknifty_yahoo.csv')

# For individual stocks
reliance = yf.download("RELIANCE.NS", start="2024-01-01", end="2024-11-29")
reliance.to_csv('reliance_yahoo.csv')
```

### **Available Intervals:**

```python
# Minute data (last 7 days only!)
yf.download("^NSEI", period="7d", interval="1m")   # 1-minute
yf.download("^NSEI", period="7d", interval="5m")   # 5-minute
yf.download("^NSEI", period="7d", interval="15m")  # 15-minute

# Hourly data (last 730 days)
yf.download("^NSEI", period="730d", interval="1h")

# Daily data (all history)
yf.download("^NSEI", start="2020-01-01", interval="1d")
```

**Limitations:**
- ❌ Intraday data only for last 7-60 days
- ❌ May have missing data
- ❌ Not as accurate as broker data
- ✅ Good for daily backtesting

---

## 💰 **Method 4: Paid Data Providers**

### **TrueData (Popular in India)**

**Website:** https://www.truedata.in/

**What You Get:**
- Tick-level data
- Historical options data
- Futures data
- Very accurate

**Pricing:** ₹500-2000/month

**How to Use:**
```python
from td import TrueData
import pandas as pd

# Login
td = TrueData(username="your_username", password="your_password")

# Download data
data = td.get_historic_data(
    symbol="NIFTY",
    duration="2M",  # 2 months
    bar_size="5min"
)

df = pd.DataFrame(data)
df.to_csv('nifty_truedata.csv')
```

### **Other Providers:**

1. **FirstRate Data**
   - Website: https://firstratedata.com/
   - Pricing: $50-100/month
   - Indian and global markets

2. **Algoseek**
   - Website: https://www.algoseek.com/
   - Tick data
   - Expensive but very detailed

3. **Quandl** (now Nasdaq Data Link)
   - Website: https://data.nasdaq.com/
   - Some free datasets
   - Mostly for US markets

---

## 🆓 **Method 5: Alternative Free Sources**

### **Alpha Vantage API**

```bash
pip install alpha_vantage
```

```python
from alpha_vantage.timeseries import TimeSeries
import pandas as pd

# Get free API key from: https://www.alphavantage.co/support/#api-key
api_key = "your_free_api_key"

ts = TimeSeries(key=api_key, output_format='pandas')

# Download data (limited to US markets mostly)
data, meta = ts.get_intraday(symbol='RELIANCE.BSE', interval='5min')
data.to_csv('reliance_alpha.csv')
```

**Limitations:**
- Limited Indian market coverage
- Rate limits (5 API calls/minute on free tier)
- Better for US stocks

### **Trading View Export**

1. Go to https://www.tradingview.com/
2. Search for NIFTY or desired symbol
3. Click "Chart"
4. Click "..." → Export chart data
5. Download CSV

**Limitations:**
- Manual process
- Limited rows
- Free account limitations

---

## 🛠️ **Troubleshooting**

### **"No data returned from broker"**

**Solutions:**
1. Check credentials in .env file
2. Verify symbol format (e.g., "NSE:NIFTY 50" not "NIFTY")
3. Check date range (not future dates)
4. Try shorter date range (30 days instead of 180)

```python
# Test broker connection
from brokers import BrokerGateway
import os

broker = BrokerGateway.from_name(os.getenv("BROKER_NAME"))

# Try simple query
data = broker.get_history("NSE:NIFTY 50", "day", "2024-11-01", "2024-11-29")
print(f"Got {len(data)} rows")
```

### **"API rate limit exceeded"**

**Solutions:**
1. Add delays between requests
2. Use smaller date ranges
3. Save to CSV and reuse

```python
import time

symbols = ["NSE:NIFTY 50", "NSE:NIFTY BANK"]
for symbol in symbols:
    data = broker.get_history(symbol, "5minute", start, end)
    # Save immediately
    df = pd.DataFrame(data)
    df.to_csv(f'{symbol.replace(":", "_")}.csv')
    time.sleep(1)  # Wait 1 second between requests
```

### **"Missing data / gaps in data"**

**Solutions:**
1. Market holidays - normal
2. Check if symbol was trading on those dates
3. Forward-fill missing data

```python
import pandas as pd

df = pd.read_csv('data.csv', parse_dates=['timestamp'])

# Fill missing values
df = df.fillna(method='ffill')  # Forward fill

# Or drop rows with missing data
df = df.dropna()

# Check for gaps
df = df.sort_values('timestamp')
time_diff = df['timestamp'].diff()
gaps = time_diff[time_diff > pd.Timedelta('10 minutes')]
print(f"Found {len(gaps)} gaps in data")
```

---

## 📝 **Data Quality Checklist**

Before using downloaded data:

```python
import pandas as pd

def validate_data(filepath):
    """Validate downloaded data quality"""

    df = pd.read_csv(filepath, parse_dates=['timestamp'])

    print("="*60)
    print("DATA QUALITY REPORT")
    print("="*60)

    # Basic info
    print(f"\n✓ Total rows: {len(df):,}")
    print(f"✓ Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"✓ Columns: {df.columns.tolist()}")

    # Check for required columns
    required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    missing = [col for col in required if col not in df.columns]
    if missing:
        print(f"\n❌ Missing columns: {missing}")
    else:
        print(f"\n✓ All required columns present")

    # Check for missing values
    null_counts = df.isnull().sum()
    if null_counts.any():
        print(f"\n⚠️  Missing values found:")
        print(null_counts[null_counts > 0])
    else:
        print(f"\n✓ No missing values")

    # Check price consistency
    invalid = df[(df['high'] < df['low']) | (df['high'] < df['close']) | (df['high'] < df['open'])]
    if len(invalid) > 0:
        print(f"\n❌ Found {len(invalid)} rows with invalid OHLC")
    else:
        print(f"\n✓ OHLC data is consistent")

    # Check for duplicates
    dupes = df[df.duplicated(subset=['timestamp'])]
    if len(dupes) > 0:
        print(f"\n⚠️  Found {len(dupes)} duplicate timestamps")
    else:
        print(f"\n✓ No duplicate timestamps")

    print("\n" + "="*60)

    return len(missing) == 0 and len(invalid) == 0

# Usage
validate_data('historical_data/NSE_NIFTY_50_5minute_90days.csv')
```

---

## 🎯 **Recommended Approach**

### **For Options Strategies (Survivor):**
1. ✅ Use Broker API for NIFTY Index data
2. ✅ 5-minute interval data
3. ✅ Last 3-6 months for initial testing
4. ✅ Use actual option prices if available

### **For Futures Strategies (Wave):**
1. ✅ Use Broker API for Futures data
2. ✅ 1-minute interval data
3. ✅ Current month contract
4. ✅ Include volume data

### **Storage:**
```
historical_data/
├── NSE_NIFTY_50_5minute_90days.csv      # For Survivor
├── NSE_NIFTY_BANK_5minute_90days.csv     # For reference
├── NFO_NIFTY25DECFUT_1minute_30days.csv # For Wave
└── README.txt                            # Document what each file is
```

---

## ✅ **Quick Start Checklist**

- [ ] Choose data source (Broker API recommended)
- [ ] Set up credentials (.env file)
- [ ] Run `python quick_download_data.py`
- [ ] Verify downloaded data quality
- [ ] Run backtest: `python run_backtest_with_real_data.py`
- [ ] Analyze results in `backtest_results/`

---

**You're now ready to backtest with real data!** 🚀
