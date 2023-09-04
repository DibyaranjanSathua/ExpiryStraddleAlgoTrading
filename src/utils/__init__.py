"""
File:           __init__.py
Author:         Dibyaranjan Sathua
Created on:     08/08/22, 5:21 pm
"""
import datetime
import pytz


# # Global variable used to define the ticker. NIFTY, BANKNIFTY, FINNIFTY
class StrategyTicker:
    __instance = None

    def __init__(self):
        self._ticker = "NIFTY"
        self._quantity = 50

    @classmethod
    def get_instance(cls):
        if cls.__instance is None:
            cls.__instance = StrategyTicker()
        return cls.__instance

    @property
    def ticker(self):
        return self._ticker

    @ticker.setter
    def ticker(self, value):
        self._ticker = value

    @property
    def quantity(self):
        return self._quantity

    @quantity.setter
    def quantity(self, value):
        self._quantity = value


def utc2ist(dt: datetime.datetime):
    """ Convert the given dt in utc to ist timezone """
    utc_dt = pytz.utc.localize(dt)      # Add UTC timezone
    ist_tz = pytz.timezone("Asia/Kolkata")
    return utc_dt.astimezone(ist_tz)


def istnow() -> datetime.datetime:
    """ Return current IST time """
    utcnow = pytz.utc.localize(datetime.datetime.utcnow())
    ist_tz = pytz.timezone("Asia/Kolkata")
    return utcnow.astimezone(ist_tz)


def make_ist_aware(dt: datetime.datetime):
    """ Add IST timezone to the offset native datetime """
    ist_tz = pytz.timezone("Asia/Kolkata")
    return ist_tz.localize(dt)
