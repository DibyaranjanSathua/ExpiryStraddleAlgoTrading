"""
File:           models.py
Author:         Dibyaranjan Sathua
Created on:     16/11/22, 1:42 pm
"""
from sqlalchemy import String, Integer, SmallInteger, Column, Boolean, Time

from . import Base


class PowerAlgoSystem(Base):
    """ Algo system is ON or OFF """
    __tablename__ = "power_algo_system"
    id = Column(SmallInteger, primary_key=True, index=True)
    on = Column(Boolean, default=False)


class AlgoRunConfig(Base):
    """ Stores algo configuration """
    __tablename__ = "algo_run_config"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(String(20))
    run = Column(Boolean, default=True)
    time = Column(Time, nullable=True)


class User(Base):
    """ Stores user name and password for connecting to dashboard """
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50))
    password = Column(String(20))
    role = Column(String(20))
