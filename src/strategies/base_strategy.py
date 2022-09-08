"""
File:           base_strategy.py
Author:         Dibyaranjan Sathua
Created on:     22/08/22, 9:29 pm
"""
from typing import Dict, Any
from abc import ABC, abstractmethod
import datetime

from src.brokerapi.angelbroking import AngelBrokingApi
from src.strategies.instrument import Instrument, PairInstrument, Action


class BaseStrategy(ABC):
    """ Abstract class contains common functions that needs to be implemented in the child class """
    STRATEGY_CODE: str = ""

    def __init__(self, dry_run: bool = False, clean_up: bool = False):
        self.dry_run: bool = dry_run
        self.clean_up_flag: bool = clean_up

    @abstractmethod
    def entry(self) -> None:
        pass

    @abstractmethod
    def exit(self) -> None:
        pass

    @abstractmethod
    def execute(self) -> None:
        pass

    def process_live_tick(self) -> None:
        pass

    def place_pair_instrument_order(self, pair_instrument: PairInstrument):
        """ Place the order using broker API """
        pass

    @staticmethod
    def is_market_hour(dt: datetime.datetime) -> bool:
        """ Return True if dt is in market hour 9:15:01 to 3:29:59. dt is IST timezone """
        start_time = datetime.time(hour=9, minute=15)
        end_time = datetime.time(hour=15, minute=30)
        return start_time < dt.time() < end_time

    @staticmethod
    def trading_session_ends(now: datetime.datetime):
        """ Return true if the time is greater than 3:36 PM else false """
        return now.time().hour == 15 and now.time().minute > 35
