"""
File:           config_reader.py
Author:         Dibyaranjan Sathua
Created on:     16/04/22, 6:31 pm
"""
from typing import Dict
import json
import datetime
from pathlib import Path

from src.utils.logger import LogFacade


logger: LogFacade = LogFacade("config_reader")


class ConfigReader:
    """ Singleton class that reads the config file and store it in memory """

    def __init__(self, config_file_path: Path):
        self._config_file_path = config_file_path
        if not self._config_file_path.is_file():
            raise FileNotFoundError(f"Config file {self._config_file_path} doesn't exist")
        with open(self._config_file_path, mode="r") as fp_:
            try:
                self._config: Dict = json.load(fp_, object_hook=self.json_object_hook)
            except json.JSONDecodeError as err:
                logger.error(f"Error decoding config file")
                logger.error(err)

    def __getitem__(self, item: str):
        return self._config[item]

    def __setitem__(self, key, value):
        self._config[key] = value

    def __contains__(self, item: str):
        return item in self._config

    def get(self, item: str, default=None):
        return self._config.get(item, default)

    @staticmethod
    def json_object_hook(input_dict: Dict):
        """ Look for specific keys and convert them to python datetime object.
        This will be called for each dict type structure in json. If JSON file has a list of dicts,
        then it will be called for each dict. The return value will be used instead of the
        decoded dict.
        """
        output_dict = dict()
        for key, value in input_dict.items():
            if key.endswith("datetime"):
                if type(value) == str:
                    output_dict[key] = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                elif type(value) == dict:
                    output_dict[key] = dict()
                    for k, v in value.items():
                        output_dict[key][k] = datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
            elif key.endswith("date"):
                if type(value) == str:
                    output_dict[key] = datetime.datetime.strptime(value, "%Y-%m-%d").date()
                elif type(value) == dict:
                    output_dict[key] = dict()
                    for k, v in value.items():
                        output_dict[key][k] = datetime.datetime.strptime(v, "%Y-%m-%d").date()
            elif key.endswith("time"):
                if type(value) == str:
                    output_dict[key] = datetime.datetime.strptime(value, "%H:%M").time()
                elif type(value) == dict:
                    output_dict[key] = dict()
                    for k, v in value.items():
                        output_dict[key][k] = datetime.datetime.strptime(v, "%H:%M").time()
            else:
                output_dict[key] = value
        return output_dict


if __name__ == "__main__":
    file = "/Users/dibyaranjan/Upwork/client_ronit_algotrading/ExpiryStraddleAlgoTrading/data/" \
           "config.json"
    config = ConfigReader(config_file_path=Path(file))
    strategy1 = config["strategies"]["strategy1"]
    print(strategy1["option_buying_shifting"])
    print(strategy1["entry_time"])
    print(strategy1["exit_time"])
