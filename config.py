import os
from datetime import timedelta
from urllib.parse import quote_plus

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _default_database_uri() -> str:
    """
    XAMPP MySQL: database `admin_portal` (see schema_xampp.sql) with tables `admins`, `password_resets`.
    Set USE_MYSQL=1 (or pass DATABASE_URL). Defaults: root / no password / 127.0.0.1.
    """
    if os.environ.get("USE_MYSQL", "").lower() in ("1", "true", "yes"):
        user = os.environ.get("MYSQL_USER", "root")
        password = os.environ.get("MYSQL_PASSWORD", "")
        host = os.environ.get("MYSQL_HOST", "127.0.0.1")
        port = os.environ.get("MYSQL_PORT", "3306")
        database = os.environ.get("MYSQL_DATABASE", "admin_portal")
        user_q = quote_plus(user)
        if password:
            auth = f"{user_q}:{quote_plus(password)}"
        else:
            auth = user_q
        return f"mysql+pymysql://{auth}@{host}:{port}/{database}?charset=utf8mb4"
    return f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"


class Config:
    # --- Core ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

    # --- Database ---
    # Override with DATABASE_URL, or set USE_MYSQL=1 for XAMPP defaults (see _default_database_uri).
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _default_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Session / Remember-Me ---
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- itsdangerous token expiry (seconds) ---
    PASSWORD_RESET_TOKEN_EXPIRY = 3600  # 1 hour

    # --- Allowed opportunity categories ---
    ALLOWED_CATEGORIES = [
        "Education",
        "Healthcare",
        "Environment",
        "Community",
        "Technology",
        "Arts & Culture",
        "Animal Welfare",
        "Disaster Relief",
        "Elderly Care",
        "Youth Development",
        "Other",
    ]
