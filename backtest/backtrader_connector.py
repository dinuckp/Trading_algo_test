#!/usr/bin/env python3
"""
Python Backtrader Connector

This script demonstrates how to integrate Node.js signals with Python Backtrader.
Usage: python backtrader_connector.py --data <csv_file> --signals <signals_json>

Requirements:
    pip install backtrader pandas

Note: This is a simplified example. For production use, enhance error handling,
add more sophisticated signal processing, and implement custom Backtrader strategies.
"""

import argparse
import json
import sys
from datetime import datetime

try:
    import backtrader as bt
    import pandas as pd
except ImportError:
    print("Error: Required packages not installed")
    print("Install with: pip install backtrader pandas")
    sys.exit(1)


class SignalStrategy(bt.Strategy):
    """
    Strategy that executes trades based on signals from JSON file
    """

    params = (
        ('signals', []),
        ('printlog', True),
    )

    def __init__(self):
        self.order = None
        self.signal_index = 0
        self.trades_executed = []

    def log(self, txt, dt=None):
        """Logging function"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
            else:
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')

        self.trades_executed.append({
            'entry_time': bt.num2date(trade.dtopen).isoformat(),
            'exit_time': bt.num2date(trade.dtclose).isoformat(),
            'symbol': self.datas[0]._name,
            'side': 'BUY',
            'entry_price': trade.price,
            'exit_price': trade.price + trade.pnl / trade.size,
            'quantity': trade.size,
            'pnl': trade.pnl
        })

    def next(self):
        # Check if we have pending signals
        if self.signal_index >= len(self.params.signals):
            return

        # Get current date
        current_date = self.datas[0].datetime.datetime(0)

        # Process signals for current timestamp
        while self.signal_index < len(self.params.signals):
            signal = self.params.signals[self.signal_index]
            signal_date = datetime.fromisoformat(signal['timestamp'].replace('Z', '+00:00'))

            # If signal is in the future, wait
            if signal_date > current_date:
                break

            # Execute signal
            if signal['action'] == 'BUY':
                self.log(f"BUY SIGNAL: {signal['reason']}")
                self.order = self.buy(size=signal['quantity'])
            elif signal['action'] in ['SELL', 'CLOSE']:
                self.log(f"SELL SIGNAL: {signal['reason']}")
                self.order = self.sell(size=signal['quantity'])

            self.signal_index += 1


def parse_args():
    parser = argparse.ArgumentParser(description='Backtrader Signal Executor')

    parser.add_argument('--data', required=True, help='CSV file with historical data')
    parser.add_argument('--signals', required=True, help='JSON file with signals')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--initial-cash', type=float, default=100000,
                        help='Initial cash (default: 100000)')
    parser.add_argument('--commission', type=float, default=0.0002,
                        help='Commission rate (default: 0.0002)')

    return parser.parse_args()


def main():
    args = parse_args()

    # Load signals
    try:
        with open(args.signals, 'r') as f:
            signals = json.load(f)
        print(f"Loaded {len(signals)} signals from {args.signals}")
    except Exception as e:
        print(f"Error loading signals: {e}")
        sys.exit(1)

    # Create cerebro engine
    cerebro = bt.Cerebro()

    # Load data
    try:
        df = pd.read_csv(args.data, parse_dates=['timestamp'])
        df.set_index('timestamp', inplace=True)

        data = bt.feeds.PandasData(
            dataname=df,
            datetime=None,
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
            openinterest='oi'
        )

        cerebro.adddata(data)
        print(f"Loaded data from {args.data}")
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

    # Add strategy with signals
    cerebro.addstrategy(SignalStrategy, signals=signals)

    # Set initial cash
    cerebro.broker.setcash(args.initial_cash)

    # Set commission
    cerebro.broker.setcommission(commission=args.commission)

    # Print starting conditions
    print(f"\nStarting Portfolio Value: ₹{cerebro.broker.getvalue():.2f}")

    # Run backtest
    results = cerebro.run()

    # Print final results
    final_value = cerebro.broker.getvalue()
    print(f"\nFinal Portfolio Value: ₹{final_value:.2f}")
    print(f"Total P&L: ₹{final_value - args.initial_cash:.2f}")

    # Get strategy results
    strat = results[0]
    trades = strat.trades_executed

    # Calculate statistics
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] <= 0]

    total_pnl = sum(t['pnl'] for t in trades)
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
    win_rate = len(winning_trades) / len(trades) if trades else 0
    profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

    # Output results as JSON for Node.js to parse
    result_json = {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'total_pnl': total_pnl,
        'max_drawdown': 0,  # Would need to calculate properly
        'sharpe_ratio': 0,  # Would need to calculate properly
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'trades': trades
    }

    print("\n" + json.dumps(result_json, indent=2))


if __name__ == '__main__':
    main()
