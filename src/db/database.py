from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def validate_mysql_config():
    """Validate that all required MySQL environment variables are present"""
    required_vars = {
        "MYSQL_HOST": os.getenv("MYSQL_HOST"),
        "MYSQL_PORT": os.getenv("MYSQL_PORT"),
        "MYSQL_USER": os.getenv("MYSQL_USER"),
        "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD"),
        "MYSQL_DATABASE": os.getenv("MYSQL_DATABASE")
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        error_msg = f"""
❌ ОШИБКА КОНФИГУРАЦИИ БАЗЫ ДАННЫХ ❌

Отсутствуют обязательные переменные окружения для подключения к MySQL:
{', '.join(missing_vars)}

Пожалуйста, добавьте следующие переменные в файл .env:
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_mysql_username
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=coinmarket_db
        """
        print(error_msg)
        sys.exit(1)
    
    return required_vars

# Validate configuration and get MySQL variables
mysql_config = validate_mysql_config()
MYSQL_HOST = mysql_config["MYSQL_HOST"]
MYSQL_PORT = mysql_config["MYSQL_PORT"]
MYSQL_USER = mysql_config["MYSQL_USER"]
MYSQL_PASSWORD = mysql_config["MYSQL_PASSWORD"]
MYSQL_DATABASE = mysql_config["MYSQL_DATABASE"]

# Construct MySQL URL from individual variables
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# MySQL engine configuration
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_database_url():
    """Get the database URL for migrations"""
    return DATABASE_URL

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
