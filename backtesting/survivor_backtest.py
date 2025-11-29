"""
Survivor Strategy Backtester

Backtesting implementation for the Survivor options trading strategy.
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


class SurvivorBacktest(BacktestEngine):
    """
    Backtesting engine specifically for Survivor Strategy
    """

    def __init__(
        self,
        config: Dict,
        start_date: str,
        end_date: str,
        initial_capital: float = 1000000,
        index_data_source=None,
        options_pricing_model=None
    ):
        """
        Initialize Survivor backtester

        Args:
            config: Survivor strategy configuration
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            initial_capital: Starting capital
            index_data_source: Function to fetch index (NIFTY) historical data
            options_pricing_model: Function to price options (or use simple model)
        """
        super().__init__(
            strategy_class=None,  # We'll implement logic directly
            config=config,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            data_source=index_data_source
        )

        self.options_pricing_model = options_pricing_model or self._simple_option_price

        # Strategy state (mirrors SurvivorStrategy)
        self.nifty_pe_last_value = 0
        self.nifty_ce_last_value = 0
        self.pe_reset_gap_flag = 0
        self.ce_reset_gap_flag = 0

        logger.info("SurvivorBacktest initialized")

    def _simple_option_price(self, strike: float, spot: float, option_type: str, days_to_expiry: int = 7) -> float:
        """
        Simple option pricing model (placeholder)

        In reality, you'd use Black-Scholes or fetch actual historical option prices.

        Args:
            strike: Strike price
            spot: Current spot price
            option_type: 'PE' or 'CE'
            days_to_expiry: Days until expiration

        Returns:
            Estimated option price
        """
        # Simple intrinsic + time value model
        if option_type == 'PE':
            intrinsic = max(strike - spot, 0)
        else:  # CE
            intrinsic = max(spot - strike, 0)

        # Simple time value decay
        time_value = max(0, (days_to_expiry / 7) * 10)  # ₹10 per week

        return intrinsic + time_value

    def _get_option_strike(self, current_price: float, option_type: str, gap: float) -> float:
        """
        Get appropriate option strike based on symbol_gap

        Args:
            current_price: Current index price
            option_type: 'PE' or 'CE'
            gap: Strike gap from current price

        Returns:
            Strike price (rounded to nearest 50)
        """
        if option_type == 'PE':
            target_strike = current_price - gap
        else:  # CE
            target_strike = current_price + gap

        # Round to nearest 50 (common NIFTY strike interval)
        return round(target_strike / 50) * 50

    def _handle_pe_trade(self, current_price: float, timestamp: datetime):
        """
        Handle PE trading logic (mirroring SurvivorStrategy._handle_pe_trade)
        """
        if current_price <= self.nifty_pe_last_value:
            return

        price_diff = round(current_price - self.nifty_pe_last_value, 0)

        if price_diff > self.config['pe_gap']:
            sell_multiplier = int(price_diff / self.config['pe_gap'])

            # Check multiplier threshold
            if sell_multiplier > self.config.get('sell_multiplier_threshold', 5):
                logger.warning(f"PE multiplier {sell_multiplier} exceeds threshold")
                return

            # Update reference value
            self.nifty_pe_last_value += self.config['pe_gap'] * sell_multiplier

            # Get strike and price
            strike = self._get_option_strike(current_price, 'PE', self.config['pe_symbol_gap'])
            option_price = self.options_pricing_model(strike, current_price, 'PE')

            # Check minimum price
            if option_price < self.config.get('min_price_to_sell', 0):
                logger.debug(f"PE option price {option_price} below minimum")
                return

            # Execute trade (SELL PE)
            total_quantity = sell_multiplier * self.config['pe_quantity']
            symbol = f"NIFTY_{strike}_PE"

            self.broker.update_prices({symbol: option_price})

            from brokers import OrderRequest, Exchange, OrderType, TransactionType, ProductType
            req = OrderRequest(
                symbol=symbol,
                exchange=Exchange.NFO,
                transaction_type=TransactionType.SELL,
                quantity=total_quantity,
                product_type=ProductType.MARGIN,
                order_type=OrderType.MARKET,
                price=option_price
            )

            self.broker.place_order(req)

            logger.info(f"[{timestamp}] PE SELL: {symbol} @ ₹{option_price:.2f} × {total_quantity} | Multiplier: {sell_multiplier}")

            # Set reset flag
            self.pe_reset_gap_flag = 1

            # Track for equity curve
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': self.broker.get_portfolio_value(),
                'action': 'PE_SELL',
                'price': current_price
            })

    def _handle_ce_trade(self, current_price: float, timestamp: datetime):
        """
        Handle CE trading logic (mirroring SurvivorStrategy._handle_ce_trade)
        """
        if current_price >= self.nifty_ce_last_value:
            return

        price_diff = round(self.nifty_ce_last_value - current_price, 0)

        if price_diff > self.config['ce_gap']:
            sell_multiplier = int(price_diff / self.config['ce_gap'])

            # Check multiplier threshold
            if sell_multiplier > self.config.get('sell_multiplier_threshold', 5):
                logger.warning(f"CE multiplier {sell_multiplier} exceeds threshold")
                return

            # Update reference value
            self.nifty_ce_last_value -= self.config['ce_gap'] * sell_multiplier

            # Get strike and price
            strike = self._get_option_strike(current_price, 'CE', self.config['ce_symbol_gap'])
            option_price = self.options_pricing_model(strike, current_price, 'CE')

            # Check minimum price
            if option_price < self.config.get('min_price_to_sell', 0):
                logger.debug(f"CE option price {option_price} below minimum")
                return

            # Execute trade (SELL CE)
            total_quantity = sell_multiplier * self.config['ce_quantity']
            symbol = f"NIFTY_{strike}_CE"

            self.broker.update_prices({symbol: option_price})

            from brokers import OrderRequest, Exchange, OrderType, TransactionType, ProductType
            req = OrderRequest(
                symbol=symbol,
                exchange=Exchange.NFO,
                transaction_type=TransactionType.SELL,
                quantity=total_quantity,
                product_type=ProductType.MARGIN,
                order_type=OrderType.MARKET,
                price=option_price
            )

            self.broker.place_order(req)

            logger.info(f"[{timestamp}] CE SELL: {symbol} @ ₹{option_price:.2f} × {total_quantity} | Multiplier: {sell_multiplier}")

            # Set reset flag
            self.ce_reset_gap_flag = 1

            # Track for equity curve
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': self.broker.get_portfolio_value(),
                'action': 'CE_SELL',
                'price': current_price
            })

    def _reset_reference_values(self, current_price: float):
        """
        Reset reference values when market moves favorably
        """
        # PE Reset
        if (self.nifty_pe_last_value - current_price) > self.config.get('pe_reset_gap', 0) and self.pe_reset_gap_flag:
            logger.debug(f"Resetting PE value from {self.nifty_pe_last_value} to {current_price + self.config['pe_reset_gap']}")
            self.nifty_pe_last_value = current_price + self.config['pe_reset_gap']

        # CE Reset
        if (current_price - self.nifty_ce_last_value) > self.config.get('ce_reset_gap', 0) and self.ce_reset_gap_flag:
            logger.debug(f"Resetting CE value from {self.nifty_ce_last_value} to {current_price - self.config['ce_reset_gap']}")
            self.nifty_ce_last_value = current_price - self.config['ce_reset_gap']

    def run(self) -> Dict[str, Any]:
        """
        Run the Survivor strategy backtest

        Returns:
            Dictionary containing backtest results
        """
        logger.info(f"Running Survivor backtest from {self.start_date} to {self.end_date}")

        # Load index data (NIFTY)
        index_symbol = self.config.get('index_symbol', 'NSE:NIFTY 50')
        index_data = self.load_historical_data(index_symbol)

        if index_data.empty:
            logger.error("No historical data available")
            return {}

        # Initialize reference values
        initial_price = index_data['close'].iloc[0]
        self.nifty_pe_last_value = self.config.get('pe_start_point', 0) or initial_price
        self.nifty_ce_last_value = self.config.get('ce_start_point', 0) or initial_price

        logger.info(f"Initial PE reference: {self.nifty_pe_last_value}, CE reference: {self.nifty_ce_last_value}")

        # Initialize equity curve
        self.equity_curve.append({
            'timestamp': index_data['timestamp'].iloc[0],
            'equity': self.initial_capital,
            'action': 'START',
            'price': initial_price
        })

        # Main backtest loop
        for idx, row in index_data.iterrows():
            current_price = row['close']
            timestamp = row['timestamp']

            # Update broker prices
            self.broker.update_prices({index_symbol: current_price})

            # Execute strategy logic
            self._handle_pe_trade(current_price, timestamp)
            self._handle_ce_trade(current_price, timestamp)
            self._reset_reference_values(current_price)

            # Record equity periodically (every 100 bars to avoid too much data)
            if idx % 100 == 0:
                self.equity_curve.append({
                    'timestamp': timestamp,
                    'equity': self.broker.get_portfolio_value(),
                    'action': 'TRACK',
                    'price': current_price
                })

        # Final equity snapshot
        self.equity_curve.append({
            'timestamp': index_data['timestamp'].iloc[-1],
            'equity': self.broker.get_portfolio_value(),
            'action': 'END',
            'price': index_data['close'].iloc[-1]
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
        report_path = os.path.join(save_dir, 'survivor_backtest_report.txt')
        perf.generate_report(report_path)

        # Save metrics JSON
        metrics_path = os.path.join(save_dir, 'survivor_metrics.json')
        perf.save_metrics_json(metrics_path)

        # Save trades CSV
        trades_path = os.path.join(save_dir, 'survivor_trades.csv')
        perf.save_trades_csv(trades_path)

        # Generate plots
        plot_path = os.path.join(save_dir, 'survivor_analysis.png')
        perf.plot_analysis(plot_path)

        logger.info(f"Reports saved to {save_dir}/")
