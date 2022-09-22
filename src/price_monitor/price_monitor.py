"""
File:           price_monitor.py
Author:         Dibyaranjan Sathua
Created on:     18/08/22, 5:58 pm
"""
from typing import Optional, Callable, List
from dataclasses import dataclass
import datetime
import time
import threading

from src.brokerapi.angelbroking.api import AngelBrokingSymbolParser
from src.utils.redis_backend import RedisBackend
from src.utils.logger import LogFacade


logger: LogFacade = LogFacade.get_logger("price_monitor")


class PriceMonitorError(Exception):
    pass


@dataclass()
class PriceRegister:
    """ Dataclass to register prices """
    symbol: str
    reference_price: float
    up_point: float
    up_func: Callable
    down_point: float
    down_func: Callable

    def __str__(self):
        return self.symbol


class PriceMonitor:
    """ Price monitor class """
    REGISTER: List[PriceRegister] = []

    def __init__(self):
        self._redis_backend = RedisBackend()
        self._symbol_parser: Optional[AngelBrokingSymbolParser] = None
        self._expiry: Optional[datetime.date] = None
        self._expiry_str = ""
        self.stop_monitor = False

    def setup(self):
        """ Setup required class for price monitor """
        self._redis_backend.connect()
        self._symbol_parser = AngelBrokingSymbolParser.instance()
        self._expiry = self._symbol_parser.current_week_expiry
        self._expiry_str = self._expiry.strftime("%d%b%y").upper()

    def get_atm_strike(self):
        """ Return ATM strike """
        return self.get_nearest_50_strike(self.get_nifty_value())

    def get_nifty_value(self) -> float:
        """ Return nifty value """
        symbol_data = self._redis_backend.get("NIFTY")
        if symbol_data is None:
            raise PriceMonitorError(f"NIFTY data is missing in redis")
        return symbol_data["ltp"]

    def get_strike_by_price(self, price: float, option_type: str) -> int:
        """ Return the strike nearest to the price argument """
        atm_strike = self.get_atm_strike()
        selected_strike = atm_strike
        step = 50 if option_type == "CE" else -50
        atm_strike_price = self._redis_backend.get(
            self.get_symbol(strike=atm_strike, option_type=option_type)
        )
        if atm_strike_price is None or "ltp" not in atm_strike_price:
            raise PriceMonitorError(
                f"Strike {atm_strike} {option_type} price is None or ltp key is missing "
                f"while reading from redis"
            )
        atm_strike_price = atm_strike_price["ltp"]
        if price > atm_strike_price:   # Scan ITM strikes
            step *= -1
        diff = abs(price - atm_strike_price)
        next_strike = atm_strike
        while True:
            next_strike += step
            next_strike_price = self._redis_backend.get(
                self.get_symbol(strike=next_strike, option_type=option_type)
            )
            # We are done with the strikes
            if next_strike_price is None:
                break
            if "ltp" not in next_strike_price:
                raise PriceMonitorError(
                    f"Strike {atm_strike} {option_type} price ltp key is missing "
                    f"while reading from redis"
                )
            next_strike_price = next_strike_price["ltp"]
            temp_diff = abs(price - next_strike_price)
            if temp_diff < diff:
                diff = temp_diff
                selected_strike = next_strike
        return selected_strike

    def get_price_by_symbol(self, symbol: str):
        """ Return the price of a symbol """
        symbol_data = self._redis_backend.get(symbol)
        if symbol_data is None or "ltp" not in symbol_data:
            raise PriceMonitorError(f"{symbol} data is missing in redis")
        return symbol_data["ltp"]

    def monitor(self):
        """ Monitor price of a symbol and call appropriate function """
        # Remove the PriceRegister obj when a function is called
        while True:
            if self.stop_monitor:
                logger.info(f"Stopping price monitoring")
                break
            # Remove the PriceRegister object that is triggered
            triggered_signals: List[PriceRegister] = []
            for reg in self.REGISTER:
                logger.debug(f"Registered: {reg} with id {id(reg)}")
                live_price = self._redis_backend.get(reg.symbol)
                if live_price is None or "ltp" not in live_price:
                    raise PriceMonitorError(
                        f"{reg.symbol} price is None or ltp key is missing while reading from redis"
                    )
                live_price = live_price["ltp"]
                price_diff = live_price - reg.reference_price
                logger.debug(f"Live price: {live_price}")
                logger.debug(f"Ref price: {reg.reference_price}")
                logger.debug(f"Up point: {reg.up_point}")
                logger.debug(f"Down point: {reg.down_point}")
                if price_diff > reg.up_point:
                    logger.info("Shifting triggered")
                    reg.up_func()
                    triggered_signals.append(reg)
                if price_diff < reg.down_point:
                    logger.info("Shifting triggered")
                    reg.down_func()
                    triggered_signals.append(reg)
            for reg in triggered_signals:
                logger.info(f"Removing reg with id {id(reg)}")
                self.REGISTER.remove(reg)
            time.sleep(2)

    def run_in_background(self):
        """ Run the monitor in background """
        threading.Thread(target=self.monitor).start()

    @classmethod
    def register(
            cls,
            symbol: str,
            reference_price: float,
            *,
            up_point: int,
            up_func: Callable,
            down_point: int,
            down_func: Callable
    ):
        """ Monitor price of a symbol and call appropriate function """
        register = PriceRegister(
            symbol=symbol,
            reference_price=reference_price,
            up_point=up_point,
            up_func=up_func,
            down_point=down_point * -1,
            down_func=down_func
        )
        cls.REGISTER.append(register)
        return register

    @classmethod
    def deregister(cls, price_register: PriceRegister) -> None:
        cls.REGISTER.remove(price_register)

    def get_symbol(self, strike: int, option_type: str) -> str:
        return f"NIFTY{self._expiry_str}{strike}{option_type}"

    @staticmethod
    def get_nearest_50_strike(index: float) -> int:
        """ Return the nearest 50 strike """
        return round(index / 50) * 50

    @property
    def expiry(self) -> Optional[datetime.date]:
        return self._expiry

    @property
    def expiry_str(self) -> str:
        return self._expiry_str


if __name__ == "__main__":
    price_monitor = PriceMonitor()
    price_monitor.setup()
    strike = price_monitor.get_strike_by_price(price=50, option_type="CE")
    print(strike)

    def up_func():
        print("Up function called")

    def down_func():
        print("Down func called")

    # price_monitor.register(
    #     "NIFTY",
    #     17542,
    #     up_point=10,
    #     up_func=up_func,
    #     down_point=12,
    #     down_func=down_func
    # )
    # price_monitor.monitor()
    obj = PriceRegister(
        symbol="X",
        reference_price=1,
        up_point=1,
        up_func=up_func,
        down_point=1,
        down_func=down_func
    )
