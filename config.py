import os


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB_DIR = os.environ.get("DATA_DIR", _BASE_DIR)
_DEFAULT_SQLITE_URI = f"sqlite:///{os.path.join(_DEFAULT_DB_DIR, 'trio_hub.db')}"


def _is_production() -> bool:
    env = os.environ.get("FLASK_ENV", "development").lower()
    return env == "production"


class Config:
    ENV = os.environ.get("FLASK_ENV", "development").lower()
    DEBUG = not _is_production()
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _is_production()
    REMEMBER_COOKIE_SECURE = _is_production()
    PREFERRED_URL_SCHEME = "https" if _is_production() else "http"

    @staticmethod
    def validate():
        if _is_production():
            secret = os.environ.get("SECRET_KEY")
            if not secret or secret == "dev-secret-key-change-me":
                raise RuntimeError(
                    "SECRET_KEY must be set to a non-default value in production."
                )
