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
from src.utils.enum import Weekdays
from src.utils.config_reader import ConfigReader
from src.utils.logger import LogFacade


logger: LogFacade = LogFacade.get_logger("strategy1")


class Strategy1(BaseStrategy):
    """ Expiry day strategy for shorting straddle """
    STRATEGY_CODE: str = "strategy1"
    QUANTITY: int = 50

    def __init__(
            self,
            api_key: str,
            client_id: str,
            password: str,
            totp_key: str,
            price_monitor: PriceMonitor,
            config: ConfigReader,
            dry_run: bool = False
    ):
        super(Strategy1, self).__init__(api_key, client_id, password, totp_key, dry_run=dry_run)
        self._dry_run: bool = dry_run
        if self._dry_run:
            logger.info(f"Executing in dry-run mode")
        self._straddle: PairInstrument = PairInstrument()
        self._hedging: PairInstrument = PairInstrument()
        self._price_monitor: PriceMonitor = price_monitor
        self._config: ConfigReader = config
        self._pnl: float = 0
        self._first_shifting: bool = False      # Indicate if first shifting is done
        self._straddle_strike: int = 0
        self._market_price: float = 0
        self._weekday: Optional[Weekdays] = None
        # At any point we should register once
        self._price_monitor_register: bool = False
        self._entry_taken: bool = False
        self._entry_time: Optional[datetime.datetime] = None
        self._changed_entry_time: Optional[datetime.time] = None
        self._sl: Optional[float] = None
        self._target: Optional[float] = None
        self._initial_capital: Optional[float] = None
        self._lot_size: int = 0
        self._remaining_lot_traded: bool = False    # Indicate if remaining lot traded or not
        self._remaining_lot_size: Optional[int] = None
        self._actual_margin_per_lot: Optional[float] = None

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
        # Buy hedging
        ce_buy_strike = self._price_monitor.get_strike_by_price(
            price=self.ce_buy_price, option_type="CE"
        )
        pe_buy_strike = self._price_monitor.get_strike_by_price(
            price=self.pe_buy_price, option_type="PE"
        )
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
        # Sell Straddle
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
        self._entry_taken = True
        logger.info(f"Remaining lot to trade: {self.remaining_lot_size}")

    def exit(self) -> None:
        """ Exit logic """
        logger.info(f"Exiting strategy")
        logger.info(f"Squaring off straddle {self._straddle}")
        self._straddle.ce_instrument.action = Action.BUY
        self._straddle.pe_instrument.action = Action.BUY
        self.place_pair_instrument_order(self._straddle)
        logger.info(f"Squaring off hedges {self._hedging}")
        self._hedging.ce_instrument.action = Action.SELL
        self._hedging.pe_instrument.action = Action.SELL
        self.place_pair_instrument_order(self._hedging)

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
        now = istnow()
        self._weekday = Weekdays(now.weekday())
        logger.info(f"Trading day: {self._weekday.name}")
        logger.info(f"Initial Capital: {self.initial_capital}")
        logger.info(f"Capital to trade: {self.capital_to_trade}")
        logger.info(f"SL percent: {self.sl_percent}")
        logger.info(f"Target percent: {self.target_percent}")
        logger.info(f"Expected margin per lot: {self.expected_margin_per_lot}")
        while True:
            now = istnow()
            if self.check_entry_time(now) and not self._entry_taken:
                # For Thursday check if straddle price is in between 70 and 110
                if self._weekday == Weekdays.THURSDAY and self._changed_entry_time is None:
                    straddle_price = self.get_current_straddle_price()
                    if 70 <= straddle_price <= 110:
                        self.entry()
                    else:
                        logger.info(f"Straddle price {straddle_price} is outside range 70 - 110.")
                        self._changed_entry_time = datetime.time(hour=10, minute=20)
                        logger.info(f"Changing the entry time to {self._changed_entry_time}")
                else:
                    self.entry()
            if self.check_exit_time(now):
                self.exit()
                break
            if self._entry_taken:
                if self.time_to_trade_remaining_lot(now) and not self._remaining_lot_traded and \
                        self.remaining_lot_size > 0:
                    self.trade_remaining_lot()
                if not self._first_shifting:
                    # Logic for first shifting
                    self.first_shifting_registration()
                else:
                    # Second shifting onwards
                    self.second_shifting_registration()
                if self._config["option_buying_shifting"][self._weekday.name.lower()]:
                    self.shift_hedging()
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
        if now.time() > datetime.time(hour=13, minute=30) and self._weekday == Weekdays.THURSDAY:
            # This is only applicable for Thursday
            # Shifting after 1:30 PM
            # When time passes 1:30 PM, remove previous registers and register new shifting
            # if second_shifting_register is not None:
            #     PriceMonitor.deregister(second_shifting_register)
            #     self._price_monitor_register = False
            # Unless the previous register is triggered, don't register any new trigger
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
                PriceMonitor.register(
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
        current_straddle_strike = self._price_monitor.get_atm_strike()
        if current_straddle_strike == self._straddle_strike:
            logger.info(
                f"Skipping straddle shift as previous straddle strike and current straddle "
                f"strike is same"
            )
            return None
        self._straddle_strike = current_straddle_strike
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
        # Squaring off previous straddle
        logger.info(f"Squaring off straddle {self._straddle}")
        self._straddle.ce_instrument.action = Action.BUY
        self._straddle.pe_instrument.action = Action.BUY
        self.place_pair_instrument_order(self._straddle)

        logger.info(f"Market price: {self._market_price}")
        logger.info(f"ATM strike: {self._straddle_strike}")
        now = istnow()
        # If remaining lots are not traded, during shifting trade the remaining lot
        if self.time_to_trade_remaining_lot(now) and not self._remaining_lot_traded and \
                self.remaining_lot_size > 0:
            logger.info(f"Trading remaining {self.remaining_lot_size} lot during shifting")
            self._lot_size += self.remaining_lot_size
            self.buy_remaining_lot_hedging()
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
        # Placing actual order
        self.place_pair_instrument_order(self._straddle)
        if not self._first_shifting:
            # If it is first shifting, mark first shifting as True which will ensure code flow
            # for second shifting
            self._first_shifting = True
        # Once this function is triggered, we can reset self._price_monitor_register so that
        # we can register for new shifting
        self._price_monitor_register = False

    def shift_hedging(self):
        """ Shift hedging close to Rs 5 """
        # Buy hedging
        ce_buy_strike = self._price_monitor.get_strike_by_price(
            price=self.ce_buy_price, option_type="CE"
        )
        pe_buy_strike = self._price_monitor.get_strike_by_price(
            price=self.pe_buy_price, option_type="PE"
        )
        if ce_buy_strike == self._hedging.ce_instrument.strike:
            logger.info(
                f"New CE strike is same as current hedging CE strike. "
                f"Skipping shifting of CE hedge."
            )
        elif ce_buy_strike > self._hedging.ce_instrument.strike:
            logger.info(
                f"New CE strike {ce_buy_strike} is upward to current hedging CE strike "
                f"{self._hedging.ce_instrument.strike}. Skipping shifting of CE hedge."
            )
        else:
            logger.info(f"Shifting CE hedge")
            logger.info(f"Current CE buy hedge: {self._hedging.ce_instrument.strike}")
            logger.info(f"New CE buy hedge: {ce_buy_strike}")
            self.shift_ce_hedge(ce_buy_strike)

        if pe_buy_strike == self._hedging.pe_instrument.strike:
            logger.info(
                f"New PE strike is same as current hedging PE strike. "
                f"Skipping shifting of PE hedge."
            )
        elif pe_buy_strike < self._hedging.pe_instrument.strike:
            logger.info(
                f"New PE strike {pe_buy_strike} is downward to current hedging PE strike "
                f"{self._hedging.pe_instrument.strike}. Skipping shifting of PE hedge."
            )
        else:
            logger.info(f"Shifting PE hedge")
            logger.info(f"Current PE buy hedge: {self._hedging.pe_instrument.strike}")
            logger.info(f"New PE buy hedge: {pe_buy_strike}")
            self.shift_pe_hedge(pe_buy_strike)

    def shift_ce_hedge(self, strike: int):
        """ Shift CE hedging leg """
        now = istnow()
        instrument = self.get_instrument(
            strike=strike,
            option_type="CE",
            action=Action.BUY,
            lot_size=self._lot_size,
            entry=now
        )
        logger.info(f"CE hedging price: {instrument.price}")
        # Buying new hedge
        self.place_instrument_order(instrument)
        logger.info(f"Squaring off CE hedge: {self._hedging.ce_instrument}")
        pnl = self.get_instrument_pnl(self._hedging.ce_instrument)
        logger.info(f"CE hedge PnL: {pnl}")
        self._pnl += pnl
        self._hedging.ce_instrument.action = Action.SELL
        self.place_instrument_order(self._hedging.ce_instrument)
        self._hedging.ce_instrument = instrument

    def shift_pe_hedge(self, strike: int):
        """ Shift PE hedging leg """
        now = istnow()
        instrument = self.get_instrument(
            strike=strike,
            option_type="PE",
            action=Action.BUY,
            lot_size=self._lot_size,
            entry=now
        )
        logger.info(f"PE hedging price: {instrument.price}")
        # Buying new hedge
        self.place_instrument_order(instrument)
        logger.info(f"Squaring off PE hedge: {self._hedging.pe_instrument}")
        pnl = self.get_instrument_pnl(self._hedging.pe_instrument)
        logger.info(f"PE hedge PnL: {pnl}")
        self._pnl += pnl
        self._hedging.pe_instrument.action = Action.SELL
        self.place_instrument_order(self._hedging.pe_instrument)
        self._hedging.pe_instrument = instrument

    def trade_remaining_lot(self) -> None:
        """
        Trade remaining lots if the initial straddle is same as current straddle else wait
        for next shifting
        """
        now = istnow()
        logger.info(f"Trading remaining {self.remaining_lot_size} lot at {now}")
        current_market_price = self._price_monitor.get_nifty_value()
        current_straddle_strike = self._price_monitor.get_atm_strike()
        logger.info(f"Market price: {current_market_price}")
        logger.info(f"ATM strike: {current_straddle_strike}")
        if current_straddle_strike != self._straddle_strike:
            logger.info(
                f"Initial straddle strike {self._straddle_strike} and current straddle strike "
                f"{current_straddle_strike} are not same. Skipping trading remaining lots."
            )
            return None

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

        remaining_lot_straddle: PairInstrument = PairInstrument()
        remaining_lot_straddle.ce_instrument = self.get_instrument(
            strike=self._straddle_strike,
            option_type="CE",
            action=Action.SELL,
            lot_size=self.remaining_lot_size,
            entry=now
        )
        remaining_lot_straddle.pe_instrument = self.get_instrument(
            strike=self._straddle_strike,
            option_type="PE",
            action=Action.SELL,
            lot_size=self.remaining_lot_size,
            entry=now
        )
        logger.info(f"Shorting straddle {remaining_lot_straddle}")
        straddle_price = self.get_pair_instrument_entry_price(remaining_lot_straddle)
        logger.info(f"Straddle price: {straddle_price}")
        self.place_pair_instrument_order(remaining_lot_straddle)
        # Update the total lot size
        logger.info(f"Lot size before trading remaining lot: {self._lot_size}")
        logger.info(f"Remaining lot size: {self.remaining_lot_size}")
        self._lot_size += self.remaining_lot_size
        logger.info(f"Final lot size after trading remaining lot: {self._lot_size}")
        # Update lot size for straddle
        self._straddle.ce_instrument.lot_size = self._lot_size * self.QUANTITY
        self._straddle.pe_instrument.lot_size = self._lot_size * self.QUANTITY
        # Update lot size for hedging
        self._hedging.ce_instrument.lot_size = self._lot_size * self.QUANTITY
        self._hedging.pe_instrument.lot_size = self._lot_size * self.QUANTITY
        self._remaining_lot_traded = True

    def buy_remaining_lot_hedging(self):
        """ Buy remaining lot hedging while we add remaining lot during straddle shifting """
        now = istnow()
        logger.info(f"Buying remaining {self.remaining_lot_size} lot hedging at {now}")
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
        # Update lot size for hedging
        self._hedging.ce_instrument.lot_size += self.remaining_lot_size * self.QUANTITY
        self._hedging.pe_instrument.lot_size += self.remaining_lot_size * self.QUANTITY

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
        return round(self._pnl + straddle_pnl + hedging_pnl, 2)

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
        # instrument lot size is lot size * quantity
        return round(pnl * instrument.lot_size, 2)

    @staticmethod
    def calc_pnl(entry_price: float, current_price: float, action: Action):
        """ Calculate pnl """
        pnl = current_price - entry_price
        if action == Action.SELL:
            pnl *= -1
        return round(pnl, 2)

    def check_entry_time(self, dt: datetime.datetime) -> bool:
        """ Return True if the time is more than entry time. Entry time is 9:50 AM """
        return dt.time() > self.entry_time

    def check_exit_time(self, dt: datetime.datetime) -> bool:
        """ Return True if the time is more than exit time. Exit time is 3:00 PM """
        return dt.time() > self.exit_time

    def time_to_trade_remaining_lot(self, dt: datetime.datetime) -> bool:
        """ Return True if the time is more than entry time + 25 mins else False """
        trade_time = self._entry_time + datetime.timedelta(minutes=25)
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

    def get_current_straddle_price(self) -> float:
        """ Get the current straddle price """
        straddle_strike = self._price_monitor.get_atm_strike()
        straddle: PairInstrument = PairInstrument()
        straddle.ce_instrument = self.get_instrument(
            strike=straddle_strike,
            option_type="CE",
            action=Action.SELL,
            lot_size=self._lot_size,
            entry=self._entry_time
        )
        straddle.pe_instrument = self.get_instrument(
            strike=straddle_strike,
            option_type="PE",
            action=Action.SELL,
            lot_size=self._lot_size,
            entry=self._entry_time
        )
        straddle_price = self.get_pair_instrument_entry_price(straddle)
        return straddle_price

    @property
    def sl_percent(self) -> float:
        return float(self._config["stop_loss"][self._weekday.name.lower()])

    @property
    def target_percent(self) -> float:
        return float(self._config["target"][self._weekday.name.lower()])

    @property
    def ce_buy_price(self) -> float:
        return float(self._config["option_buying"][self._weekday.name.lower()]["CE"])

    @property
    def pe_buy_price(self) -> float:
        return float(self._config["option_buying"][self._weekday.name.lower()]["PE"])

    @property
    def entry_time(self) -> datetime.time:
        if self._changed_entry_time is None:
            return self._config["entry_time"][self._weekday.name.lower()]
        return self._changed_entry_time

    @property
    def exit_time(self) -> datetime.time:
        return self._config["exit_time"][self._weekday.name.lower()]

    @property
    def sl(self) -> float:
        if self._sl is None:
            self._sl = self.sl_percent * self.initial_capital / 100
        return self._sl * -1

    @property
    def target(self) -> float:
        if self._target is None:
            self._target = self.target_percent * self.initial_capital / 100
        return self._target

    @property
    def initial_capital(self) -> float:
        """ Make API call to get initial capital in the account """
        if self._initial_capital is None:
            # API Call
            if self._dry_run:
                self._initial_capital = self._config["dry_run"]["initial_capital"]
            else:
                self._initial_capital = self.get_initial_capital()
        return self._initial_capital

    @property
    def capital_to_trade(self) -> float:
        """ Calculate capital to trade which is 95% of initial capital """
        return self._config["capital_to_trade_percent"][self._weekday.name.lower()] * \
               self.initial_capital

    @property
    def expected_margin_per_lot(self) -> float:
        """ A rough estimate for margin per lot """
        return self._config["margin"][self._weekday.name.lower()]

    @property
    def actual_margin_per_lot(self) -> float:
        """ MAke API call to get actual margin used and divide it by initial lot """
        if self._actual_margin_per_lot is None:
            if self._dry_run:
                self._actual_margin_per_lot = self._config["dry_run"]["actual_margin_per_lot"]
            else:
                margin_used = self.get_used_margin()    # Get this using API call
                self._actual_margin_per_lot = round(margin_used / self.initial_lot_size, 2)
            logger.info(f"Actual margin per lot: {self._actual_margin_per_lot}")
        return self._actual_margin_per_lot

    @property
    def initial_lot_size(self) -> int:
        """ Initial lot size based on your initial capital """
        return math.floor(math.floor(self.initial_capital / self.expected_margin_per_lot) / 2)

    @property
    def remaining_lot_size(self) -> int:
        """ Calculate how many lot we can trade with the remaining capital """
        if self._remaining_lot_size is None:
            margin_used = self.actual_margin_per_lot * self.initial_lot_size
            self._remaining_lot_size = math.floor(
                (self.capital_to_trade - margin_used) / self.actual_margin_per_lot
            )
        return self._remaining_lot_size


if __name__ == "__main__":
    from src import BASE_DIR
    price_monitor = PriceMonitor()
    price_monitor.setup()
    price_monitor.run_in_background()
    config_path = BASE_DIR / 'data' / 'config.json'
    config = ConfigReader(config_file_path=config_path)
    strategy = Strategy1(price_monitor=price_monitor, config=config, dry_run=True)
    strategy.execute()
