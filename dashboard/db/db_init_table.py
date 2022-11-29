"""
File:           db_init_table.py
Author:         Dibyaranjan Sathua
Created on:     16/11/22, 4:21 pm

Initialize tables with some default data
"""
from dashboard.db import SessionLocal
from dashboard.db.db_api import DBApi


db = SessionLocal()


def init_tables():
    DBApi.create_algo_power_status(db)
    DBApi.create_run_config(db)


if __name__ == "__main__":
    init_tables()
