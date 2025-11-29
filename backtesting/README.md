# Backtesting Framework

A comprehensive backtesting framework for trading strategies with historical data replay, performance analysis, and detailed reporting.

## Features

✅ **Strategy-Specific Backtesting**: Dedicated backtesting engines for Survivor and Wave strategies
✅ **Mock Broker**: Simulates order execution without live trading
✅ **Performance Metrics**: 20+ metrics including Sharpe, Sortino, Calmar ratios
✅ **Comprehensive Reports**: Text reports, JSON metrics, CSV trade logs
✅ **Visualization**: Equity curves, drawdown charts, returns distribution
✅ **Flexible Data Sources**: Support for broker APIs, CSV files, or custom sources

## Quick Start

### Install Dependencies

```bash
uv sync
```

### Run Example Backtests

**Survivor Strategy:**
```bash
python examples/backtest_survivor_example.py
```

**Wave Strategy:**
```bash
python examples/backtest_wave_example.py
```

## Framework Architecture

```
backtesting/
├── __init__.py                  # Module exports
├── engine.py                    # Base backtesting engine and MockBroker
├── metrics.py                   # Performance metrics calculator
├── survivor_backtest.py         # Survivor strategy backtester
├── wave_backtest.py            # Wave strategy backtester
└── README.md                    # This file

examples/
├── backtest_survivor_example.py # Survivor backtest example
├── backtest_wave_example.py     # Wave backtest example
└── README.md                    # Examples documentation
```

## Core Components

### 1. BacktestEngine (`engine.py`)

Base class providing:
- Historical data loading
- Equity curve tracking
- Trade logging
- Performance metrics calculation
- Result visualization

### 2. MockBroker (`engine.py`)

Simulates broker functionality:
- Order placement and execution
- Position tracking
- Portfolio value calculation
- Quote provision

### 3. PerformanceMetrics (`metrics.py`)

Calculates comprehensive metrics:

**Return Metrics:**
- Total Return, CAGR, Absolute Profit

**Risk Metrics:**
- Max Drawdown, Volatility, Sharpe Ratio, Sortino Ratio, Calmar Ratio, VaR, CVaR

**Trade Metrics:**
- Win Rate, Profit Factor, Average Win/Loss, Expectancy, Consecutive Wins/Losses

### 4. Strategy Backtests

**SurvivorBacktest** (`survivor_backtest.py`):
- Replays NIFTY index movements
- Simulates PE/CE option selling
- Tracks gap-based triggers
- Models option pricing

**WaveBacktest** (`wave_backtest.py`):
- Replays futures price data
- Simulates limit order fills
- Tracks position scaling
- Models order book interactions

## Usage

### Basic Backtesting Workflow

```python
from backtesting.survivor_backtest import SurvivorBacktest
import yaml

# 1. Load configuration
with open('strategy/configs/survivor.yml', 'r') as f:
    config = yaml.safe_load(f)['default']

# 2. Define data source
def fetch_data(symbol, start_date, end_date):
    from brokers import BrokerGateway
    broker = BrokerGateway.from_name("zerodha")
    return broker.get_history(symbol, "5minute", start_date, end_date)

# 3. Create backtester
backtester = SurvivorBacktest(
    config=config,
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=1000000,
    index_data_source=fetch_data
)

# 4. Run backtest
results = backtester.run()

# 5. Generate reports
backtester.generate_report(save_dir='backtest_results/survivor')
```

### Custom Data Source

**From Broker API:**
```python
def fetch_from_broker(symbol, start_date, end_date):
    from brokers import BrokerGateway
    broker = BrokerGateway.from_name("zerodha")
    data = broker.get_history(symbol, "5minute", start_date, end_date)
    return pd.DataFrame(data)
```

**From CSV File:**
```python
def fetch_from_csv(symbol, start_date, end_date):
    df = pd.read_csv(f'data/{symbol}.csv', parse_dates=['timestamp'])
    return df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
```

**Synthetic Data (Testing):**
```python
def generate_synthetic(symbol, start_date, end_date):
    dates = pd.date_range(start_date, end_date, freq='5min')
    prices = 24500 + np.cumsum(np.random.randn(len(dates)))
    return pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices * 1.001,
        'low': prices * 0.999,
        'close': prices,
        'volume': 100000
    })
```

### Custom Option Pricing

For more accurate Survivor backtests, provide a custom pricing model:

```python
import mibian

def black_scholes_price(strike, spot, option_type, days_to_expiry):
    bs = mibian.BS(
        [spot, strike, 10, days_to_expiry],  # spot, strike, rate, days
        volatility=20  # IV
    )
    return bs.callPrice if option_type == 'CE' else bs.putPrice

backtester = SurvivorBacktest(
    config=config,
    start_date=start_date,
    end_date=end_date,
    options_pricing_model=black_scholes_price
)
```

## Performance Analysis

### View Results

**Console Output:**
```python
backtester.print_results()
```

**Generate Full Report:**
```python
backtester.generate_report(save_dir='results')
```

### Output Files

```
backtest_results/
├── survivor/
│   ├── survivor_backtest_report.txt   # Detailed text report
│   ├── survivor_metrics.json          # Metrics in JSON
│   ├── survivor_trades.csv            # Trade log
│   └── survivor_analysis.png          # Charts (6 subplots)
```

### Metrics Interpretation

**Sharpe Ratio** (>1.0 good, >2.0 excellent):
- Risk-adjusted return measure
- Higher is better

**Max Drawdown** (<20% good):
- Largest peak-to-trough decline
- Lower is better

**Win Rate** (>50% for profitable strategies):
- Percentage of winning trades
- Should be balanced with profit factor

**Profit Factor** (>1.5 good):
- Gross profit / Gross loss
- Measures strategy efficiency

## Parameter Optimization

### Grid Search Example

```python
import itertools

# Define parameter ranges
pe_gaps = [15, 20, 25, 30]
ce_gaps = [15, 20, 25, 30]
quantities = [50, 75, 100]

results = []

for pe_gap, ce_gap, qty in itertools.product(pe_gaps, ce_gaps, quantities):
    config['pe_gap'] = pe_gap
    config['ce_gap'] = ce_gap
    config['pe_quantity'] = qty
    config['ce_quantity'] = qty

    backtester = SurvivorBacktest(config, start_date, end_date)
    result = backtester.run()

    results.append({
        'pe_gap': pe_gap,
        'ce_gap': ce_gap,
        'quantity': qty,
        'sharpe': result['metrics']['sharpe_ratio'],
        'return': result['metrics']['total_return_pct'],
        'max_dd': result['metrics']['max_drawdown_pct']
    })

# Find best parameters
best = max(results, key=lambda x: x['sharpe'])
print(f"Best parameters: {best}")
```

### Walk-Forward Analysis

```python
def walk_forward_test(config, full_start, full_end, train_period, test_period):
    results = []
    current_date = pd.to_datetime(full_start)
    end_date = pd.to_datetime(full_end)

    while current_date < end_date:
        train_start = current_date
        train_end = current_date + pd.Timedelta(days=train_period)
        test_start = train_end
        test_end = test_start + pd.Timedelta(days=test_period)

        # Run in-sample backtest (training)
        train_backtester = SurvivorBacktest(config, str(train_start.date()), str(train_end.date()))
        train_results = train_backtester.run()

        # Run out-of-sample backtest (testing)
        test_backtester = SurvivorBacktest(config, str(test_start.date()), str(test_end.date()))
        test_results = test_backtester.run()

        results.append({
            'train_period': f"{train_start.date()} to {train_end.date()}",
            'test_period': f"{test_start.date()} to {test_end.date()}",
            'train_sharpe': train_results['metrics']['sharpe_ratio'],
            'test_sharpe': test_results['metrics']['sharpe_ratio']
        })

        current_date = test_end

    return pd.DataFrame(results)

# Run walk-forward analysis
wf_results = walk_forward_test(config, "2024-01-01", "2024-12-31", 90, 30)
print(wf_results)
```

## Advanced Features

### Adding Transaction Costs

Modify `MockBroker` in `engine.py`:

```python
class MockBroker:
    def __init__(self, initial_capital=1000000, brokerage_per_order=20, tax_rate=0.000325):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.brokerage_per_order = brokerage_per_order
        self.tax_rate = tax_rate
        # ... rest of init

    def place_order(self, req):
        # ... existing code

        # Deduct brokerage
        self.capital -= self.brokerage_per_order

        # Deduct taxes (STT, transaction charges, etc.)
        tax = req.quantity * price * self.tax_rate
        self.capital -= tax

        # ... rest of method
```

### Adding Slippage

```python
def apply_slippage(self, price, transaction_type, slippage_pct=0.05):
    """Apply realistic slippage to order execution"""
    if transaction_type == 'BUY':
        return price * (1 + slippage_pct/100)
    else:  # SELL
        return price * (1 - slippage_pct/100)
```

### Market Hours Filtering

```python
def is_market_hours(timestamp):
    """Check if timestamp is during market hours"""
    if timestamp.weekday() >= 5:  # Weekend
        return False
    if timestamp.hour < 9 or timestamp.hour >= 15:  # Outside 9 AM - 3 PM
        return False
    if timestamp.hour == 9 and timestamp.minute < 15:  # Before 9:15 AM
        return False
    return True

# Filter data
data = data[data['timestamp'].apply(is_market_hours)]
```

## Limitations & Considerations

**Current Limitations:**

1. **Order Fills**: Simplistic fill model (doesn't account for liquidity, order book depth)
2. **Slippage**: Not included by default
3. **Transaction Costs**: Brokerage and taxes not included
4. **Market Impact**: Assumes orders don't move the market
5. **Option Pricing**: Simple pricing model for Survivor strategy

**Recommendations:**

- Use real historical option prices when available
- Add transaction costs for realistic results
- Consider market hours in your analysis
- Test multiple time periods (avoid overfitting)
- Use walk-forward analysis for robustness
- Account for changing market regimes

## Best Practices

1. **Use Real Data**: Always use actual historical data, not synthetic
2. **Include Costs**: Add brokerage, slippage, and taxes
3. **Avoid Overfitting**: Test on out-of-sample data
4. **Consider Regime Changes**: Test across different market conditions
5. **Validate Assumptions**: Check if backtest assumptions match live trading
6. **Monitor Drawdowns**: Ensure max drawdown is acceptable for your risk tolerance
7. **Check Trade Frequency**: Too many/few trades may indicate issues

## Troubleshooting

**No trades executed:**
- Check if gaps are appropriate for price movements
- Verify option premium thresholds
- Review trigger conditions in logs

**Unrealistic returns:**
- Add transaction costs
- Include slippage
- Check for look-ahead bias
- Validate option pricing model

**Memory issues with large datasets:**
- Process data in chunks
- Reduce tick frequency (use 5min instead of 1min bars)
- Sample equity curve less frequently

## Further Reading

- [Examples README](../examples/README.md) - Detailed usage examples
- [Survivor Strategy](../strategy/survivor.py) - Live strategy implementation
- [Wave Strategy](../strategy/wave.py) - Live strategy implementation
- [Main README](../README.md) - Repository overview

## Contributing

Contributions welcome! Areas for improvement:

- More sophisticated order fill models
- Additional performance metrics
- Integration with more data sources
- Monte Carlo simulation
- Portfolio backtesting (multiple strategies)

## Support

For issues or questions:
1. Check this documentation
2. Review example scripts
3. Open an issue on GitHub
