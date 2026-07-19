"""
Application configuration.

FLASK_ENV / FLASK_CONFIG selects which config class is used.
SECRET_KEY MUST be set via environment variable in production - a random
key regenerated on every restart (as the original app did) invalidates all
sessions on every deploy/restart and is not suitable for production use.
"""
import os
from datetime import timedelta


def _bool_env(name, default=False):
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


_INSTANCE_DIR = os.path.join(os.getcwd(), "instance")
os.makedirs(_INSTANCE_DIR, exist_ok=True)

# SQLite URIs require forward slashes even on Windows (a URI is not a raw
# filesystem path). os.path.join produces backslashes on Windows, which
# corrupts "sqlite:///" + path into something SQLAlchemy/SQLite can't open
# ("unable to open database file"). Path(...).as_posix() normalizes this
# on every platform.
from pathlib import Path

_DB_PATH = Path(_INSTANCE_DIR, "emotions.db").as_posix()


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    DEBUG = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        if self.SECRET_KEY == "dev-key-change-me-in-production":
            raise RuntimeError(
                "SECRET_KEY must be set to a secure random value in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    env = os.getenv("FLASK_CONFIG", os.getenv("FLASK_ENV", "development")).lower()
    config_cls = _CONFIGS.get(env, DevelopmentConfig)
    # Instantiate production config to trigger the SECRET_KEY safety check,
    # but return the class either way (Flask's from_object accepts both).
    if config_cls is ProductionConfig:
        config_cls()
    return config_cls
