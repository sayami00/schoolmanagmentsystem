import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import config
from ..db import get_db, one, transaction
from ..security import (burn_verify_time, create_session, current_user, delete_session, hash_password,
                        iso, utcnow, verify_password)
from ..validation import Password

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID = "Invalid username or password"


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        config.COOKIE_NAME, token,
        max_age=config.SESSION_HOURS * 3600,
        httponly=True, samesite="strict", secure=config.COOKIE_SECURE, path="/",
    )


@router.post("/login")
def login(body: LoginIn, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    user = one(conn.execute(
        "SELECT id, username, full_name, role, password_hash, is_active, failed_attempts, locked_until "
        "FROM users WHERE username = ?", (body.username.strip(),)))
    if not user:
        burn_verify_time(body.password)
        raise HTTPException(401, INVALID)

    now = utcnow()
    if user["locked_until"] and datetime.strptime(user["locked_until"], "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=now.tzinfo) > now:
        raise HTTPException(423, "Account temporarily locked after repeated failed logins. Try again later.")

    if not verify_password(body.password, user["password_hash"]) or not user["is_active"]:
        attempts = user["failed_attempts"] + 1
        locked = iso(now + timedelta(minutes=config.LOCKOUT_MINUTES)) if attempts >= config.MAX_FAILED_LOGINS else None
        conn.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                     (0 if locked else attempts, locked, user["id"]))
        if locked:
            raise HTTPException(423, "Account temporarily locked after repeated failed logins. Try again later.")
        raise HTTPException(401, INVALID)

    with transaction(conn):
        conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (user["id"],))
        token = create_session(conn, user["id"])
    _set_cookie(response, token)
    return {"id": user["id"], "username": user["username"], "full_name": user["full_name"], "role": user["role"]}


@router.post("/logout")
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    token = request.cookies.get(config.COOKIE_NAME)
    if token:
        delete_session(conn, token)
    response.delete_cookie(config.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user


@router.post("/change-password")
def change_password(body: ChangePasswordIn, response: Response,
                    user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    row = one(conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)))
    if not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    with transaction(conn):
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.new_password), user["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        token = create_session(conn, user["id"])
    _set_cookie(response, token)
    return {"ok": True}
