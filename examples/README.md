# Backtesting Examples

This directory contains example scripts demonstrating how to backtest trading strategies.

## Prerequisites

Make sure all dependencies are installed:
```bash
uv sync
```

## Available Examples

### 1. Survivor Strategy Backtest

Backtest the Survivor options trading strategy:

```bash
python examples/backtest_survivor_example.py
```

**Features:**
- Uses historical NIFTY index data
- Simulates PE/CE option selling based on price movements
- Generates comprehensive performance reports
- Creates visualization charts

### 2. Wave Strategy Backtest

Backtest the Wave market-making strategy:

```bash
python examples/backtest_wave_example.py
```

**Features:**
- Uses historical NIFTY futures data
- Simulates limit order placements and fills
- Tracks position scaling based on imbalances
- Generates detailed trade analysis

## Output

Both scripts generate results in the `backtest_results/` directory:

```
backtest_results/
├── survivor/
│   ├── survivor_backtest_report.txt   # Detailed text report
│   ├── survivor_metrics.json          # Metrics in JSON format
│   ├── survivor_trades.csv            # Complete trade log
│   └── survivor_analysis.png          # Performance charts
└── wave/
    ├── wave_backtest_report.txt
    ├── wave_metrics.json
    ├── wave_trades.csv
    └── wave_analysis.png
```

## Using Real Historical Data

### Option 1: Broker API

Replace the synthetic data generator with actual broker data:

```python
from brokers import BrokerGateway

def fetch_historical_data(symbol: str, start_date: str, end_date: str):
    broker = BrokerGateway.from_name("zerodha")
    data = broker.get_history(symbol, "5minute", start_date, end_date)
    return pd.DataFrame(data)
```

### Option 2: CSV Files

Load data from CSV files:

```python
def fetch_historical_data(symbol: str, start_date: str, end_date: str):
    return pd.read_csv('data/nifty_historical.csv', parse_dates=['timestamp'])
```

## Customizing Backtests

### Modify Configuration

Edit the configuration directly in the script:

```python
config = {
    'pe_gap': 30,           # Changed from 20
    'ce_gap': 30,
    'pe_quantity': 50,      # Changed from 75
    'ce_quantity': 50,
    # ... other parameters
}
```

### Change Date Range

```python
start_date = "2023-01-01"
end_date = "2023-12-31"
```

### Adjust Initial Capital

```python
initial_capital = 500000  # ₹5 lakhs
```

## Performance Metrics

The backtesting framework calculates:

**Return Metrics:**
- Total Return (%)
- CAGR (Compound Annual Growth Rate)
- Absolute Profit

**Risk Metrics:**
- Maximum Drawdown (%)
- Volatility (Annual)
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Value at Risk (VaR)

**Trade Metrics:**
- Total Trades
- Win Rate (%)
- Profit Factor
- Average Win/Loss
- Max Consecutive Wins/Losses
- Expectancy

## Advanced Usage

### Custom Option Pricing

For Survivor strategy, provide a custom option pricing model:

```python
def black_scholes_price(strike, spot, option_type, days_to_expiry):
    # Implement Black-Scholes or use mibian library
    import mibian
    bs = mibian.BS([spot, strike, 10, days_to_expiry], volatility=20)
    return bs.callPrice if option_type == 'CE' else bs.putPrice

backtester = SurvivorBacktest(
    config=config,
    start_date=start_date,
    end_date=end_date,
    options_pricing_model=black_scholes_price
)
```

### Parameter Optimization

Run multiple backtests with different parameters:

```python
for pe_gap in [15, 20, 25, 30]:
    for ce_gap in [15, 20, 25, 30]:
        config['pe_gap'] = pe_gap
        config['ce_gap'] = ce_gap

        backtester = SurvivorBacktest(config, start_date, end_date)
        results = backtester.run()

        print(f"PE Gap: {pe_gap}, CE Gap: {ce_gap}")
        print(f"Sharpe: {results['metrics']['sharpe_ratio']:.2f}")
        print(f"Total Return: {results['metrics']['total_return_pct']:.2f}%")
        print("-" * 50)
```

## Notes

- **Synthetic Data**: The examples use synthetic data by default for demonstration. Always use real historical data for actual backtesting.
- **Slippage**: The current implementation doesn't account for slippage. Add custom slippage models as needed.
- **Transaction Costs**: Modify the MockBroker class to include brokerage fees and taxes.
- **Market Hours**: Consider adding market hours filtering for more realistic backtests.

## Troubleshooting

**Issue: "No historical data available"**
- Ensure your data source function returns a valid DataFrame
- Check date format (YYYY-MM-DD)
- Verify the symbol name matches your data source

**Issue: "No trades executed"**
- Check if gaps are too wide for the price movement
- Verify option premium thresholds aren't filtering all trades
- Review the generated equity curve for strategy triggers

## Support

For questions or issues:
1. Check the main [README.md](../README.md)
2. Review strategy documentation in `strategy/` folder
3. Open an issue on GitHub
