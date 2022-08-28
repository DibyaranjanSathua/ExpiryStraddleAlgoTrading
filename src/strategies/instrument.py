"""
File:           instrument.py
Author:         Dibyaranjan Sathua
Created on:     25/08/22, 11:15 am
"""
from typing import Optional
from dataclasses import dataclass
import datetime
from enum import IntEnum


class Action(IntEnum):
    BUY = 1
    SELL = 2


@dataclass()
class Instrument:
    action: Action                 # BUY or SELL
    lot_size: Optional[int]
    expiry: Optional[datetime.date]
    option_type: Optional[str]
    strike: Optional[int]
    index: Optional[str]
    entry: Optional[datetime.datetime]
    price: Optional[float]
    order_id: Optional[str]

    def __str__(self):
        return self.symbol

    @property
    def symbol(self):
        date_str = self.expiry.strftime("%d%b%y").upper()
        return f"{self.index}{date_str}{self.strike}{self.option_type}"


class PairInstrument:
    """ Pair CE and PE instrument """

    def __init__(self):
        self.ce_instrument: Optional[Instrument] = None
        self.pe_instrument: Optional[Instrument] = None

    def __str__(self):
        return f"{self.ce_instrument} & {self.pe_instrument}"
