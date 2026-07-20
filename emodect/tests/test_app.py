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
from app import app as flask_app, db, User


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["MAIL_SUPPRESS_SEND"] = True  # never send real emails in tests
    with flask_app.test_client() as client:
        with flask_app.app_context():
            db.create_all()
        yield client
        with flask_app.app_context():
            db.drop_all()


def _verify_user(username):
    """Test helper: mark a user's email as verified directly in the DB,
    bypassing the real email-click flow (which isn't exercised here since
    MAIL_SUPPRESS_SEND just logs instead of sending)."""
    with flask_app.app_context():
        user = User.query.filter_by(username=username).first()
        user.email_verified = True
        db.session.commit()


def test_index_redirects_to_login(client):
    res = client.get("/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_register_requires_email_confirmation_before_login(client):
    res = client.post(
        "/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret1"},
    )
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Login should be blocked until the email is verified.
    res = client.post("/login", json={"username": "alice", "password": "secret1"})
    assert res.status_code == 403
    assert res.get_json()["unverified"] is True

    # Simulate clicking the confirmation link, then login should succeed.
    _verify_user("alice")
    res = client.post("/login", json={"username": "alice", "password": "secret1"})
    assert res.status_code == 200
    assert res.get_json()["success"] is True


def test_verify_email_with_invalid_token(client):
    res = client.get("/verify-email/not-a-real-token")
    assert res.status_code == 200  # renders an "invalid link" page, not an error status
    assert b"Invalid link" in res.data


def test_resend_confirmation_does_not_leak_account_existence(client):
    client.post(
        "/register",
        json={"username": "carol", "email": "carol@example.com", "password": "secret1"},
    )
    res_existing = client.post("/resend-confirmation", json={"email": "carol@example.com"})
    res_missing = client.post("/resend-confirmation", json={"email": "nobody@example.com"})
    assert res_existing.status_code == 200
    assert res_missing.status_code == 200
    assert res_existing.get_json()["message"] == res_missing.get_json()["message"]


def test_forgot_password_does_not_leak_account_existence(client):
    client.post(
        "/register",
        json={"username": "dave", "email": "dave@example.com", "password": "secret1"},
    )
    res_existing = client.post("/forgot-password", json={"email": "dave@example.com"})
    res_missing = client.post("/forgot-password", json={"email": "nobody@example.com"})
    assert res_existing.status_code == 200
    assert res_missing.status_code == 200
    assert res_existing.get_json()["message"] == res_missing.get_json()["message"]


def test_reset_password_with_invalid_token(client):
    res = client.post("/reset-password/not-a-real-token", json={"password": "newpass1"})
    assert res.status_code == 400


def test_delete_account_requires_login(client):
    res = client.post("/delete-account", json={"password": "whatever"})
    assert res.status_code == 401


def test_delete_account_requires_correct_password(client):
    client.post(
        "/register",
        json={"username": "erin", "email": "erin@example.com", "password": "secret1"},
    )
    _verify_user("erin")
    client.post("/login", json={"username": "erin", "password": "secret1"})

    res = client.post("/delete-account", json={"password": "wrong-password"})
    assert res.status_code == 401

    res = client.post("/delete-account", json={"password": "secret1"})
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Account should no longer be able to log in.
    res = client.post("/login", json={"username": "erin", "password": "secret1"})
    assert res.status_code == 401


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
