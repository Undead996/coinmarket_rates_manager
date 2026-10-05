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
import requests
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
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


# ── Фикстура module-scope: прямое подключение к тестовой БД ──────


@pytest.fixture(scope="module")
def db_session():
    """
    Фикстура с scope='module', которая создаёт ИЗОЛИРОВАННУЮ
    SQLite-базу в памяти и возвращает сессию для прямых запросов.

    scope='module' — фикстура создаётся ОДИН раз для ВСЕХ тестов
    в файле (модуле). Тесты внутри модуля разделяют одну сессию.

    Ключевые моменты:
      1. create_engine("sqlite:///:memory:") — лёгкая БД в ОЗУ.
      2. Base.metadata.create_all(bind=engine) — создаём схему
         один раз при первом вызове фикстуры.
      3. sessionmaker(bind=engine) — фабрика сессий, привязанная
         к нашему engine.
      4. Тест получает готовую сессию и может делать напрямую
         session.add(), session.query(), session.commit() и т.д.
      5. После всех тестов модуля закрываем engine — ресурсы
         освобождены.
    """
    from src.db.database import Base

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    yield session

    session.close()
    engine.dispose()


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


# ══════════════════════════════════════════════════════════════════
# Примеры для учебных целей: параметризированная фикстура + тест
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(params=[
    {"username": "alice",   "expected_id": 42},
    {"username": "bob",     "expected_id": 99},
    {"username": "carol",   "expected_id": 7},
])
def parametrized_user_fixture(request):
    """
    Параметризированная фикстура.

    Ключевые моменты:
      1. params= — список значений. Для каждого элемента pytest
         запустит зависящие тесты отдельно.
      2. request.param — текущий элемент из params (внутри функции).
      3. Фикстура сама настраивает моки, чтобы тесту не пришлось
         повторять boilerplate с patch-контекстами.
    """
    data = request.param
    with patch.object(crud, "get_user_by_username", return_value=None), \
         patch.object(crud, "create_user") as mock_create:

        mock_user = MagicMock()
        mock_user.id = data["expected_id"]
        mock_user.username = data["username"]
        mock_user.is_active = True
        mock_user.created_at = datetime(2025, 1, 1)
        mock_create.return_value = mock_user

        # yield — тест получит dict с данными; код после yield
        # выполнится после завершения теста (clean-up).
        yield {
            "username": data["username"],
            "expected_id": data["expected_id"],
        }


@pytest.mark.parametrize("role,http_method", [
    ("guest",   "POST"),
    ("admin",   "POST"),
    ("service", "POST"),
])
def test_parametrized_register_with_fixture(client,
                                            parametrized_user_fixture,
                                            role, http_method):
    """
    Пример теста, в котором ОДНОВРЕМЕННО используются:

      • параметризированная фикстура parametrized_user_fixture
        (пробегает по трём наборам данных — alice, bob, carol)

      • параметризация через @pytest.mark.parametrize
        (пробегает по трём комбинациям role × http_method)

    Итоговое число запусков = 3 (параметры фикстуры) × 3 (parametrize) = 9.

    В реальном тесте проверяли бы, что role влияет на поведение
    эндпоинта. Здесь — только демонстрация синтаксиса.
    """
    data = parametrized_user_fixture
    resp = client.post(
        f"/register?role={role}",
        json={"username": data["username"], "password": "pwd"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == data["username"]
    assert resp.json()["id"] == data["expected_id"]


# ══════════════════════════════════════════════════════════════════
# Пример: тест с реальным HTTP-вызовом внешнего API (requests)
# ══════════════════════════════════════════════════════════════════


HTTPBIN_URL = "https://httpbin.org/post"


@pytest.mark.parametrize("payload,expected_keys", [
    ({"name": "Alice",   "age": 30},  {"name", "age"}),
    ({"name": "Bob",     "age": 25},  {"name", "age"}),
    ({"query": "pytest", "page": 1},  {"query", "page"}),
])
def test_external_post_request(payload, expected_keys):
    """
    Тест, который отправляет POST-запрос на ВНЕШНИЙ HTTP-сервис
    (httpbin.org/post) с передачей параметров в теле запроса.

    httpbin.org/post — echo-сервис: он возвращает JSON, в котором
    поле 'json' содержит то, что мы отправили.

    Ключевые моменты:
      1. requests.post(url, json=...) — стандартный HTTP-запрос.
      2. @pytest.mark.parametrize — три разных payload, каждый
         со своим набором ожидаемых ключей.
      3. Тест зависит от сети — при недоступности httpbin.org
         он упадёт. Для учебного примера это нормально.
      4. В реальном проекте внешние HTTP-вызовы мокают через
         responses, httpretty или monkeypatch.
    """
    resp = requests.post(HTTPBIN_URL, json=payload, timeout=10)

    assert resp.status_code == 200, \
        "httpbin.org должен вернуть 200"

    data = resp.json()
    echo = data.get("json", {})

    # Проверяем, что в эхо-ответе присутствуют все отправленные ключи
    for key in expected_keys:
        assert key in echo, f"Ключ '{key}' отсутствует в ответе сервера"

    # Проверяем, что Content-Type в запросе — application/json
    assert data.get("headers", {}).get("Content-Type") \
        == "application/json"


# ══════════════════════════════════════════════════════════════════
# Пример: тест, использующий db_session (прямая работа с БД)
# ══════════════════════════════════════════════════════════════════


def test_direct_db_insert_and_query(db_session):
    """
    Тест, который использует фикстуру db_session с scope='module'
    для прямой вставки и выборки из БД без моков.

    Фикстура db_session:
      • scope='module' — создаётся один раз на весь файл.
      • Использует SQLite :memory: и создаёт все таблицы
        через Base.metadata.create_all.
      • Тесты внутри одного модуля разделяют одну сессию
        (но для учебных целей каждый тест может начинать
        с чистого состояния, используя rollback или
        отдельную транзакцию).

    Демонстрирует:
      • session.add() — добавить запись.
      • session.commit() — зафиксировать.
      • session.query(...).filter(...).first() — прочитать.
      • Прямые манипуляции с моделями SQLAlchemy.
    """
    from src.models.models import User
    from src.auth.auth import get_password_hash

    hashed_pw = get_password_hash("secret123")

    # Создаём пользователя напрямую через ORM
    new_user = User(
        username="direct_test_user",
        hashed_password=hashed_pw,
        is_active=True,
    )
    db_session.add(new_user)
    db_session.commit()

    # Читаем пользователя обратно
    fetched = (
        db_session.query(User)
        .filter(User.username == "direct_test_user")
        .first()
    )

    assert fetched is not None, "Пользователь должен быть найден"
    assert fetched.username == "direct_test_user"
    assert fetched.is_active is True
    assert fetched.id is not None, "ID должен быть назначен БД"