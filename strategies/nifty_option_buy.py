"""
NIFTY50 Options Buying Strategy

Strategy Logic:
1. Strike Selection (Daily at market open):
   - CE (Call): Nearest strike at (current_price - 100)
   - PE (Put): Nearest strike at (current_price + 100)
   - Use current week expiry options

2. Entry Trigger:
   - Enter when NIFTY spot price reaches: day_low + 1.5%

3. Stop Loss:
   - Exit when NIFTY spot price reaches: day_low + 1.2%

4. Target:
   - Exit when NIFTY spot price reaches: day_low + 1.8%

5. Daily Reset:
   - Close all positions at end of day
   - Select new strikes next day
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brokers.core.schemas import OrderRequest
from brokers.core.enums import Exchange, OrderType, ProductType, TransactionType
from brokers.core.gateway import BrokerGateway


class NiftyOptionBuyStrategy:
    """NIFTY50 Options Buying Strategy"""

    def __init__(self, broker: BrokerGateway, config: Dict):
        self.broker = broker
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Strategy parameters
        self.base_symbol = config.get('base_symbol', 'NSE:NIFTY 50')
        self.lot_size = config.get('lot_size', 50)  # NIFTY lot size
        self.quantity = config.get('quantity', 50)  # 1 lot

        # Strike selection offsets
        self.ce_offset = -100  # CE at spot - 100
        self.pe_offset = 100   # PE at spot + 100

        # Entry/Exit percentages (from day low)
        self.entry_pct = 1.015  # day_low * 1.5% = day_low * 1.015
        self.stop_loss_pct = 1.012  # day_low * 1.2% = day_low * 1.012
        self.target_pct = 1.018  # day_low * 1.8% = day_low * 1.018

        # State tracking
        self.current_day = None
        self.day_low = None
        self.entry_price = None
        self.stop_loss_price = None
        self.target_price = None

        # Selected strikes
        self.ce_strike = None
        self.pe_strike = None
        self.ce_symbol = None
        self.pe_symbol = None

        # Position tracking
        self.ce_position = None
        self.pe_position = None
        self.ce_entry_option_price = None
        self.pe_entry_option_price = None

        # Flags
        self.ce_entered = False
        self.pe_entered = False

        self.logger.info("NiftyOptionBuy strategy initialized")

    def _round_to_strike(self, price: float, strike_gap: int = 50) -> int:
        """Round price to nearest strike price"""
        return int(round(price / strike_gap) * strike_gap)

    def _get_weekly_expiry(self, current_date: datetime) -> datetime:
        """Get the weekly expiry date (Thursday of current week)"""
        # NIFTY weekly options expire on Thursday
        days_until_thursday = (3 - current_date.weekday()) % 7
        if days_until_thursday == 0 and current_date.hour >= 15:
            # If it's Thursday after 3:30 PM, use next week
            days_until_thursday = 7
        expiry_date = current_date + timedelta(days=days_until_thursday)
        return expiry_date.replace(hour=15, minute=30, second=0, microsecond=0)

    def _format_option_symbol(self, strike: int, option_type: str, expiry: datetime) -> str:
        """
        Format option symbol for trading
        Example: NFO:NIFTY24DEC24500CE
        """
        expiry_str = expiry.strftime("%y%b").upper()  # e.g., "24DEC"
        symbol = f"NFO:NIFTY{expiry_str}{strike}{option_type}"
        return symbol

    def _select_daily_strikes(self, current_price: float, current_date: datetime):
        """Select CE and PE strikes for the day"""
        # Get weekly expiry
        expiry = self._get_weekly_expiry(current_date)

        # Calculate strikes
        self.ce_strike = self._round_to_strike(current_price + self.ce_offset)
        self.pe_strike = self._round_to_strike(current_price + self.pe_offset)

        # Format symbols
        self.ce_symbol = self._format_option_symbol(self.ce_strike, "CE", expiry)
        self.pe_symbol = self._format_option_symbol(self.pe_strike, "PE", expiry)

        self.logger.info(f"Selected strikes for {current_date.date()}: "
                        f"CE={self.ce_strike} ({self.ce_symbol}), "
                        f"PE={self.pe_strike} ({self.pe_symbol}), "
                        f"Expiry={expiry.date()}")

    def _reset_daily_state(self, current_date: datetime, current_price: float):
        """Reset daily tracking variables"""
        self.current_day = current_date.date()
        self.day_low = current_price
        self.entry_price = None
        self.stop_loss_price = None
        self.target_price = None

        # Reset positions
        self.ce_position = None
        self.pe_position = None
        self.ce_entry_option_price = None
        self.pe_entry_option_price = None
        self.ce_entered = False
        self.pe_entered = False

        # Select new strikes
        self._select_daily_strikes(current_price, current_date)

        self.logger.info(f"Reset daily state for {self.current_day}, initial low={self.day_low}")

    def _update_day_low(self, current_price: float):
        """Update day low and recalculate entry/exit levels"""
        if current_price < self.day_low:
            self.day_low = current_price

            # Recalculate levels
            self.entry_price = self.day_low * self.entry_pct
            self.stop_loss_price = self.day_low * self.stop_loss_pct
            self.target_price = self.day_low * self.target_pct

            self.logger.debug(f"Updated day_low={self.day_low:.2f}, "
                            f"entry={self.entry_price:.2f}, "
                            f"SL={self.stop_loss_price:.2f}, "
                            f"target={self.target_price:.2f}")

    def _check_entry(self, current_price: float) -> bool:
        """Check if entry condition is met"""
        if self.entry_price is None:
            return False
        return current_price >= self.entry_price

    def _check_stop_loss(self, current_price: float) -> bool:
        """Check if stop loss is hit"""
        if self.stop_loss_price is None:
            return False
        return current_price <= self.stop_loss_price

    def _check_target(self, current_price: float) -> bool:
        """Check if target is hit"""
        if self.target_price is None:
            return False
        return current_price >= self.target_price

    def _enter_ce_position(self, current_date: datetime) -> Optional[Order]:
        """Enter CE (Call) position"""
        try:
            # Get CE option price
            quote = self.broker.get_quote(self.ce_symbol)
            option_price = quote.last_price

            # Place buy order
            order = OrderRequest(
                symbol=self.ce_symbol,
                exchange=Exchange.NFO,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY,
                product_type=ProductType.INTRADAY,
                quantity=self.quantity,
                price=None
            )

            self.ce_position = order
            self.ce_entry_option_price = option_price
            self.ce_entered = True

            self.logger.info(f"Entered CE position: {self.ce_symbol} @ {option_price:.2f}, "
                           f"qty={self.quantity}, time={current_date}")

            return order

        except Exception as e:
            self.logger.error(f"Error entering CE position: {e}")
            return None

    def _enter_pe_position(self, current_date: datetime) -> Optional[Order]:
        """Enter PE (Put) position"""
        try:
            # Get PE option price
            quote = self.broker.get_quote(self.pe_symbol)
            option_price = quote.last_price

            # Place buy order
            order = OrderRequest(
                symbol=self.pe_symbol,
                exchange=Exchange.NFO,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY,
                product_type=ProductType.INTRADAY,
                quantity=self.quantity,
                price=None
            )

            self.pe_position = order
            self.pe_entry_option_price = option_price
            self.pe_entered = True

            self.logger.info(f"Entered PE position: {self.pe_symbol} @ {option_price:.2f}, "
                           f"qty={self.quantity}, time={current_date}")

            return order

        except Exception as e:
            self.logger.error(f"Error entering PE position: {e}")
            return None

    def _exit_ce_position(self, reason: str, current_date: datetime) -> Optional[Order]:
        """Exit CE position"""
        if not self.ce_entered:
            return None

        try:
            quote = self.broker.get_quote(self.ce_symbol)
            exit_price = quote.last_price

            order = OrderRequest(
                symbol=self.ce_symbol,
                exchange=Exchange.NFO,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.SELL,
                product_type=ProductType.INTRADAY,
                quantity=self.quantity,
                price=None
            )

            pnl = (exit_price - self.ce_entry_option_price) * self.quantity

            self.logger.info(f"Exited CE position [{reason}]: {self.ce_symbol}, "
                           f"entry={self.ce_entry_option_price:.2f}, "
                           f"exit={exit_price:.2f}, "
                           f"PnL={pnl:.2f}, time={current_date}")

            self.ce_entered = False
            self.ce_position = None

            return order

        except Exception as e:
            self.logger.error(f"Error exiting CE position: {e}")
            return None

    def _exit_pe_position(self, reason: str, current_date: datetime) -> Optional[Order]:
        """Exit PE position"""
        if not self.pe_entered:
            return None

        try:
            quote = self.broker.get_quote(self.pe_symbol)
            exit_price = quote.last_price

            order = OrderRequest(
                symbol=self.pe_symbol,
                exchange=Exchange.NFO,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.SELL,
                product_type=ProductType.INTRADAY,
                quantity=self.quantity,
                price=None
            )

            pnl = (exit_price - self.pe_entry_option_price) * self.quantity

            self.logger.info(f"Exited PE position [{reason}]: {self.pe_symbol}, "
                           f"entry={self.pe_entry_option_price:.2f}, "
                           f"exit={exit_price:.2f}, "
                           f"PnL={pnl:.2f}, time={current_date}")

            self.pe_entered = False
            self.pe_position = None

            return order

        except Exception as e:
            self.logger.error(f"Error exiting PE position: {e}")
            return None

    def on_tick(self, timestamp: datetime, data: Dict) -> list:
        """
        Process each tick/candle

        Args:
            timestamp: Current timestamp
            data: Dict with 'open', 'high', 'low', 'close', 'volume' for NIFTY spot

        Returns:
            List of orders to place
        """
        orders = []
        current_price = data['close']
        current_date = timestamp.date()

        # Check if new day
        if self.current_day != current_date:
            # Close any open positions from previous day
            if self.ce_entered:
                order = self._exit_ce_position("EOD", timestamp)
                if order:
                    orders.append(order)
            if self.pe_entered:
                order = self._exit_pe_position("EOD", timestamp)
                if order:
                    orders.append(order)

            # Reset for new day
            self._reset_daily_state(timestamp, current_price)

        # Update day low
        self._update_day_low(data['low'])

        # Check for entry
        if not self.ce_entered and not self.pe_entered and self._check_entry(current_price):
            # Enter both CE and PE positions
            ce_order = self._enter_ce_position(timestamp)
            pe_order = self._enter_pe_position(timestamp)

            if ce_order:
                orders.append(ce_order)
            if pe_order:
                orders.append(pe_order)

        # Check for exit conditions if in position
        if self.ce_entered or self.pe_entered:
            # Check stop loss
            if self._check_stop_loss(current_price):
                if self.ce_entered:
                    order = self._exit_ce_position("Stop Loss", timestamp)
                    if order:
                        orders.append(order)
                if self.pe_entered:
                    order = self._exit_pe_position("Stop Loss", timestamp)
                    if order:
                        orders.append(order)

            # Check target
            elif self._check_target(current_price):
                if self.ce_entered:
                    order = self._exit_ce_position("Target", timestamp)
                    if order:
                        orders.append(order)
                if self.pe_entered:
                    order = self._exit_pe_position("Target", timestamp)
                    if order:
                        orders.append(order)

        return orders

    def get_status(self) -> Dict:
        """Get current strategy status"""
        return {
            'current_day': str(self.current_day),
            'day_low': self.day_low,
            'entry_price': self.entry_price,
            'stop_loss_price': self.stop_loss_price,
            'target_price': self.target_price,
            'ce_strike': self.ce_strike,
            'pe_strike': self.pe_strike,
            'ce_symbol': self.ce_symbol,
            'pe_symbol': self.pe_symbol,
            'ce_entered': self.ce_entered,
            'pe_entered': self.pe_entered,
            'ce_entry_price': self.ce_entry_option_price,
            'pe_entry_price': self.pe_entry_option_price
        }
