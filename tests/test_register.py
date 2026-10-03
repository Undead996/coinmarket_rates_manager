"""
test_register.py — тесты для POST /register.

Что проверяем:
  1. Успешная регистрация нового пользователя → 200 + UserResponse
  2. Попытка регистрации с уже существующим username → 400
  3. Пропущенные обязательные поля → 422 (валидация Pydantic)
  4. Пустая строка username → 200 (нет ограничения min_length в схеме)

Ключевые приёмы тестирования FastAPI:
  • client(mock_db) — фикстура, которая переопределяет get_db
    через app.dependency_overrides[get_db], чтобы ни один запрос
    не ходил в реальную базу данных.
  • patch.object(crud, ...) — мок конкретных функций
    crud_controller.py (get_user_by_username, create_user),
    чтобы контролировать, что вернёт "БД".
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch
from datetime import datetime

# Импорт приложения — теперь он безопасен, потому что conftest.py
# уже подменил pymysql и engine на MagicMock.
from main import app
from src.db.database import get_db         # оригинальная зависимость
from controllers import crud_controller as crud


# ── Фикстуры ──────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """
    Создаёт мок-объект SQLAlchemy Session.
    spec=Session говорит MagicMock'у: "обладай всеми методами
    настоящего Session, чтобы вызовы .query(), .commit(), .add()
    не падали с AttributeError".
    """
    return MagicMock(spec=Session)


@pytest.fixture
def client(mock_db):
    """
    FastAPI TestClient с ПОДМЕНЁННОЙ зависимостью get_db.
    Вместо реальной сессии БД каждый эндпоинт получит mock_db.

    _override() — функция-генератор, которую FastAPI вызывает
    как Depends(get_db). Она возвращает mock_db и "закрывает" его
    (no-op).

    app.dependency_overrides — словарь, в котором FastAPI ищет
    замену для любой зависимости. Ключ — оригинальная функция
    (get_db), значение — новая функция (_override).

    После теста удаляем переопределение, чтобы не повлиять
    на соседние тесты.
    """

    def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    # clean-up: убираем переопределение после теста
    app.dependency_overrides.pop(get_db, None)


# ── Набор тестов ──────────────────────────────────────────────────


class TestRegister:
    """
    Группируем тесты для /register в один класс.
    VALID — эталонный payload, переиспользуется в нескольких тестах.
    """
    VALID = {"username": "alice", "password": "secret123"}

    # ── 1. Успешная регистрация ──
    def test_register_creates_user(self, client):
        """
        Цель: проверить, что при уникальном username эндпоинт
              возвращает 200 и тело ответа соответствует UserResponse.

        Как работает подмена:
          1. get_user_by_username → None (пользователь не найден)
          2. create_user → MagicMock с полями id=42, username="alice"
             (имитируем, что create_user вернул объект User из ORM)
          3. Эндпоинт возвращает этот объект — FastAPI сериализует
             его в JSON через Pydantic UserResponse.
        """
        # patch.object(crud, "get_user_by_username", return_value=None)
        #   → любой вызов crud.get_user_by_username() вернёт None
        # patch.object(crud, "create_user") as mock_create
        #   → перехватываем вызов create_user, можем проверить
        #     что он был вызван (assert_called_once)
        with patch.object(crud, "get_user_by_username", return_value=None), \
             patch.object(crud, "create_user") as mock_create:

            # Формируем "ответ от БД" — объект, похожий на User
            mock_user = MagicMock()
            mock_user.id = 42
            mock_user.username = "alice"
            mock_user.is_active = True
            mock_user.created_at = datetime(2025, 1, 1)

            # Говорим моку: "когда тебя вызовут — верни mock_user"
            mock_create.return_value = mock_user

            # Отправляем POST-запрос
            resp = client.post("/register", json=self.VALID)

        # Проверки
        assert resp.status_code == 200, \
            "Эндпоинт не имеет status_code, поэтому 200 по умолчанию"
        data = resp.json()
        assert data["username"] == "alice"
        assert data["id"] == 42
        assert data["is_active"] is True

        # Убеждаемся, что create_user был вызван ровно один раз
        mock_create.assert_called_once()

    # ── 2. Дубликат username ──
    def test_register_duplicate(self, client):
        """
        Цель: если пользователь с таким username уже существует,
              эндпоинт должен вернуть 400 + detail.

        get_user_by_username возвращает НЕ None (найден!), поэтому
        код идёт в ветку if db_user: raise HTTPException(400).
        """
        # Создаём объект, имитирующий найденного пользователя
        existing = MagicMock()
        existing.username = "alice"

        with patch.object(crud, "get_user_by_username",
                          return_value=existing):
            resp = client.post("/register", json=self.VALID)

        assert resp.status_code == 400, \
            "Должен быть 400 Bad Request"
        assert resp.json()["detail"] == "Username already registered"

    # ── 3. Пропущенные обязательные поля ──
    @pytest.mark.parametrize("payload,desc", [
        ({"password": "x"},        "нет username"),
        ({"username": "x"},        "нет password"),
        ({},                       "пустое тело"),
    ])
    def test_register_missing_fields(self, client, payload, desc):
        """
        Цель: Pydantic-валидация схемы UserCreate.
              Поля username и password — обязательные.
              Если поля нет — должен быть 422 Unprocessable Entity.

        Параметризация: три вызова с разными payload.
        desc — строка, которая появится в отчёте при падении.
        """
        resp = client.post("/register", json=payload)
        assert resp.status_code == 422, desc

    # ── 4. Пустая строка username ──
    def test_register_empty_username(self, client):
        """
        Цель: убедиться, что Pydantic не имеет min_length=1,
              поэтому пустая строка "" проходит валидацию.

        Если бы в UserCreate стояло Field(min_length=1),
        ответ был бы 422. В текущей схеме — 200.
        """
        with patch.object(crud, "get_user_by_username",
                          return_value=None), \
             patch.object(crud, "create_user") as mock_create:

            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.username = ""
            mock_user.is_active = True
            mock_user.created_at = datetime(2025, 1, 1)
            mock_create.return_value = mock_user

            resp = client.post("/register",
                               json={"username": "", "password": "s"})

        assert resp.status_code == 200
        assert resp.json()["username"] == ""