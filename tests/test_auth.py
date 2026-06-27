"""Auth tests: registration, login, and protected-endpoint access.

Each test makes a uniquely-named user because the database persists between runs.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _unique() -> str:
    return "authtest_" + uuid.uuid4().hex[:8]


def _register(client, username, password="secret123"):
    return client.post("/auth/register", json={"username": username, "password": password})


# --- registration ---------------------------------------------------------

def test_register_returns_user(client):
    u = _unique()
    r = _register(client, u)
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == u
    assert isinstance(body["id"], int)


def test_register_duplicate_conflicts(client):
    u = _unique()
    _register(client, u)
    assert _register(client, u).status_code == 409


def test_register_short_password_is_422(client):
    assert _register(client, _unique(), password="x").status_code == 422


# --- login ----------------------------------------------------------------

def test_login_returns_bearer_token(client):
    u = _unique()
    _register(client, u)
    r = client.post("/auth/login", json={"username": u, "password": "secret123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_is_401(client):
    u = _unique()
    _register(client, u)
    r = client.post("/auth/login", json={"username": u, "password": "wrongpass"})
    assert r.status_code == 401


def test_login_unknown_user_is_401(client):
    r = client.post("/auth/login", json={"username": _unique(), "password": "secret123"})
    assert r.status_code == 401


# --- protected access -----------------------------------------------------

def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_invalid_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401


def test_protected_flow_with_valid_token(client):
    u = _unique()
    _register(client, u)
    token = client.post(
        "/auth/login", json={"username": u, "password": "secret123"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == u

    # The token lets us reach the protected recommend endpoint.
    assert client.get("/recommend?k=5", headers=headers).status_code == 200
