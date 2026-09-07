from datetime import timedelta

import pytest

from app.core.security import create_access_token


def test_register_returns_created_user(client):
    resp = client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert body["is_admin"] is False
    assert "hashed_password" not in body


def test_register_rejects_duplicate_email(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    resp = client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert resp.status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post("/auth/register", json={"email": "x@example.com", "password": "short"})
    assert resp.status_code == 422


def test_login_returns_bearer_token(client):
    client.post("/auth/register", json={"email": "b@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "b@example.com", "password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


def test_login_wrong_password_is_401(client):
    client.post("/auth/register", json={"email": "c@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "c@example.com", "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_user_is_401(client):
    resp = client.post("/auth/login", json={"email": "ghost@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client, auth_headers):
    headers = auth_headers("me@example.com")
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.parametrize("token", ["garbage", "a.b.c"])
def test_me_rejects_malformed_token(client, token):
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_me_rejects_expired_token(client, auth_headers):
    auth_headers("exp@example.com")
    from app.database import SessionLocal
    from app.models import User
    from sqlalchemy import select

    with SessionLocal() as s:
        user = s.scalar(select(User).where(User.email == "exp@example.com"))
        expired = create_access_token(user.id, expires_delta=timedelta(minutes=-1))

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
