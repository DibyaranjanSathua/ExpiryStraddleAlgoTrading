"""
File:           redis_backend.py
Author:         Dibyaranjan Sathua
Created on:     18/08/22, 5:15 pm
"""
from typing import Optional, Dict, Union
import os
import json

import redis
from dotenv import load_dotenv

from src import BASE_DIR


dotenv_path = BASE_DIR / 'env' / '.env'
load_dotenv(dotenv_path=dotenv_path)


class RedisBackend:
    """ Connect to redis backend and perform pub/sub """

    def __init__(self):
        self._host: str = os.environ.get("REDIS_HOST", "localhost")
        self._port: int = int(os.environ.get("REDIS_PORT", 6379))
        self._redis: Optional[redis.Redis] = None

    def connect(self) -> None:
        self._redis = redis.Redis(host=self._host, port=self._port)

    def set(self, key: str, data: Union[Dict, str]) -> None:
        if isinstance(data, dict):
            data = json.dumps(data)
        self._redis.set(key, data)

    def get(self, key: str) -> Optional[Dict]:
        data = self._redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.decoder.JSONDecodeError:
                return data.decode("utf-8")

    def cleanup(self, pattern="NIFTY*") -> None:
        """ Delete all keys matching the pattern so that everyday we have fresh data """
        for key in self._redis.scan_iter(pattern):
            self._redis.delete(key)

    def print(self, pattern="NIFTY*") -> None:
        """ Print all the keys value matching the pattern """
        for key in self._redis.scan_iter(pattern):
            value = self._redis.get(key)
            print(f"{key} --> {value}")


if __name__ == "__main__":
    obj = RedisBackend()
    obj.connect()
    data = {"token": "12345", "ltp": 123}
    obj.set("NIFTY25AUG2217000CE", data)
    value = obj.get("NIFTY25AUG2217000CE")
    print(value)
    if value is None:
        print("No data found")
    else:
        assert data == value
    obj.set("KEY", "VALUE")
    value = obj.get("KEY")
    print(value)
