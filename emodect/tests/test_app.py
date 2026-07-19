"""
Basic smoke tests for the Emotion Analyzer app.
Run with: pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FLASK_CONFIG", "testing")
os.environ.setdefault("GEMINI_API_KEY", "")  # tests don't call the real API

import pytest
from app import app as flask_app, db


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        with flask_app.app_context():
            db.create_all()
        yield client
        with flask_app.app_context():
            db.drop_all()


def test_index_redirects_to_login(client):
    res = client.get("/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_register_and_login(client):
    res = client.post(
        "/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret1"},
    )
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    res = client.post("/login", json={"username": "alice", "password": "secret1"})
    assert res.status_code == 200
    assert res.get_json()["success"] is True


def test_register_rejects_short_password(client):
    res = client.post(
        "/register",
        json={"username": "bob", "email": "bob@example.com", "password": "123"},
    )
    assert res.status_code == 400


def test_login_rejects_bad_credentials(client):
    res = client.post("/login", json={"username": "nobody", "password": "wrongpass"})
    assert res.status_code == 401


def test_dashboard_requires_login(client):
    res = client.get("/dashboard")
    assert res.status_code == 302


def test_analyze_requires_login(client):
    res = client.post("/analyze", json={"message": "hello"})
    assert res.status_code == 401


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
