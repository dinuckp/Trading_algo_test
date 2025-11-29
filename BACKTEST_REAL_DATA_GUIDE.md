# Backtesting with Real Historical Data - Complete Guide

This guide shows you how to backtest your trading strategies using **real historical data** from your broker.

---

## 🚀 Quick Start (3 Steps)

### Step 1: Configure Broker Credentials

Create a `.env` file with your broker credentials:

```bash
cp .sample.env .env
```

Edit `.env` and fill in your details:

```bash
# Broker Configuration
BROKER_NAME=zerodha  # or "fyers"

# Zerodha Credentials
BROKER_API_KEY=your_api_key_here
BROKER_API_SECRET=your_api_secret_here
BROKER_PASSWORD=your_password_here

# OR for Fyers
BROKER_ID=your_fyers_id
BROKER_TOTP_KEY=your_totp_key
BROKER_TOTP_PIN=your_pin
```

### Step 2: Download Historical Data

```bash
python download_historical_data.py
```

This will download and save data to `historical_data/` directory.

### Step 3: Run Backtest with Real Data

```bash
python run_backtest_with_real_data.py
```

---

## 📊 What Gets Downloaded

The download script fetches:

1. **NIFTY Index** (5-minute data)
   - For Survivor strategy
   - Last 3 months
   - Saved as: `historical_data/NSE_NIFTY_50_5minute_*.csv`

2. **Bank NIFTY Index** (5-minute data)
   - For reference and analysis
   - Saved as: `historical_data/NSE_NIFTY_BANK_5minute_*.csv`

3. **Futures Data** (1-minute data) - Optional
   - For Wave strategy
   - Update contract month in script
   - Saved as: `historical_data/NFO_NIFTY*FUT_1minute_*.csv`

---

## 🔧 Advanced Configuration

### Custom Date Ranges

Edit `download_historical_data.py`:

```python
downloads = [
    {
        'symbol': 'NSE:NIFTY 50',
        'start_date': '2024-01-01',  # Change this
        'end_date': '2024-12-31',     # Change this
        'interval': '5minute',
        'description': 'NIFTY Index'
    },
]
```

### Different Intervals

Available intervals:
- `"1minute"` - 1-minute candles
- `"5minute"` - 5-minute candles (recommended)
- `"15minute"` - 15-minute candles
- `"60minute"` - 1-hour candles
- `"day"` - Daily candles

### Download Specific Symbols

```python
from download_historical_data import download_and_save_data

# Download NIFTY data
download_and_save_data(
    symbol="NSE:NIFTY 50",
    start_date="2024-09-01",
    end_date="2024-11-29",
    interval="5minute"
)

# Download Bank NIFTY
download_and_save_data(
    symbol="NSE:NIFTY BANK",
    start_date="2024-09-01",
    end_date="2024-11-29",
    interval="5minute"
)

# Download Futures (update contract month)
download_and_save_data(
    symbol="NFO:NIFTY25DECFUT",  # December 2025 contract
    start_date="2024-10-01",
    end_date="2024-11-29",
    interval="1minute"
)
```

---

## 📈 Running Backtests

### Option 1: Automatic (Recommended)

```bash
python run_backtest_with_real_data.py
```

This automatically:
- Looks for CSV files in `historical_data/`
- Falls back to broker API if CSVs not found
- Runs both Survivor and Wave backtests
- Generates comprehensive reports including **weekly analysis**

### Option 2: Direct Broker API (Slower)

If you don't want to save CSV files:

```python
# Edit run_backtest_with_real_data.py
# Set data_source="broker" in main()
```

### Option 3: Use Saved CSV Files (Fastest)

If you already have CSV files:

```python
from backtesting.survivor_backtest import SurvivorBacktest
import pandas as pd
import yaml

# Load CSV
df = pd.read_csv('historical_data/NSE_NIFTY_50_5minute_*.csv', parse_dates=['timestamp'])

# Create data fetcher
def data_fetcher(symbol, start, end):
    return df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]

# Load config
with open('strategy/configs/survivor.yml', 'r') as f:
    config = yaml.safe_load(f)['default']

# Run backtest
backtester = SurvivorBacktest(
    config=config,
    start_date="2024-09-01",
    end_date="2024-11-29",
    initial_capital=1000000,
    index_data_source=data_fetcher
)

results = backtester.run()
backtester.generate_report(save_dir='backtest_results/survivor_real')
```

---

## 📊 Generated Reports

After running backtests, you'll get:

```
backtest_results/
├── survivor_real/
│   ├── survivor_backtest_report.txt       # Overall performance
│   ├── survivor_weekly_report.txt         # ✨ NEW: Weekly analysis
│   ├── survivor_weekly_analysis.png       # ✨ NEW: Weekly charts (9 panels)
│   ├── survivor_metrics.json              # Metrics in JSON
│   ├── survivor_trades.csv                # All trades
│   └── survivor_analysis.png              # Performance charts
└── wave_real/
    ├── wave_backtest_report.txt
    ├── wave_weekly_report.txt             # ✨ NEW: Weekly analysis
    ├── wave_weekly_analysis.png           # ✨ NEW: Weekly charts (9 panels)
    ├── wave_metrics.json
    ├── wave_trades.csv
    └── wave_analysis.png
```

---

## 📅 Weekly Analysis Features

The new weekly analysis provides:

### **9 Comprehensive Charts:**
1. **Weekly P&L** - Bar chart showing profit/loss per week
2. **Trades per Week** - Volume of trading activity
3. **Weekly Win Rate** - Consistency tracking
4. **Weekly Equity Return** - Percentage returns
5. **Day of Week Analysis** - Best/worst trading days
6. **Intraday Patterns** - Best/worst trading hours
7. **Weekly Profit Factor** - Risk-reward by week
8. **Avg Win vs Loss** - Trade quality comparison
9. **Weekly Drawdown** - Risk visualization

### **Weekly Report Includes:**
- Overall summary (all weeks)
- Top 3 best performing weeks
- Top 3 worst performing weeks
- Week-by-week breakdown table
- Day-of-week statistics
- Optimal trading times

---

## 🔍 Analyzing Results

### View Text Reports

```bash
# Overall performance
cat backtest_results/survivor_real/survivor_backtest_report.txt

# Weekly breakdown
cat backtest_results/survivor_real/survivor_weekly_report.txt
```

### Open Visualizations

```bash
# Performance charts
open backtest_results/survivor_real/survivor_analysis.png

# Weekly analysis charts
open backtest_results/survivor_real/survivor_weekly_analysis.png
```

### Analyze Trades

```bash
# View all trades
head -20 backtest_results/survivor_real/survivor_trades.csv

# Count trades
wc -l backtest_results/survivor_real/survivor_trades.csv

# Find best trades
sort -t',' -k5 -n backtest_results/survivor_real/survivor_trades.csv | tail -10
```

### Load Metrics in Python

```python
import json

with open('backtest_results/survivor_real/survivor_metrics.json', 'r') as f:
    metrics = json.load(f)

print(f"Total Return: {metrics['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
print(f"Win Rate: {metrics['win_rate_pct']:.2f}%")
```

---

## 🎯 Optimization Tips

### 1. Test Different Date Ranges

```bash
# Test bull market period
python run_backtest_with_real_data.py --start 2024-06-01 --end 2024-08-31

# Test bear market period
python run_backtest_with_real_data.py --start 2024-03-01 --end 2024-05-31
```

### 2. Parameter Sweep

```python
import yaml

for pe_gap in [20, 25, 30, 35]:
    for ce_gap in [20, 25, 30, 35]:
        # Load config
        with open('strategy/configs/survivor.yml', 'r') as f:
            config = yaml.safe_load(f)['default']

        # Modify parameters
        config['pe_gap'] = pe_gap
        config['ce_gap'] = ce_gap

        # Run backtest
        backtester = SurvivorBacktest(config, start_date, end_date)
        results = backtester.run()

        print(f"PE: {pe_gap}, CE: {ce_gap} | Sharpe: {results['metrics']['sharpe_ratio']:.2f}")
```

### 3. Weekly Pattern Analysis

Look at the weekly reports to find:
- **Best performing weeks** - What market conditions?
- **Worst performing weeks** - What went wrong?
- **Day-of-week patterns** - Trade more on certain days?
- **Intraday patterns** - Best hours to trade?

---

## ⚠️ Important Notes

### Broker API Limits

Different brokers have different rate limits:

**Zerodha:**
- Historical data: 3 requests per second
- Data range: Up to 60 days per request (for minute data)

**Fyers:**
- Historical data: 10 requests per second
- Data range: Up to 100 days per request

The download script automatically handles chunking.

### Data Quality

Real broker data may have:
- **Gaps**: Market holidays, weekends
- **Errors**: Occasional missing candles
- **Splits/Bonuses**: Corporate actions affecting prices

The backtesting engine handles these gracefully.

### Market Hours

Downloaded data includes only market hours:
- **Equity**: 9:15 AM - 3:30 PM IST
- **Futures**: 9:15 AM - 3:30 PM IST

---

## 🐛 Troubleshooting

### "No .env file found"

```bash
cp .sample.env .env
# Edit .env with your credentials
```

### "No data returned from broker"

Check:
1. Broker credentials are correct
2. Symbol name is correct (e.g., "NSE:NIFTY 50" not "NIFTY")
3. Date range is valid (not future dates)
4. Broker API is accessible

### "CSV file not found"

Run download script first:
```bash
python download_historical_data.py
```

### "Historical data call failed"

The broker API call may have issues. Check:
1. Internet connection
2. Broker API status
3. Authentication tokens are valid
4. Rate limits not exceeded

---

## 📚 Next Steps

1. **Download Real Data**
   ```bash
   python download_historical_data.py
   ```

2. **Run Initial Backtest**
   ```bash
   python run_backtest_with_real_data.py
   ```

3. **Analyze Weekly Patterns**
   - Open weekly analysis charts
   - Read weekly reports
   - Identify best/worst periods

4. **Optimize Parameters**
   - Adjust gaps based on weekly analysis
   - Test different quantities
   - Find optimal settings

5. **Forward Test**
   - Test on out-of-sample data
   - Validate on different time periods
   - Check robustness

---

## 🎓 Best Practices

1. **Always use real data** for final validation
2. **Test multiple time periods** (bull, bear, sideways markets)
3. **Analyze weekly patterns** to understand strategy behavior
4. **Consider transaction costs** in final analysis
5. **Validate on out-of-sample data** to avoid overfitting
6. **Monitor drawdowns** as much as returns
7. **Check day-of-week effects** for optimal trading times

---

## ✅ Checklist

Before going live:

- [ ] Downloaded real historical data
- [ ] Ran backtests on multiple time periods
- [ ] Analyzed weekly performance patterns
- [ ] Tested different parameter combinations
- [ ] Validated on out-of-sample data
- [ ] Added transaction costs to calculations
- [ ] Checked maximum drawdown is acceptable
- [ ] Reviewed worst-case scenarios
- [ ] Documented strategy parameters
- [ ] Set up position sizing rules

---

## 📞 Support

For issues or questions:
1. Check this documentation
2. Review backtest output logs
3. Check broker API documentation
4. Open an issue on GitHub

---

**Happy Backtesting!** 🚀
