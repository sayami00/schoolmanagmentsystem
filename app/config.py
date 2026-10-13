import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
PAGES_DIR = STATIC_DIR / "pages"


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def db_path() -> Path:
    # Read on every call so tests can point the app at a temporary database.
    return Path(os.environ.get("EAMS_DB_PATH", str(BASE_DIR / "data" / "eams.db")))


COOKIE_NAME = "eams_session"
COOKIE_SECURE = _flag("EAMS_COOKIE_SECURE", "0")
SESSION_HOURS = int(os.environ.get("EAMS_SESSION_HOURS", "8"))
SEED_ON_EMPTY = _flag("EAMS_SEED_ON_EMPTY", "1")

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
PBKDF2_ITERATIONS = 600_000
