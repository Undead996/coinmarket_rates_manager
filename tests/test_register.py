"""Tests for POST /register with mocked get_db dependency."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch
from datetime import datetime

from main import app
from src.db.database import get_db
from controllers import crud_controller as crud


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def client(mock_db):
    def _override():
        yield mock_db
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


class TestRegister:
    VALID = {"username": "alice", "password": "secret123"}

    def test_register_creates_user(self, client, mock_db):
        with patch.object(crud, "get_user_by_username", return_value=None), \
             patch.object(crud, "create_user") as mock_create:
            mock_user = MagicMock()
            mock_user.id = 42
            mock_user.username = "alice"
            mock_user.is_active = True
            mock_user.created_at = datetime(2025, 1, 1)
            mock_create.return_value = mock_user
            resp = client.post("/register", json=self.VALID)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "alice"
        assert data["id"] == 42
        assert data["is_active"] is True

    def test_register_duplicate(self, client):
        existing = MagicMock()
        existing.username = "alice"
        with patch.object(crud, "get_user_by_username", return_value=existing):
            resp = client.post("/register", json=self.VALID)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Username already registered"

    @pytest.mark.parametrize("payload,desc", [
        ({"password": "x"}, "missing username"),
        ({"username": "x"}, "missing password"),
        ({}, "empty body"),
    ])
    def test_register_missing_fields(self, client, payload, desc):
        resp = client.post("/register", json=payload)
        assert resp.status_code == 422, desc

    def test_register_empty_username(self, client):
        with patch.object(crud, "get_user_by_username", return_value=None), \
             patch.object(crud, "create_user") as mock_create:
            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.username = ""
            mock_user.is_active = True
            mock_user.created_at = datetime(2025, 1, 1)
            mock_create.return_value = mock_user
            resp = client.post("/register", json={"username": "", "password": "s"})
        assert resp.status_code == 200
        assert resp.json()["username"] == ""