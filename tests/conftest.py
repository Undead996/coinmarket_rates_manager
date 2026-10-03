"""
conftest.py — подготавливает окружение для всех тестов.
Задача: подменить модуль базы данных, чтобы тесты могли
        запускаться БЕЗ реального MySQL-сервера.

Важно: этот файл выполняется ДО импорта любого теста.
       Мы подменяем pymysql и engine на уровне процесса,
       чтобы from main import app не упало с ошибкой
       "ModuleNotFoundError: No module named 'pymysql'".
"""

import sys
from unittest.mock import MagicMock

# ── 1. Подмена pymysql ────────────────────────────────────────────
# SQLAlchemy при создании engine = create_engine("mysql+pymysql://...")
# пытается импортировать pymysql. Если библиотека не установлена —
# будет ImportError. Мы подкладываем заглушку прямо в sys.modules,
# чтобы import pymysql внутри SQLAlchemy вернул MagicMock.
sys.modules["pymysql"] = MagicMock()

# ── 2. Подмена engine, SessionLocal и прочего в src.db.database ──
# Импортируем модуль database.py. Все его глобальные переменные
# (engine, SessionLocal, Base, validate_mysql_config) сейчас равны
# настоящим объектам SQLAlchemy. Мы их заменяем на MagicMock,
# чтобы при импорте main.py не выполнялся реальный connect к MySQL.
import src.db.database as db_mod

# engine — глобальный объект create_engine(...) в database.py.
# Подменяем заглушкой — никакого TCP-соединения к MySQL не будет.
db_mod.engine = MagicMock()

# SessionLocal — фабрика сессий. Замена на MagicMock гарантирует,
# что get_db() не откроет реальную транзакцию.
db_mod.SessionLocal = MagicMock()

# Base.metadata.create_all вызывается в main.py для авто-создания таблиц.
# В тестах нам это не нужно — подменяем пустой функцией.
db_mod.Base.metadata.create_all = MagicMock()

# validate_mysql_config() вызывается при импорте database.py.
# Она читает .env и завершает программу через sys.exit(1),
# если переменные окружения не заданы. Подмена возвращает
# словарь-заглушку, чтобы скрипт не упал.
db_mod.validate_mysql_config = MagicMock(return_value={
    "MYSQL_HOST": "localhost",
    "MYSQL_PORT": "3306",
    "MYSQL_USER": "test",
    "MYSQL_PASSWORD": "test",
    "MYSQL_DATABASE": "test",
})

# ── 3. Сама get_db (необязательно) ────────────────────────────────
# Эта подмена технически не нужна, потому что каждый тестовый файл
# переопределяет get_db через app.dependency_overrides. Но мы всё
# равно ставим заглушку на всякий случай.
db_mod.get_db = MagicMock()