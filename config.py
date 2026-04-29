import os


def _is_production() -> bool:
    return os.environ.get("FLASK_ENV", "development").lower() == "production"


class Config:
    ENV = os.environ.get("FLASK_ENV", "development").lower()
    DEBUG = not _is_production()
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _is_production()
    REMEMBER_COOKIE_SECURE = _is_production()
    PREFERRED_URL_SCHEME = "https" if _is_production() else "http"

    @staticmethod
    def validate():
        if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")
        if _is_production():
            secret = os.environ.get("SECRET_KEY")
            if not secret or secret == "dev-secret-key-change-me":
                raise RuntimeError("SECRET_KEY must be set to a non-default value in production.")
