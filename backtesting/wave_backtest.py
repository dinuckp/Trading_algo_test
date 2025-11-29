"""
Wave Strategy Backtester

Backtesting implementation for the Wave market-making strategy.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
from logger import logger
from backtesting.engine import BacktestEngine, MockBroker
from backtesting.metrics import PerformanceMetrics


class WaveBacktest(BacktestEngine):
    """
    Backtesting engine specifically for Wave Strategy
    """

    def __init__(
        self,
        config: Dict,
        start_date: str,
        end_date: str,
        initial_capital: float = 1000000,
        futures_data_source=None
    ):
        """
        Initialize Wave backtester

        Args:
            config: Wave strategy configuration
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            initial_capital: Starting capital
            futures_data_source: Function to fetch futures historical data
        """
        super().__init__(
            strategy_class=None,  # We'll implement logic directly
            config=config,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            data_source=futures_data_source
        )

        # Wave strategy state
        self.scraper_last_price = 0
        self.active_buy_order = None
        self.active_sell_order = None
        self.initial_position = 0
        self.lot_size = config.get('lot_size', 75)

        # Simplified multiplier scale (first few levels)
        self.multiplier_scale = {
            "0": [1.0, 1.0],
            "1": [1.3, 1.0],
            "2": [1.7, 1.0],
            "3": [2.5, 1.0],
            "-1": [1.0, 1.3],
            "-2": [1.0, 1.7],
            "-3": [1.0, 2.5],
        }

        logger.info("WaveBacktest initialized")

    def _get_scaled_gaps(self, position_diff: float) -> tuple:
        """
        Calculate scaled gaps based on position imbalance
        """
        diff_key = str(int(position_diff))

        if diff_key not in self.multiplier_scale:
            mult = [100.0, 1.0] if position_diff > 0 else [1.0, 100.0]
        else:
            mult = self.multiplier_scale[diff_key]

        buy_gap = round(self.config['buy_gap'] * mult[0], 1)
        sell_gap = round(self.config['sell_gap'] * mult[1], 1)

        return buy_gap, sell_gap

    def _place_wave_orders(self, current_price: float, timestamp: datetime, position_diff: float):
        """
        Place buy and sell limit orders based on current price and gaps
        """
        # Calculate scaled gaps
        buy_gap, sell_gap = self._get_scaled_gaps(position_diff)

        buy_price = current_price - buy_gap
        sell_price = current_price + sell_gap

        symbol = self.config.get('symbol_name', 'NIFTY_FUT')

        # Update broker prices
        self.broker.update_prices({symbol: current_price})

        # Place buy order
        if self.active_buy_order is None:
            from brokers import OrderRequest, Exchange, OrderType, TransactionType, ProductType

            req = OrderRequest(
                symbol=symbol,
                exchange=Exchange.NFO,
                transaction_type=TransactionType.BUY,
                quantity=self.config['buy_quantity'],
                product_type=ProductType.MARGIN,
                order_type=OrderType.LIMIT,
                price=buy_price
            )

            # Store as pending order (will check fills later)
            self.active_buy_order = {
                'price': buy_price,
                'quantity': self.config['buy_quantity'],
                'timestamp': timestamp
            }

            logger.debug(f"[{timestamp}] BUY order placed @ ₹{buy_price:.2f} (gap: {buy_gap})")

        # Place sell order
        if self.active_sell_order is None:
            from brokers import OrderRequest, Exchange, OrderType, TransactionType, ProductType

            req = OrderRequest(
                symbol=symbol,
                exchange=Exchange.NFO,
                transaction_type=TransactionType.SELL,
                quantity=self.config['sell_quantity'],
                product_type=ProductType.MARGIN,
                order_type=OrderType.LIMIT,
                price=sell_price
            )

            self.active_sell_order = {
                'price': sell_price,
                'quantity': self.config['sell_quantity'],
                'timestamp': timestamp
            }

            logger.debug(f"[{timestamp}] SELL order placed @ ₹{sell_price:.2f} (gap: {sell_gap})")

    def _check_order_fills(self, row: pd.Series, symbol: str):
        """
        Check if any pending orders got filled based on price movement

        In reality, this is a simplification. Real fills depend on order book depth.
        """
        low = row['low']
        high = row['high']
        close = row['close']
        timestamp = row['timestamp']

        # Check buy order fill
        if self.active_buy_order and low <= self.active_buy_order['price']:
            # Buy order filled
            fill_price = self.active_buy_order['price']

            self.broker.update_prices({symbol: fill_price})

            from brokers import OrderRequest, Exchange, OrderType, TransactionType, ProductType
            req = OrderRequest(
                symbol=symbol,
                exchange=Exchange.NFO,
                transaction_type=TransactionType.BUY,
                quantity=self.active_buy_order['quantity'],
                product_type=ProductType.MARGIN,
                order_type=OrderType.MARKET,
                price=fill_price
            )

            self.broker.place_order(req)

            logger.info(f"[{timestamp}] BUY FILLED @ ₹{fill_price:.2f} × {self.active_buy_order['quantity']}")

            # Update scraper last price
            self.scraper_last_price = fill_price

            # Cancel sell order
            self.active_sell_order = None
            self.active_buy_order = None

            # Track equity
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': self.broker.get_portfolio_value(),
                'action': 'BUY_FILL',
                'price': fill_price
            })

        # Check sell order fill
        elif self.active_sell_order and high >= self.active_sell_order['price']:
            # Sell order filled
            fill_price = self.active_sell_order['price']

            self.broker.update_prices({symbol: fill_price})

            from brokers import OrderRequest, Exchange, OrderType, TransactionType, ProductType
            req = OrderRequest(
                symbol=symbol,
                exchange=Exchange.NFO,
                transaction_type=TransactionType.SELL,
                quantity=self.active_sell_order['quantity'],
                product_type=ProductType.MARGIN,
                order_type=OrderType.MARKET,
                price=fill_price
            )

            self.broker.place_order(req)

            logger.info(f"[{timestamp}] SELL FILLED @ ₹{fill_price:.2f} × {self.active_sell_order['quantity']}")

            # Update scraper last price
            self.scraper_last_price = fill_price

            # Cancel buy order
            self.active_buy_order = None
            self.active_sell_order = None

            # Track equity
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': self.broker.get_portfolio_value(),
                'action': 'SELL_FILL',
                'price': fill_price
            })

    def _get_position_diff(self) -> float:
        """
        Calculate current position difference from initial position
        """
        positions = self.broker.get_positions()
        symbol = self.config.get('symbol_name', 'NIFTY_FUT')

        current_qty = 0
        for pos in positions:
            if symbol in pos.symbol:
                current_qty = pos.quantity_total

        return (current_qty - self.initial_position) / self.lot_size

    def run(self) -> Dict[str, Any]:
        """
        Run the Wave strategy backtest

        Returns:
            Dictionary containing backtest results
        """
        logger.info(f"Running Wave backtest from {self.start_date} to {self.end_date}")

        # Load futures data
        symbol = self.config.get('symbol_name', 'NIFTY_FUT')
        futures_data = self.load_historical_data(symbol)

        if futures_data.empty:
            logger.error("No historical data available")
            return {}

        # Initialize
        initial_price = futures_data['close'].iloc[0]
        self.scraper_last_price = initial_price
        self.initial_position = 0

        logger.info(f"Initial futures price: ₹{initial_price:.2f}")

        # Initialize equity curve
        self.equity_curve.append({
            'timestamp': futures_data['timestamp'].iloc[0],
            'equity': self.initial_capital,
            'action': 'START',
            'price': initial_price
        })

        # Main backtest loop
        for idx, row in futures_data.iterrows():
            current_price = row['close']
            timestamp = row['timestamp']

            # Check if any pending orders filled
            self._check_order_fills(row, symbol)

            # Calculate position difference
            position_diff = self._get_position_diff()

            # Place new wave orders if none active
            if self.active_buy_order is None and self.active_sell_order is None:
                self._place_wave_orders(current_price, timestamp, position_diff)

            # Record equity periodically
            if idx % 100 == 0:
                self.equity_curve.append({
                    'timestamp': timestamp,
                    'equity': self.broker.get_portfolio_value(),
                    'action': 'TRACK',
                    'price': current_price
                })

        # Final equity snapshot
        self.equity_curve.append({
            'timestamp': futures_data['timestamp'].iloc[-1],
            'equity': self.broker.get_portfolio_value(),
            'action': 'END',
            'price': futures_data['close'].iloc[-1]
        })

        logger.info(f"Backtest complete. Total trades: {len(self.broker.trades)}")

        return {
            'equity_curve': self.equity_curve,
            'trades': self.broker.trades,
            'metrics': self.calculate_metrics()
        }

    def generate_report(self, save_dir: str = 'backtest_results'):
        """
        Generate comprehensive backtest report

        Args:
            save_dir: Directory to save report files
        """
        import os
        os.makedirs(save_dir, exist_ok=True)

        # Calculate metrics
        metrics = self.calculate_metrics()

        # Create performance metrics object
        perf = PerformanceMetrics(self.broker.trades, self.equity_curve)

        # Print results to console
        self.print_results()

        # Generate text report
        report_path = os.path.join(save_dir, 'wave_backtest_report.txt')
        perf.generate_report(report_path)

        # Save metrics JSON
        metrics_path = os.path.join(save_dir, 'wave_metrics.json')
        perf.save_metrics_json(metrics_path)

        # Save trades CSV
        trades_path = os.path.join(save_dir, 'wave_trades.csv')
        perf.save_trades_csv(trades_path)

        # Generate plots
        plot_path = os.path.join(save_dir, 'wave_analysis.png')
        perf.plot_analysis(plot_path)

        logger.info(f"Reports saved to {save_dir}/")
