"""
Base Backtesting Engine

Provides core functionality for backtesting trading strategies with historical data.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from logger import logger
import time


class MockBroker:
    """
    Mock broker for backtesting that simulates order execution
    """

    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.orders = []
        self.trades = []
        self.current_price = {}

    def place_order(self, req):
        """Simulate order placement"""
        from brokers import OrderResponse

        order_id = f"MOCK_{len(self.orders) + 1}"
        symbol = req.symbol

        # Get execution price
        if req.order_type.value == "MARKET":
            price = self.current_price.get(symbol, req.price or 0)
        else:
            price = req.price

        # Create order
        order = {
            'order_id': order_id,
            'symbol': symbol,
            'transaction_type': req.transaction_type.value,
            'quantity': req.quantity,
            'price': price,
            'order_type': req.order_type.value,
            'status': 'COMPLETE',
            'timestamp': datetime.now()
        }

        self.orders.append(order)

        # Update position
        if symbol not in self.positions:
            self.positions[symbol] = {'quantity': 0, 'avg_price': 0}

        if req.transaction_type.value == 'BUY':
            old_qty = self.positions[symbol]['quantity']
            old_avg = self.positions[symbol]['avg_price']
            new_qty = old_qty + req.quantity
            new_avg = ((old_qty * old_avg) + (req.quantity * price)) / new_qty if new_qty > 0 else 0
            self.positions[symbol]['quantity'] = new_qty
            self.positions[symbol]['avg_price'] = new_avg
            self.capital -= req.quantity * price
        else:  # SELL
            self.positions[symbol]['quantity'] -= req.quantity
            self.capital += req.quantity * price

            # Record trade
            self.trades.append({
                'symbol': symbol,
                'entry_price': self.positions[symbol]['avg_price'],
                'exit_price': price,
                'quantity': req.quantity,
                'pnl': (price - self.positions[symbol]['avg_price']) * req.quantity,
                'timestamp': datetime.now()
            })

        return OrderResponse(order_id=order_id, status='success', message='Order placed')

    def get_quote(self, symbol):
        """Return mock quote"""
        from brokers import Quote, Exchange

        price = self.current_price.get(symbol, 0)
        return Quote(
            symbol=symbol,
            exchange=Exchange.NFO,  # Default to NFO
            last_price=price,
            bid=price,
            ask=price,
            volume=0
        )

    def update_prices(self, prices: Dict[str, float]):
        """Update current market prices"""
        self.current_price.update(prices)

    def get_positions(self):
        """Return current positions"""
        from brokers import Position, Exchange

        positions = []
        for symbol, pos in self.positions.items():
            if pos['quantity'] != 0:
                positions.append(Position(
                    symbol=symbol,
                    exchange=Exchange.NFO,  # Default to NFO
                    quantity_total=pos['quantity'],
                    quantity_available=pos['quantity'],  # All available in backtest
                    average_price=pos['avg_price'],
                    pnl=0  # Will be calculated separately
                ))
        return positions

    def get_portfolio_value(self):
        """Calculate total portfolio value"""
        position_value = 0
        for symbol, pos in self.positions.items():
            current_price = self.current_price.get(symbol, pos['avg_price'])
            position_value += pos['quantity'] * current_price

        return self.capital + position_value

    def cancel_order(self, order_id):
        """Mock cancel order"""
        pass

    def download_instruments(self):
        """Mock download instruments"""
        pass

    def get_instruments(self):
        """Mock get instruments"""
        return pd.DataFrame()


class BacktestEngine:
    """
    Core backtesting engine that replays historical data through a strategy
    """

    def __init__(
        self,
        strategy_class,
        config: Dict,
        start_date: str,
        end_date: str,
        initial_capital: float = 1000000,
        data_source: Optional[Callable] = None
    ):
        """
        Initialize backtesting engine

        Args:
            strategy_class: Strategy class to backtest
            config: Strategy configuration dictionary
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Starting capital
            data_source: Optional function to fetch historical data
        """
        self.strategy_class = strategy_class
        self.config = config
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.data_source = data_source

        # Initialize mock broker
        self.broker = MockBroker(initial_capital)

        # Results tracking
        self.equity_curve = []
        self.trade_log = []
        self.daily_returns = []

        logger.info(f"BacktestEngine initialized: {start_date} to {end_date}")

    def load_historical_data(self, symbol: str) -> pd.DataFrame:
        """
        Load historical data for a symbol

        Args:
            symbol: Trading symbol

        Returns:
            DataFrame with OHLC data
        """
        if self.data_source:
            return self.data_source(symbol, self.start_date, self.end_date)
        else:
            # Default: Generate synthetic data for testing
            logger.warning("No data source provided, generating synthetic data")
            dates = pd.date_range(self.start_date, self.end_date, freq='1min')
            df = pd.DataFrame({
                'timestamp': dates,
                'open': 24500 + pd.Series(range(len(dates))) % 100,
                'high': 24510 + pd.Series(range(len(dates))) % 100,
                'low': 24490 + pd.Series(range(len(dates))) % 100,
                'close': 24500 + pd.Series(range(len(dates))) % 100,
                'volume': 1000
            })
            return df

    def run(self) -> Dict[str, Any]:
        """
        Run the backtest

        Returns:
            Dictionary containing backtest results
        """
        logger.info("Starting backtest...")

        # This is a template - specific implementations in strategy backtests
        raise NotImplementedError("Use specific strategy backtester (SurvivorBacktest, WaveBacktest)")

    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate performance metrics from backtest results

        Returns:
            Dictionary of performance metrics
        """
        if not self.equity_curve:
            return {}

        equity_series = pd.Series([e['equity'] for e in self.equity_curve])
        returns = equity_series.pct_change().dropna()

        total_return = (equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0]

        # Calculate maximum drawdown
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        max_drawdown = drawdown.min()

        # Sharpe ratio (annualized, assuming 252 trading days)
        sharpe = (returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() > 0 else 0

        # Win rate
        winning_trades = [t for t in self.broker.trades if t['pnl'] > 0]
        win_rate = len(winning_trades) / len(self.broker.trades) if self.broker.trades else 0

        # Average trade
        avg_trade = sum(t['pnl'] for t in self.broker.trades) / len(self.broker.trades) if self.broker.trades else 0

        return {
            'initial_capital': self.initial_capital,
            'final_capital': equity_series.iloc[-1],
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'sharpe_ratio': sharpe,
            'total_trades': len(self.broker.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(self.broker.trades) - len(winning_trades),
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'avg_trade': avg_trade,
            'total_pnl': sum(t['pnl'] for t in self.broker.trades)
        }

    def print_results(self):
        """Print backtest results in a formatted way"""
        metrics = self.calculate_metrics()

        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80)
        print(f"Period: {self.start_date} to {self.end_date}")
        print(f"Initial Capital: ₹{metrics.get('initial_capital', 0):,.2f}")
        print(f"Final Capital: ₹{metrics.get('final_capital', 0):,.2f}")
        print(f"Total Return: ₹{metrics.get('total_pnl', 0):,.2f} ({metrics.get('total_return_pct', 0):.2f}%)")
        print(f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print("-"*80)
        print(f"Total Trades: {metrics.get('total_trades', 0)}")
        print(f"Winning Trades: {metrics.get('winning_trades', 0)}")
        print(f"Losing Trades: {metrics.get('losing_trades', 0)}")
        print(f"Win Rate: {metrics.get('win_rate_pct', 0):.2f}%")
        print(f"Average Trade P&L: ₹{metrics.get('avg_trade', 0):,.2f}")
        print("="*80)

    def plot_results(self):
        """Plot equity curve and other visualizations"""
        try:
            import matplotlib.pyplot as plt

            if not self.equity_curve:
                logger.warning("No equity curve data to plot")
                return

            equity_series = pd.Series([e['equity'] for e in self.equity_curve])
            timestamps = [e['timestamp'] for e in self.equity_curve]

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

            # Equity curve
            ax1.plot(timestamps, equity_series, label='Portfolio Value')
            ax1.axhline(y=self.initial_capital, color='r', linestyle='--', label='Initial Capital')
            ax1.set_title('Equity Curve')
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Portfolio Value (₹)')
            ax1.legend()
            ax1.grid(True)

            # Drawdown
            cummax = equity_series.cummax()
            drawdown = (equity_series - cummax) / cummax * 100
            ax2.fill_between(timestamps, drawdown, 0, alpha=0.3, color='red')
            ax2.set_title('Drawdown')
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Drawdown (%)')
            ax2.grid(True)

            plt.tight_layout()
            plt.savefig('backtest_results.png', dpi=150)
            logger.info("Results plot saved to backtest_results.png")
            plt.show()

        except ImportError:
            logger.warning("matplotlib not available for plotting")
