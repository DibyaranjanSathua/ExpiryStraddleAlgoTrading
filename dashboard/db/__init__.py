"""
File:           __init__.py
Author:         Dibyaranjan Sathua
Created on:     16/11/22, 12:59 pm
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# Load env vars from .env
dotenv_path = Path(__file__).resolve().parents[1] / 'env' / '.env'
load_dotenv(dotenv_path=dotenv_path)


DB_NAME = os.environ.get("DB_NAME", "algotrading")
DB_USER = os.environ.get("DB_USER", "algobot")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "algobot123")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_size=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
