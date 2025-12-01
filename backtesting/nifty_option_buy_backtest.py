"""
Backtesting module for NIFTY50 Options Buying Strategy
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brokers.core.schemas import OrderRequest, Position, Quote
from brokers.core.enums import Exchange, OrderType, ProductType, TransactionType
from backtesting.engine import MockBroker


class NiftyOptionBuyBacktest:
    """Backtest engine for NIFTY Options Buying Strategy"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize mock broker
        self.broker = MockBroker(initial_capital=config.get('initial_capital', 100000))

        # Strategy parameters
        self.lot_size = config.get('lot_size', 50)
        self.quantity = config.get('quantity', 50)

        # Strike offsets
        self.ce_offset = -100
        self.pe_offset = 100

        # Entry/Exit percentages
        self.entry_trigger_pct = 1.015  # Entry when price reaches day_low + 1.5%
        self.stop_loss_pct = 0.988  # Stop loss: 1.2% below entry
        self.target_pct = 1.018  # Target: 1.8% above entry

        # State tracking
        self.current_day = None
        self.day_low = None
        self.day_open = None
        self.entry_price = None
        self.stop_loss_price = None
        self.target_price = None

        # Selected strikes
        self.ce_strike = None
        self.pe_strike = None
        self.ce_symbol = None
        self.pe_symbol = None

        # Position tracking
        self.ce_entered = False
        self.pe_entered = False
        self.ce_entry_price = None
        self.pe_entry_price = None
        self.ce_entry_time = None
        self.pe_entry_time = None

        # Trade log
        self.trades = []
        self.daily_stats = []

        # Results tracking
        self.equity_curve = []
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    def _round_to_strike(self, price: float, strike_gap: int = 50) -> int:
        """Round price to nearest strike price"""
        return int(round(price / strike_gap) * strike_gap)

    def _get_weekly_expiry(self, current_date: datetime) -> datetime:
        """Get the weekly expiry date (Thursday of current week)"""
        days_until_thursday = (3 - current_date.weekday()) % 7
        if days_until_thursday == 0 and current_date.hour >= 15:
            days_until_thursday = 7
        expiry_date = current_date + timedelta(days=days_until_thursday)
        return expiry_date.replace(hour=15, minute=30, second=0, microsecond=0)

    def _format_option_symbol(self, strike: int, option_type: str, expiry: datetime) -> str:
        """Format option symbol"""
        expiry_str = expiry.strftime("%y%b").upper()
        symbol = f"NFO:NIFTY{expiry_str}{strike}{option_type}"
        return symbol

    def _calculate_option_price(self, spot_price: float, strike: int, option_type: str,
                                time_to_expiry_days: float, volatility: float = 0.15) -> float:
        """
        Calculate theoretical option price using simplified Black-Scholes

        For backtesting purposes, we use a simplified model:
        - ATM options have base value of ~2-3% of spot
        - OTM options decay based on distance from spot
        - Time decay applied
        """
        # Distance from strike
        if option_type == "CE":
            moneyness = (spot_price - strike) / spot_price
        else:  # PE
            moneyness = (strike - spot_price) / spot_price

        # Base premium (as % of spot)
        if moneyness > 0:  # ITM
            intrinsic = abs(spot_price - strike)
            time_value = spot_price * 0.01 * (time_to_expiry_days / 7)
            premium = intrinsic + time_value
        else:  # OTM or ATM
            # Premium decays with distance from ATM
            distance_pct = abs(moneyness)
            base_premium = spot_price * 0.025  # 2.5% for ATM
            decay_factor = np.exp(-distance_pct * 10)  # Exponential decay
            time_factor = (time_to_expiry_days / 7)
            premium = base_premium * decay_factor * time_factor

        # Add volatility component
        premium *= (1 + volatility)

        return max(premium, 0.5)  # Minimum 0.5

    def _get_option_price(self, symbol: str, spot_price: float, strike: int,
                         option_type: str, current_date: datetime) -> float:
        """Get option price (from broker or calculated)"""
        try:
            # Check if price already registered with mock broker
            quote = self.broker.get_quote(symbol)
            return quote.last_price
        except:
            # Calculate theoretical price
            expiry = self._get_weekly_expiry(current_date)
            time_to_expiry = (expiry - current_date).total_seconds() / (24 * 3600)
            return self._calculate_option_price(spot_price, strike, option_type,
                                               time_to_expiry)

    def _select_daily_strikes(self, current_price: float, current_date: datetime):
        """Select CE and PE strikes for the day"""
        expiry = self._get_weekly_expiry(current_date)

        # Calculate strikes
        self.ce_strike = self._round_to_strike(current_price + self.ce_offset)
        self.pe_strike = self._round_to_strike(current_price + self.pe_offset)

        # Format symbols
        self.ce_symbol = self._format_option_symbol(self.ce_strike, "CE", expiry)
        self.pe_symbol = self._format_option_symbol(self.pe_strike, "PE", expiry)

        self.logger.info(f"Selected strikes for {current_date.date()}: "
                        f"CE={self.ce_strike}, PE={self.pe_strike}, Expiry={expiry.date()}")

    def _reset_daily_state(self, current_date: datetime, open_price: float):
        """Reset daily tracking variables"""
        self.current_day = current_date.date()
        self.day_open = open_price
        self.day_low = open_price
        self.entry_price = None
        self.stop_loss_price = None
        self.target_price = None

        # Reset position flags
        self.ce_entered = False
        self.pe_entered = False
        self.ce_entry_price = None
        self.pe_entry_price = None
        self.ce_entry_time = None
        self.pe_entry_time = None

        # Select new strikes
        self._select_daily_strikes(open_price, current_date)

    def _update_day_low(self, current_price: float):
        """Update day low and recalculate entry trigger"""
        if current_price < self.day_low:
            self.day_low = current_price
            self.entry_price = self.day_low * self.entry_trigger_pct
            # Stop loss and target will be set relative to actual entry price when we enter

    def _enter_positions(self, spot_price: float, timestamp: datetime):
        """Enter both CE and PE positions"""
        # Set stop loss and target based on entry price
        self.stop_loss_price = spot_price * self.stop_loss_pct
        self.target_price = spot_price * self.target_pct

        # Get option prices
        expiry = self._get_weekly_expiry(timestamp)
        time_to_expiry = (expiry - timestamp).total_seconds() / (24 * 3600)

        ce_price = self._calculate_option_price(spot_price, self.ce_strike, "CE", time_to_expiry)
        pe_price = self._calculate_option_price(spot_price, self.pe_strike, "PE", time_to_expiry)

        # Register prices with mock broker
        self.broker.update_prices({
            self.ce_symbol: ce_price,
            self.pe_symbol: pe_price
        })

        # Place CE order
        ce_order = OrderRequest(
            symbol=self.ce_symbol,
            exchange=Exchange.NFO,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            product_type=ProductType.INTRADAY,
            quantity=self.quantity,
            price=None
        )
        self.broker.place_order(ce_order)
        self.ce_entered = True
        self.ce_entry_price = ce_price
        self.ce_entry_time = timestamp

        # Place PE order
        pe_order = OrderRequest(
            symbol=self.pe_symbol,
            exchange=Exchange.NFO,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            product_type=ProductType.INTRADAY,
            quantity=self.quantity,
            price=None
        )
        self.broker.place_order(pe_order)
        self.pe_entered = True
        self.pe_entry_price = pe_price
        self.pe_entry_time = timestamp

        self.logger.info(f"Entered positions at {timestamp}: "
                        f"CE={self.ce_symbol}@{ce_price:.2f}, "
                        f"PE={self.pe_symbol}@{pe_price:.2f}")

    def _exit_positions(self, spot_price: float, timestamp: datetime, reason: str):
        """Exit both CE and PE positions"""
        # Get current option prices
        expiry = self._get_weekly_expiry(timestamp)
        time_to_expiry = (expiry - timestamp).total_seconds() / (24 * 3600)

        ce_exit_price = self._calculate_option_price(spot_price, self.ce_strike, "CE", time_to_expiry)
        pe_exit_price = self._calculate_option_price(spot_price, self.pe_strike, "PE", time_to_expiry)

        # Update prices
        self.broker.update_prices({
            self.ce_symbol: ce_exit_price,
            self.pe_symbol: pe_exit_price
        })

        # Exit CE
        if self.ce_entered:
            ce_order = OrderRequest(
                symbol=self.ce_symbol,
                exchange=Exchange.NFO,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.SELL,
                product_type=ProductType.INTRADAY,
                quantity=self.quantity,
                price=None
            )
            self.broker.place_order(ce_order)

            ce_pnl = (ce_exit_price - self.ce_entry_price) * self.quantity

            self.trades.append({
                'timestamp': timestamp,
                'symbol': self.ce_symbol,
                'type': 'CE',
                'entry_time': self.ce_entry_time,
                'exit_time': timestamp,
                'entry_price': self.ce_entry_price,
                'exit_price': ce_exit_price,
                'quantity': self.quantity,
                'pnl': ce_pnl,
                'reason': reason
            })

            self.total_trades += 1
            if ce_pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1

        # Exit PE
        if self.pe_entered:
            pe_order = OrderRequest(
                symbol=self.pe_symbol,
                exchange=Exchange.NFO,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.SELL,
                product_type=ProductType.INTRADAY,
                quantity=self.quantity,
                price=None
            )
            self.broker.place_order(pe_order)

            pe_pnl = (pe_exit_price - self.pe_entry_price) * self.quantity

            self.trades.append({
                'timestamp': timestamp,
                'symbol': self.pe_symbol,
                'type': 'PE',
                'entry_time': self.pe_entry_time,
                'exit_time': timestamp,
                'entry_price': self.pe_entry_price,
                'exit_price': pe_exit_price,
                'quantity': self.quantity,
                'pnl': pe_pnl,
                'reason': reason
            })

            self.total_trades += 1
            if pe_pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1

        total_pnl = (ce_exit_price - self.ce_entry_price + pe_exit_price - self.pe_entry_price) * self.quantity

        self.logger.info(f"Exited positions [{reason}] at {timestamp}: "
                        f"CE PnL={(ce_exit_price - self.ce_entry_price) * self.quantity:.2f}, "
                        f"PE PnL={(pe_exit_price - self.pe_entry_price) * self.quantity:.2f}, "
                        f"Total PnL={total_pnl:.2f}")

        self.ce_entered = False
        self.pe_entered = False

    def run(self, spot_data: pd.DataFrame) -> Dict:
        """
        Run backtest on historical spot data

        Args:
            spot_data: DataFrame with columns ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        Returns:
            Dictionary with backtest results
        """
        self.logger.info(f"Starting backtest with {len(spot_data)} candles")

        for idx, row in spot_data.iterrows():
            timestamp = row['timestamp']
            current_date = timestamp.date()

            # Check if new day
            if self.current_day != current_date:
                # Close any open positions from previous day
                if self.ce_entered or self.pe_entered:
                    self._exit_positions(row['close'], timestamp, "EOD")

                # Reset for new day
                self._reset_daily_state(timestamp, row['open'])

            # Update day low
            self._update_day_low(row['low'])

            # Skip if no entry levels set yet
            if self.entry_price is None:
                continue

            # Check for entry
            if not self.ce_entered and not self.pe_entered:
                if row['high'] >= self.entry_price:
                    self.logger.info(f"Entry triggered! day_low={self.day_low:.2f}, "
                                   f"entry_price={self.entry_price:.2f}, high={row['high']:.2f}")
                    self._enter_positions(self.entry_price, timestamp)

            # Check for exit if in position
            elif self.ce_entered or self.pe_entered:
                # Check stop loss
                if row['low'] <= self.stop_loss_price:
                    self._exit_positions(self.stop_loss_price, timestamp, "Stop Loss")

                # Check target
                elif row['high'] >= self.target_price:
                    self._exit_positions(self.target_price, timestamp, "Target")

            # Update equity curve
            equity = self.broker.get_portfolio_value()
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': equity
            })

        # Close any remaining positions
        if self.ce_entered or self.pe_entered:
            last_row = spot_data.iloc[-1]
            self._exit_positions(last_row['close'], last_row['timestamp'], "Backtest End")

        return self._generate_results()

    def _generate_results(self) -> Dict:
        """Generate backtest results"""
        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)

        # Calculate metrics
        total_pnl = trades_df['pnl'].sum() if len(trades_df) > 0 else 0
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        final_equity = self.broker.get_portfolio_value()
        initial_capital = self.config.get('initial_capital', 100000)
        total_return = ((final_equity - initial_capital) / initial_capital) * 100

        results = {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_return_pct': total_return,
            'final_equity': final_equity,
            'initial_capital': initial_capital,
            'trades_df': trades_df,
            'equity_df': equity_df
        }

        return results
