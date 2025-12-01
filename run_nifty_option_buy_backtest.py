"""
Run backtest for NIFTY50 Options Buying Strategy
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import numpy as np
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtesting.nifty_option_buy_backtest import NiftyOptionBuyBacktest
from backtesting.metrics import PerformanceMetrics
from backtesting.weekly_analysis import WeeklyAnalyzer


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_data_from_csv(filepath: str) -> pd.DataFrame:
    """Load historical data from CSV"""
    logger.info(f"Loading data from {filepath}")
    df = pd.read_csv(filepath, parse_dates=['timestamp'])
    logger.info(f"Loaded {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")
    return df


def generate_synthetic_data(start_date: str, end_date: str, interval_minutes: int = 5) -> pd.DataFrame:
    """Generate synthetic NIFTY spot data for testing"""
    logger.info("Generating synthetic NIFTY spot data...")

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    # Generate timestamps (market hours: 9:15 AM to 3:30 PM)
    timestamps = []
    current = start.replace(hour=9, minute=15, second=0, microsecond=0)

    while current <= end:
        if current.weekday() < 5:  # Monday to Friday
            time = current.time()
            if time >= datetime.strptime("09:15", "%H:%M").time() and \
               time <= datetime.strptime("15:30", "%H:%M").time():
                timestamps.append(current)
        current += timedelta(minutes=interval_minutes)

    n = len(timestamps)
    logger.info(f"Generated {n} timestamps")

    # Generate price data with realistic patterns and higher intraday volatility
    base_price = 24500
    trend = np.linspace(0, 200, n)  # Slight uptrend
    daily_cycle = np.sin(np.linspace(0, len(set([t.date() for t in timestamps])) * 2 * np.pi, n)) * 150
    intraday_vol = np.sin(np.linspace(0, n / 75 * 2 * np.pi, n)) * 100  # Higher intraday volatility
    random_walk = np.cumsum(np.random.randn(n) * 15)  # Increased random walk
    noise = np.random.randn(n) * 10  # Increased noise

    close_prices = base_price + trend + daily_cycle + intraday_vol + random_walk + noise

    # Generate OHLC with wider spreads
    high_prices = close_prices + np.abs(np.random.randn(n) * 20)  # Wider high
    low_prices = close_prices - np.abs(np.random.randn(n) * 20)   # Wider low
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = close_prices[0]

    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': np.random.randint(100000, 500000, n)
    })

    # Ensure OHLC logic (high >= open, close, low <= open, close)
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df


def plot_results(results: Dict, output_dir: str):
    """Generate visualization of backtest results"""
    os.makedirs(output_dir, exist_ok=True)

    trades_df = results['trades_df']
    equity_df = results['equity_df']

    if len(trades_df) == 0:
        logger.warning("No trades to plot")
        return

    # Create figure with subplots
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # 1. Equity Curve
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(equity_df['timestamp'], equity_df['equity'], linewidth=2, color='blue')
    ax1.axhline(y=results['initial_capital'], color='red', linestyle='--', label='Initial Capital')
    ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Equity (₹)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Trade PnL Distribution
    ax2 = fig.add_subplot(gs[1, 0])
    trades_df['pnl'].hist(bins=30, ax=ax2, color='green', alpha=0.7, edgecolor='black')
    ax2.axvline(x=0, color='red', linestyle='--')
    ax2.set_title('PnL Distribution', fontsize=12, fontweight='bold')
    ax2.set_xlabel('PnL (₹)')
    ax2.set_ylabel('Frequency')
    ax2.grid(True, alpha=0.3)

    # 3. Cumulative PnL
    ax3 = fig.add_subplot(gs[1, 1])
    trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
    ax3.plot(range(len(trades_df)), trades_df['cumulative_pnl'], linewidth=2, color='purple')
    ax3.axhline(y=0, color='red', linestyle='--')
    ax3.set_title('Cumulative PnL', fontsize=12, fontweight='bold')
    ax3.set_xlabel('Trade Number')
    ax3.set_ylabel('Cumulative PnL (₹)')
    ax3.grid(True, alpha=0.3)

    # 4. Win/Loss Count
    ax4 = fig.add_subplot(gs[1, 2])
    win_loss = trades_df['pnl'].apply(lambda x: 'Win' if x > 0 else 'Loss').value_counts()
    colors = ['green' if x == 'Win' else 'red' for x in win_loss.index]
    ax4.bar(win_loss.index, win_loss.values, color=colors, alpha=0.7, edgecolor='black')
    ax4.set_title('Win vs Loss Trades', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Count')
    ax4.grid(True, alpha=0.3)

    # 5. PnL by Option Type
    ax5 = fig.add_subplot(gs[2, 0])
    pnl_by_type = trades_df.groupby('type')['pnl'].sum()
    colors = ['blue', 'orange']
    ax5.bar(pnl_by_type.index, pnl_by_type.values, color=colors, alpha=0.7, edgecolor='black')
    ax5.set_title('Total PnL by Option Type', fontsize=12, fontweight='bold')
    ax5.set_ylabel('Total PnL (₹)')
    ax5.grid(True, alpha=0.3)

    # 6. Exit Reasons
    ax6 = fig.add_subplot(gs[2, 1])
    exit_reasons = trades_df['reason'].value_counts()
    ax6.pie(exit_reasons.values, labels=exit_reasons.index, autopct='%1.1f%%',
            startangle=90, colors=['lightgreen', 'lightcoral', 'lightyellow'])
    ax6.set_title('Exit Reasons', fontsize=12, fontweight='bold')

    # 7. Trade Duration
    ax7 = fig.add_subplot(gs[2, 2])
    trades_df['duration'] = (trades_df['exit_time'] - trades_df['entry_time']).dt.total_seconds() / 60
    trades_df['duration'].hist(bins=20, ax=ax7, color='teal', alpha=0.7, edgecolor='black')
    ax7.set_title('Trade Duration Distribution', fontsize=12, fontweight='bold')
    ax7.set_xlabel('Duration (minutes)')
    ax7.set_ylabel('Frequency')
    ax7.grid(True, alpha=0.3)

    # Save figure
    output_path = os.path.join(output_dir, 'nifty_option_buy_analysis.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"Saved analysis chart to {output_path}")
    plt.close()


def generate_report(results: Dict, output_dir: str):
    """Generate text report of backtest results"""
    os.makedirs(output_dir, exist_ok=True)

    report = []
    report.append("=" * 80)
    report.append("NIFTY50 OPTIONS BUYING STRATEGY - BACKTEST REPORT")
    report.append("=" * 80)
    report.append("")

    report.append("STRATEGY PARAMETERS:")
    report.append("-" * 80)
    report.append(f"  Strike Selection:")
    report.append(f"    - CE Strike: Current Price - 100")
    report.append(f"    - PE Strike: Current Price + 100")
    report.append(f"    - Expiry: Current Week Thursday")
    report.append(f"  Entry: Day Low + 1.5%")
    report.append(f"  Stop Loss: Day Low + 1.2%")
    report.append(f"  Target: Day Low + 1.8%")
    report.append("")

    report.append("PERFORMANCE SUMMARY:")
    report.append("-" * 80)
    report.append(f"  Initial Capital: ₹{results['initial_capital']:,.2f}")
    report.append(f"  Final Equity: ₹{results['final_equity']:,.2f}")
    report.append(f"  Total Return: {results['total_return_pct']:.2f}%")
    report.append(f"  Total PnL: ₹{results['total_pnl']:,.2f}")
    report.append("")

    report.append("TRADE STATISTICS:")
    report.append("-" * 80)
    report.append(f"  Total Trades: {results['total_trades']}")
    report.append(f"  Winning Trades: {results['winning_trades']}")
    report.append(f"  Losing Trades: {results['losing_trades']}")
    report.append(f"  Win Rate: {results['win_rate']:.2f}%")
    report.append("")

    if len(results['trades_df']) > 0:
        trades_df = results['trades_df']

        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if len(trades_df[trades_df['pnl'] > 0]) > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if len(trades_df[trades_df['pnl'] < 0]) > 0 else 0

        report.append("  Average Win: ₹{:,.2f}".format(avg_win))
        report.append("  Average Loss: ₹{:,.2f}".format(avg_loss))
        report.append(f"  Largest Win: ₹{trades_df['pnl'].max():,.2f}")
        report.append(f"  Largest Loss: ₹{trades_df['pnl'].min():,.2f}")
        report.append("")

        report.append("PnL BY OPTION TYPE:")
        report.append("-" * 80)
        pnl_by_type = trades_df.groupby('type')['pnl'].agg(['sum', 'mean', 'count'])
        for option_type, row in pnl_by_type.iterrows():
            report.append(f"  {option_type}:")
            report.append(f"    Total PnL: ₹{row['sum']:,.2f}")
            report.append(f"    Average PnL: ₹{row['mean']:,.2f}")
            report.append(f"    Trade Count: {int(row['count'])}")
        report.append("")

        report.append("EXIT REASONS:")
        report.append("-" * 80)
        exit_reasons = trades_df['reason'].value_counts()
        for reason, count in exit_reasons.items():
            pct = (count / len(trades_df)) * 100
            report.append(f"  {reason}: {count} ({pct:.1f}%)")
        report.append("")

    report.append("=" * 80)

    # Write to file
    report_text = "\n".join(report)
    output_path = os.path.join(output_dir, 'nifty_option_buy_report.txt')
    with open(output_path, 'w') as f:
        f.write(report_text)

    logger.info(f"Saved report to {output_path}")
    print("\n" + report_text)


def main():
    """Main execution function"""
    print("\n" + "=" * 80)
    print("NIFTY50 OPTIONS BUYING STRATEGY - BACKTEST")
    print("=" * 80 + "\n")

    # Configuration
    config = {
        'initial_capital': 100000,
        'lot_size': 50,
        'quantity': 50  # 1 lot
    }

    # Try to load real data, fallback to synthetic
    data_file = 'historical_data/NSE_NIFTY_50_5minute_90days.csv'

    if os.path.exists(data_file):
        print(f"Loading real data from {data_file}...")
        spot_data = load_data_from_csv(data_file)
    else:
        print(f"Real data file not found. Generating synthetic data...")
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        spot_data = generate_synthetic_data(start_date, end_date, interval_minutes=5)

    print(f"\nData loaded: {len(spot_data)} candles")
    print(f"Period: {spot_data['timestamp'].min()} to {spot_data['timestamp'].max()}\n")

    # Run backtest
    print("Running backtest...")
    backtest = NiftyOptionBuyBacktest(config)
    results = backtest.run(spot_data)

    # Generate outputs
    output_dir = 'backtest_results/nifty_option_buy'
    os.makedirs(output_dir, exist_ok=True)

    print("\nGenerating report...")
    generate_report(results, output_dir)

    print("\nGenerating visualizations...")
    plot_results(results, output_dir)

    # Save trades to CSV
    if len(results['trades_df']) > 0:
        trades_path = os.path.join(output_dir, 'trades.csv')
        results['trades_df'].to_csv(trades_path, index=False)
        logger.info(f"Saved trades to {trades_path}")

    # Save equity curve to CSV
    if len(results['equity_df']) > 0:
        equity_path = os.path.join(output_dir, 'equity_curve.csv')
        results['equity_df'].to_csv(equity_path, index=False)
        logger.info(f"Saved equity curve to {equity_path}")

    print(f"\n✓ Backtest complete! Results saved to: {output_dir}")
    print(f"\nKey Metrics:")
    print(f"  - Total Return: {results['total_return_pct']:.2f}%")
    print(f"  - Win Rate: {results['win_rate']:.2f}%")
    print(f"  - Total Trades: {results['total_trades']}")
    print(f"  - Total PnL: ₹{results['total_pnl']:,.2f}\n")


if __name__ == '__main__':
    main()
