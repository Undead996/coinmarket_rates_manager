"""
test_rate_calc.py — тесты для validate_currency_and_get_rate.

Никакого FastAPI, TestClient, dependency_overrides.
Только мок SQLAlchemy Session + вызов функции.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Импортируем тестируемую функцию.
# ВАЖНО: этот импорт НЕ тянет main.py и НЕ требует pymysql,
# потому что rate_calc.py импортирует только модели SQLAlchemy
# (которые просто описывают структуру таблиц) — без engine.
from src.calculate.rate_calc import validate_currency_and_get_rate


class TestValidateCurrencyAndGetRate:
    """
    Тесты для функции валидации валюты и получения курса.
    Функция:
      — ищет валюту по symbol
      — если валюта активна — ищет последний rate с date_activation <= now
      — возвращает {"curr": bind_curr, "price": price} или {"curr": symbol, "price": None}
    """

    # ── 1. Валюта не найдена в таблице currencies ──
    def test_currency_not_found_returns_symbol(self):
        """
        Если валюты с таким symbol нет в таблице currencies,
        функция должна вернуть {"curr": original_symbol, "price": None}.
        """
        db = MagicMock()

        # Настраиваем цепочку: db.query(Currency).filter(...).first() → None
        db.query.return_value.filter.return_value.first.return_value = None

        result = validate_currency_and_get_rate(db, "BTC", "symbol")

        assert result == {"curr": "BTC", "price": None}
        # Проверяем, что в БД действительно ходили за Currency
        db.query.assert_called_once()

    # ── 2. Валюта найдена, но не активна → HTTPException ──
    def test_currency_not_active_raises_error(self):
        """
        Если валюта есть в БД, но active=False — HTTPException(400).
        """
        db = MagicMock()

        # Создаём объект, похожий на Currency: symbol="BTC", active=False
        mock_currency = MagicMock()
        mock_currency.active = False
        mock_currency.id = 1
        db.query.return_value.filter.return_value.first.return_value = mock_currency

        with pytest.raises(Exception) as exc_info:
            validate_currency_and_get_rate(db, "BTC", "symbol")

        assert exc_info.value.status_code == 400
        assert "not active" in exc_info.value.detail

    # ── 3. Валюта активна, есть rate с подходящей date_activation ──
    def test_currency_found_and_rate_found(self):
        """
        Счастливый путь: валюта активна, есть rate c date_activation <= now.
        Должна вернуть {"curr": bind_curr, "price": price}.
        """
        db = MagicMock()

        # 1) Currency: active=True
        mock_currency = MagicMock()
        mock_currency.active = True
        mock_currency.id = 1
        db.query.return_value.filter.return_value.first.return_value = mock_currency

        # 2) Rate: bind_curr="USD", price=50000, date_activation в прошлом
        mock_rate = MagicMock()
        mock_rate.bind_curr = "USD"
        mock_rate.price = 50000.0
        mock_rate.date_activation = datetime(2020, 1, 1)  # прошлое → подходит
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_rate]

        result = validate_currency_and_get_rate(db, "BTC", "symbol")

        assert result == {"curr": "USD", "price": 50000.0}

    # ── 4. Валюта активна, rate есть, но date_activation в будущем ──
    def test_rate_not_activated_yet_raises_error(self):
        """
        Все rate есть, но у всех date_activation > now → HTTPException.
        """
        db = MagicMock()

        mock_currency = MagicMock()
        mock_currency.active = True
        mock_currency.id = 1
        db.query.return_value.filter.return_value.first.return_value = mock_currency

        # rate с датой в будущем
        mock_rate = MagicMock()
        mock_rate.date_activation = datetime(2099, 1, 1)
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_rate]

        with pytest.raises(Exception) as exc_info:
            validate_currency_and_get_rate(db, "BTC", "symbol")

        assert exc_info.value.status_code == 400
        assert "No active rate" in exc_info.value.detail

    # ── 5. Валюта активна, но rate вообще нет ──
    def test_currency_active_no_rates(self):
        """
        Валюта есть и активна, но у неё нет rate-записей.
        Функция не отличает "нет валюты" от "нет rate" —
        возвращает {"curr": symbol, "price": None}.
        """
        db = MagicMock()

        mock_currency = MagicMock()
        mock_currency.active = True
        mock_currency.id = 1
        db.query.return_value.filter.return_value.first.return_value = mock_currency

        # Пустой список rate → if rates: ложно → выход из if currency:
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = validate_currency_and_get_rate(db, "BTC", "symbol")

        assert result == {"curr": "BTC", "price": None}