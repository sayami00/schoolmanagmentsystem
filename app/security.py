import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status

from . import config
from .db import get_db, one


# ---------- passwords ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, config.PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${config.PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


# A fixed hash used to spend the same time verifying when the username does not exist.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


def burn_verify_time(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


# ---------- time helpers ----------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- sessions ----------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = utcnow() + timedelta(hours=config.SESSION_HOURS)
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (iso(utcnow()),))
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, iso(expires)),
    )
    return token


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def user_from_token(conn: sqlite3.Connection, token: str | None) -> dict | None:
    if not token:
        return None
    return one(conn.execute(
        """SELECT u.id, u.username, u.full_name, u.role
             FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1""",
        (_token_hash(token), iso(utcnow())),
    ))


# ---------- dependencies ----------

def current_user(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    user = user_from_token(conn, request.cookies.get(config.COOKIE_NAME))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user
