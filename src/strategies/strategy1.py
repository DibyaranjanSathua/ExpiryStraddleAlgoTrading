"""
File:           strategy1.py
Author:         Dibyaranjan Sathua
Created on:     22/08/22, 9:30 pm
"""
import time
from typing import Optional
import datetime
import math

from src.strategies.base_strategy import BaseStrategy
from src.utils import utc2ist, istnow, make_ist_aware
from src.strategies.instrument import Instrument, PairInstrument, Action
from src.price_monitor.price_monitor import PriceMonitor, PriceRegister
from src.utils.logger import LogFacade


logger: LogFacade = LogFacade.get_logger("strategy1")


class Strategy1(BaseStrategy):
    """ Expiry day strategy for shorting straddle """
    STRATEGY_CODE: str = "strategy1"
    QUANTITY: int = 50
    SL_PERCENT: float = 1.25
    TARGET_PERCENT: float = 2.5

    def __init__(self, price_monitor: PriceMonitor, dry_run: bool = False):
        super(Strategy1, self).__init__(dry_run=dry_run)
        self._straddle: PairInstrument = PairInstrument()
        self._hedging: PairInstrument = PairInstrument()
        self._price_monitor: PriceMonitor = price_monitor
        self._pnl: float = 0
        self._first_shifting: bool = False      # Indicate if first shifting is done
        self._straddle_strike: int = 0
        self._market_price: float = 0
        # At any point we should register once
        self._price_monitor_register: bool = False
        self._entry_taken: bool = False
        self._entry_time: Optional[datetime.datetime] = None
        self._sl: Optional[float] = None
        self._target: Optional[float] = None
        self._initial_capital: Optional[float] = None
        self._lot_size: int = 0
        self._remaining_lot_traded: bool = False    # Indicate if remaining lot traded or not

    def entry(self) -> None:
        """ Entry logic """
        self._entry_time = istnow()
        logger.info(f"Entry taken at {self._entry_time}")
        self._market_price = self._price_monitor.get_nifty_value()
        self._straddle_strike = self._price_monitor.get_atm_strike()
        logger.info(f"Market price: {self._market_price}")
        logger.info(f"ATM strike: {self._straddle_strike}")
        self._lot_size = self.initial_lot_size
        logger.info(f"Initial lot size: {self._lot_size}")
        self._straddle.ce_instrument = self.get_instrument(
            strike=self._straddle_strike,
            option_type="CE",
            action=Action.SELL,
            lot_size=self._lot_size,
            entry=self._entry_time
        )
        self._straddle.pe_instrument = self.get_instrument(
            strike=self._straddle_strike,
            option_type="PE",
            action=Action.SELL,
            lot_size=self._lot_size,
            entry=self._entry_time
        )
        logger.info(f"Shorting straddle {self._straddle}")
        straddle_price = self.get_pair_instrument_entry_price(self._straddle)
        logger.info(f"Straddle price: {straddle_price}")
        self.place_pair_instrument_order(self._straddle)
        # TODO: Read price value from config
        ce_buy_strike = self._price_monitor.get_strike_by_price(price=5, option_type="CE")
        pe_buy_strike = self._price_monitor.get_strike_by_price(price=5, option_type="PE")
        self._hedging.ce_instrument = self.get_instrument(
            strike=ce_buy_strike,
            option_type="CE",
            action=Action.BUY,
            lot_size=self._lot_size,
            entry=self._entry_time
        )
        self._hedging.pe_instrument = self.get_instrument(
            strike=pe_buy_strike,
            option_type="PE",
            action=Action.BUY,
            lot_size=self._lot_size,
            entry=self._entry_time
        )
        logger.info(f"Hedging {self._hedging}")
        hedging_price = self.get_pair_instrument_entry_price(self._hedging)
        logger.info(f"Hedging price: {hedging_price}")
        self.place_pair_instrument_order(self._hedging)
        self._entry_taken = True
        logger.info(f"Remaining lot to trade: {self.remaining_lot_size}")

    def exit(self) -> None:
        """ Exit logic """
        logger.info(f"Exiting strategy")
        logger.info(f"Squaring off straddle {self._straddle}")
        logger.info(f"Squaring off hedges {self._hedging}")

    def monitor_pnl(self, pnl: float) -> bool:
        """
        Monitor pnl to see if it hits the target or SL. Return True if target or SL hit else False
        """
        if pnl > self.target:
            logger.info(f"Target {self.target} hit")
            self.exit()
            return True
        if pnl < self.sl:
            logger.info(f"SL {self.sl} hit")
            self.exit()
            return True
        return False

    def execute(self) -> None:
        """ Execute the strategy """
        logger.info(f"Starting execution of strategy {Strategy1.STRATEGY_CODE}")
        super(Strategy1, self).execute()
        logger.info(f"Initial Capital: {self.initial_capital}")
        logger.info(f"Capital to trade: {self.capital_to_trade}")
        while True:
            now = istnow()
            if self.entry_time(now) and not self._entry_taken:
                self.entry()
            if self.exit_time(now):
                self.exit()
                break
            if self._entry_taken:
                if self.time_to_trade_remaining_lot(now) and not self._remaining_lot_traded:
                    self.trade_remaining_lot()
                if not self._first_shifting:
                    # Logic for first shifting
                    self.first_shifting_registration()
                else:
                    # Second shifting onwards
                    self.second_shifting_registration()
                pnl = self.get_strategy_pnl()
                logger.info(f"Lot traded: {self._lot_size}")
                logger.info(f"Strategy PnL: {pnl}")
                target_sl_hit = self.monitor_pnl(pnl)
                if target_sl_hit:
                    break
            time.sleep(2)
        logger.info(f"Stopping price monitoring")
        self._price_monitor.stop_monitor = True
        logger.info(f"Execution completed")

    def first_shifting_registration(self):
        """ Straddle first shifting """
        if self._market_price > self._straddle_strike:
            # This part of the code is running inside an infinite loop. So we need a
            # safety guard for not registering for price monitor more than once
            if not self._price_monitor_register:
                up_point = int(abs(self._market_price - self._straddle_strike - 50))        # 50
                down_point = int(abs(self._market_price - self._straddle_strike + 40))      # 40
                logger.info(
                    f"First shifting will be done when market moves above "
                    f"{self._market_price + up_point} or below {self._market_price - down_point}"
                )
                PriceMonitor.register(
                    symbol="NIFTY",
                    reference_price=self._market_price,
                    up_point=up_point,
                    up_func=self.shift_straddle,
                    down_point=down_point,
                    down_func=self.shift_straddle
                )
                self._price_monitor_register = True
        else:
            if not self._price_monitor_register:
                up_point = int(abs(self._market_price - self._straddle_strike - 40))        # 40
                down_point = int(abs(self._market_price - self._straddle_strike + 50))      # 50
                logger.info(
                    f"First shifting will be done when market moves above "
                    f"{self._market_price + up_point} or below {self._market_price - down_point}"
                )
                PriceMonitor.register(
                    symbol="NIFTY",
                    reference_price=self._market_price,
                    up_point=up_point,
                    up_func=self.shift_straddle,
                    down_point=down_point,
                    down_func=self.shift_straddle
                )
                self._price_monitor_register = True

    def second_shifting_registration(self):
        """ Straddle second shifting onwards """
        now = istnow()
        second_shifting_register: Optional[PriceRegister] = None
        if now.time() > datetime.time(hour=13, minute=30):
            # Shifting after 1:30 PM
            # When time passes 1:30 PM, remove previous registers and register new shifting
            if second_shifting_register is not None:
                PriceMonitor.deregister(second_shifting_register)
                self._price_monitor_register = False
            if not self._price_monitor_register:
                logger.info(
                    f"Next shifting will be done when market moves above "
                    f"{self._market_price + 35} or below {self._market_price - 35}"
                )
                PriceMonitor.register(
                    symbol="NIFTY",
                    reference_price=self._market_price,
                    up_point=35,
                    up_func=self.shift_straddle,
                    down_point=35,
                    down_func=self.shift_straddle
                )
                self._price_monitor_register = True
        else:
            # Second shifting after the first shifting but before 1:30 PM
            if not self._price_monitor_register:
                logger.info(
                    f"Next shifting will be done when market moves above "
                    f"{self._market_price + 45} or below {self._market_price - 45}"
                )
                second_shifting_register = PriceMonitor.register(
                    symbol="NIFTY",
                    reference_price=self._market_price,
                    up_point=45,
                    up_func=self.shift_straddle,
                    down_point=45,
                    down_func=self.shift_straddle
                )
                self._price_monitor_register = True

    def shift_straddle(self):
        """ Shift straddle """
        self._market_price = self._price_monitor.get_nifty_value()
        self._straddle_strike = self._price_monitor.get_atm_strike()
        logger.info(f"Shifting straddle")
        logger.info(
            f"Previous straddle {self._straddle} entry price: "
            f"{self.get_pair_instrument_entry_price(self._straddle)}"
        )
        logger.info(
            f"Previous straddle {self._straddle} exit price: "
            f"{self.get_pair_instrument_current_price(self._straddle)}"
        )
        # Calculate the pnl of previous straddle
        straddle_pnl = self.get_pair_instrument_pnl(self._straddle)
        logger.info(f"Straddle {self._straddle} PnL: {straddle_pnl}")
        self._pnl += straddle_pnl
        logger.info(f"Market price: {self._market_price}")
        logger.info(f"ATM strike: {self._straddle_strike}")
        now = istnow()
        # If remaining lots are not traded, during shifting trade the remaining lot
        if self.time_to_trade_remaining_lot(now) and not self._remaining_lot_traded:
            logger.info(f"Trading remaining lot during shifting")
            self._lot_size += self.remaining_lot_size
            logger.info(f"Final lot size: {self._lot_size}")
            self._remaining_lot_traded = True

        self._straddle.ce_instrument = self.get_instrument(
            strike=self._straddle_strike,
            option_type="CE",
            action=Action.SELL,
            lot_size=self._lot_size,
            entry=now
        )
        self._straddle.pe_instrument = self.get_instrument(
            strike=self._straddle_strike,
            option_type="PE",
            action=Action.SELL,
            lot_size=self._lot_size,
            entry=now
        )
        logger.info(f"Shifting straddle to {self._straddle}")
        straddle_price = self.get_pair_instrument_entry_price(self._straddle)
        logger.info(f"Straddle price: {straddle_price}")
        if not self._first_shifting:
            # If it is first shifting, mark first shifting as True which will ensure code flow
            # for second shifting
            self._first_shifting = True
        # Once this function is triggered, we can reset self._price_monitor_register so that
        # we can register for new shifting
        self._price_monitor_register = False

    def trade_remaining_lot(self):
        """
        Trade remaining lots if the initial straddle is same as current straddle else wait
        for next shifting
        """
        now = istnow()
        logger.info(f"Trading remaining {self.remaining_lot_size} lot  at {now}")
        current_market_price = self._price_monitor.get_nifty_value()
        current_straddle_strike = self._price_monitor.get_atm_strike()
        logger.info(f"Market price: {current_market_price}")
        logger.info(f"ATM strike: {current_straddle_strike}")
        if current_straddle_strike == self._straddle_strike:
            remaining_lot_straddle: PairInstrument = PairInstrument()
            remaining_lot_straddle.ce_instrument = self.get_instrument(
                strike=current_straddle_strike,
                option_type="CE",
                action=Action.SELL,
                lot_size=self.remaining_lot_size,
                entry=now
            )
            remaining_lot_straddle.pe_instrument = self.get_instrument(
                strike=current_straddle_strike,
                option_type="PE",
                action=Action.SELL,
                lot_size=self.remaining_lot_size,
                entry=now
            )
            logger.info(f"Shorting straddle {remaining_lot_straddle}")
            straddle_price = self.get_pair_instrument_entry_price(remaining_lot_straddle)
            logger.info(f"Straddle price: {straddle_price}")
            self.place_pair_instrument_order(remaining_lot_straddle)
            remaining_lot_hedging: PairInstrument = PairInstrument()
            remaining_lot_hedging.ce_instrument = self.get_instrument(
                strike=self._hedging.ce_instrument.strike,
                option_type="CE",
                action=Action.BUY,
                lot_size=self.remaining_lot_size,
                entry=now
            )
            remaining_lot_hedging.pe_instrument = self.get_instrument(
                strike=self._hedging.pe_instrument.strike,
                option_type="PE",
                action=Action.BUY,
                lot_size=self.remaining_lot_size,
                entry=now
            )
            logger.info(f"Hedging {remaining_lot_hedging}")
            hedging_price = self.get_pair_instrument_entry_price(remaining_lot_hedging)
            logger.info(f"Hedging price: {hedging_price}")
            self.place_pair_instrument_order(remaining_lot_hedging)
            self._lot_size += self.remaining_lot_size
            self._remaining_lot_traded = True
        else:
            logger.info(
                f"Initial straddle strike {self._straddle_strike} and current straddle strike "
                f"{current_straddle_strike} are not same. Skipping trading remaining lots."
            )

    def get_instrument(
            self,
            strike: int,
            option_type: str,
            action: Action,
            lot_size: int,
            entry: datetime.datetime,
    ):
        """ Return a CE instrument """
        instrument = Instrument(
            action=action,
            lot_size=lot_size * self.QUANTITY,
            expiry=self._price_monitor.expiry,
            option_type=option_type,
            strike=strike,
            index="NIFTY",
            entry=entry,
            price=0,
            order_id=""
        )
        instrument.price = self._price_monitor.get_price_by_symbol(instrument.symbol)
        return instrument

    def get_strategy_pnl(self):
        """ Get the strategy pnl """
        straddle_pnl = self.get_pair_instrument_pnl(self._straddle)
        hedging_pnl = self.get_pair_instrument_pnl(self._hedging)
        return round((self._pnl + straddle_pnl + hedging_pnl) * self.QUANTITY * self._lot_size, 2)

    def get_pair_instrument_pnl(self, instrument: PairInstrument):
        """ Calculate current straddle pnl """
        ce_pnl = self.get_instrument_pnl(instrument.ce_instrument)
        pe_pnl = self.get_instrument_pnl(instrument.pe_instrument)
        return round(ce_pnl + pe_pnl, 2)

    def get_instrument_pnl(self, instrument: Instrument):
        """ Calculate pnl for an individual instrument """
        entry_price = instrument.price
        current_price = self._price_monitor.get_price_by_symbol(instrument.symbol)
        pnl = self.calc_pnl(entry_price, current_price, instrument.action)
        # logger.info(f"Entry price for {instrument.symbol}: {entry_price}")
        # logger.info(f"Current price for {instrument.symbol}: {current_price}")
        # logger.info(f"PnL for {instrument.symbol}: {pnl}")
        return round(pnl, 2)

    @staticmethod
    def calc_pnl(entry_price: float, current_price: float, action: Action):
        """ Calculate pnl """
        pnl = current_price - entry_price
        if action == Action.SELL:
            pnl *= -1
        return round(pnl, 2)

    @staticmethod
    def entry_time(dt: datetime.datetime) -> bool:
        """ Return True if the time is more than entry time. Entry time is 9:50 AM """
        start_time = datetime.time(hour=9, minute=30)
        return dt.time() > start_time

    @staticmethod
    def exit_time(dt: datetime.datetime) -> bool:
        """ Return True if the time is more than exit time. Exit time is 3:00 PM """
        end_time = datetime.time(hour=15, minute=0)
        return dt.time() > end_time

    def time_to_trade_remaining_lot(self, dt: datetime.datetime) -> bool:
        """ Return True if the time is more than entry time + 25 mins else False """
        trade_time = self._entry_time + datetime.timedelta(minutes=1)
        return dt.time() > trade_time.time()

    def get_pair_instrument_entry_price(self, pair_instrument: PairInstrument) -> float:
        """ Return pair instrument entry price which is summation of individual instrument """
        price = pair_instrument.pe_instrument.price + pair_instrument.ce_instrument.price
        return round(price, 2)

    def get_pair_instrument_current_price(self, pair_instrument: PairInstrument) -> float:
        """ Return pair instrument current price by fetching the live feed from redis """
        price = self._price_monitor.get_price_by_symbol(
            pair_instrument.pe_instrument.symbol
        )
        price += self._price_monitor.get_price_by_symbol(
            pair_instrument.ce_instrument.symbol
        )
        return round(price, 2)

    @property
    def sl(self) -> float:
        if self._sl is None:
            self._sl = self.SL_PERCENT * self.initial_capital / 100
        return self._sl * -1

    @property
    def target(self) -> float:
        if self._target is None:
            self._target = self.TARGET_PERCENT * self.initial_capital / 100
        return self._target

    @property
    def initial_capital(self) -> float:
        """ Make API call to get initial capital in the account """
        if self._initial_capital is None:
            # API Call
            self._initial_capital = 1000000
        return self._initial_capital

    @property
    def capital_to_trade(self) -> float:
        """ Calculate capital to trade which is 95% of initial capital """
        return 0.95 * self.initial_capital

    @property
    def expected_margin_per_lot(self) -> float:
        """ A rough estimate for margin per lot """
        return 50000

    @property
    def actual_margin_per_lot(self) -> float:
        """ MAke API call to get actual margin used and divide it by initial lot """
        margin_used = 600000    # Get this using API call
        return round(margin_used / self.initial_lot_size, 2)

    @property
    def initial_lot_size(self) -> int:
        """ Initial lot size based on your initial capital """
        return math.floor(math.floor(self.initial_capital / self.expected_margin_per_lot) / 2)

    @property
    def remaining_lot_size(self) -> int:
        """ Calculate how many lot we can trade with the remaining capital """
        margin_used = self.actual_margin_per_lot * self.initial_lot_size
        return math.floor((self.capital_to_trade - margin_used) / self.actual_margin_per_lot)


if __name__ == "__main__":
    price_monitor = PriceMonitor()
    price_monitor.setup()
    price_monitor.run_in_background()
    strategy = Strategy1(price_monitor=price_monitor)
    strategy.execute()
