"""
File:           db_api.py
Author:         Dibyaranjan Sathua
Created on:     16/11/22, 3:13 pm
"""
from sqlalchemy.orm import Session

from dashboard.db import models


class DBApi:
    """ Contains database CRUD operations """

    @staticmethod
    def get_algo_power(db: Session) -> models.PowerAlgoSystem:
        return db.query(models.PowerAlgoSystem).first()

    @staticmethod
    def update_algo_power_status(db: Session, on: bool) -> models.PowerAlgoSystem:
        power = DBApi.get_algo_power(db)
        power.on = on
        db.commit()
        db.refresh(power)
        return power

    @staticmethod
    def create_algo_power_status(db: Session) -> models.PowerAlgoSystem:
        power = models.PowerAlgoSystem(on=False)
        db.add(power)
        db.commit()
        db.refresh(power)
        return power

    @staticmethod
    def get_users(db: Session):
        return db.query(models.User).all()

    @staticmethod
    def get_run_config_by_day(db: Session, day: str) -> models.AlgoRunConfig:
        return db.query(models.AlgoRunConfig).filter(models.AlgoRunConfig.day == day).first()

    @staticmethod
    def get_run_config(db: Session):
        return db.query(models.AlgoRunConfig).order_by(models.AlgoRunConfig.id).all()

    @staticmethod
    def update_run_config(db: Session, data: dict[str, dict]):
        run_configs = db.query(models.AlgoRunConfig).all()
        for config in run_configs:
            run_time_data = data[config.day]
            config.run = run_time_data["run"]
            config.time = run_time_data["time"]
        db.bulk_save_objects(run_configs)
        db.commit()

    @staticmethod
    def create_run_config(db: Session):
        run_configs = [
            models.AlgoRunConfig(day=day, run=False, time=None)
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
        ]
        db.add_all(run_configs)
        db.commit()



