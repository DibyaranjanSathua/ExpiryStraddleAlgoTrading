"""
File:           logger.py
Author:         Dibyaranjan Sathua
Created on:     05/08/22, 9:52 pm
"""
from typing import Dict
import logging

from src import LOG_DIR


class LogFacade:
    """ Log module """

    __LOGGER_INSTANCES: Dict[str, "LogFacade"] = dict()
    FORMAT = "[%(levelname)s] %(asctime)s: %(message)s"

    def __init__(self, name: str, level=None):
        self._name: str = name
        self._level = level or logging.INFO
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self.add_stream_handler()
        self.add_file_handler()

    def add_stream_handler(self):
        """ Add stream handler to logger """
        handler = logging.StreamHandler()
        handler.setLevel(self._level)
        handler.setFormatter(logging.Formatter(LogFacade.FORMAT))
        self._logger.addHandler(handler)

    def add_file_handler(self):
        """ Add a file handler to logger """
        handler = logging.FileHandler(filename=LOG_DIR / f"{self._name}.log", mode="w")
        handler.setLevel(level=self._level)
        handler.setFormatter(logging.Formatter(LogFacade.FORMAT))
        self._logger.addHandler(handler)

    @classmethod
    def get_logger(cls, name: str, level=None):
        """ Get logger instance """
        if name not in cls.__LOGGER_INSTANCES:
            cls.__LOGGER_INSTANCES[name] = LogFacade(name=name, level=level)
        return cls.__LOGGER_INSTANCES[name]

    def error(self, msg):
        self._logger.error(msg)

    def info(self, msg):
        self._logger.info(msg)

    def warning(self, msg):
        self._logger.warning(msg)

    def debug(self, msg):
        self._logger.debug(msg)

    def critical(self, msg):
        self._logger.critical(msg)

    def exception(self, msg):
        self._logger.exception(msg)
