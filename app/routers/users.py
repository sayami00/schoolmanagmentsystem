import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_db, one, rows, transaction
from ..security import hash_password, require_admin
from ..validation import Name, Password, Username

router = APIRouter(prefix="/api/users", tags=["users"])

FIELDS = "id, username, full_name, role, is_active, locked_until, created_at"


class UserCreate(BaseModel):
    username: Username
    full_name: Name
    role: Literal["admin", "hr"]
    password: Password


class UserUpdate(BaseModel):
    full_name: Name
    role: Literal["admin", "hr"]
    is_active: bool
    password: Password | None = None


@router.get("")
def list_users(_: dict = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    return rows(conn.execute(f"SELECT {FIELDS} FROM users ORDER BY username"))


@router.post("", status_code=201)
def create_user(body: UserCreate, _: dict = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    try:
        cur = conn.execute(
            "INSERT INTO users (username, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
            (body.username, body.full_name, body.role, hash_password(body.password)))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username already exists")
    return one(conn.execute(f"SELECT {FIELDS} FROM users WHERE id = ?", (cur.lastrowid,)))


@router.put("/{user_id}")
def update_user(user_id: int, body: UserUpdate, admin: dict = Depends(require_admin),
                conn: sqlite3.Connection = Depends(get_db)):
    if not one(conn.execute("SELECT id FROM users WHERE id = ?", (user_id,))):
        raise HTTPException(404, "User not found")
    if user_id == admin["id"] and (body.role != "admin" or not body.is_active):
        raise HTTPException(400, "You cannot demote or deactivate your own account")
    with transaction(conn):
        conn.execute("UPDATE users SET full_name = ?, role = ?, is_active = ? WHERE id = ?",
                     (body.full_name, body.role, int(body.is_active), user_id))
        if body.password:
            # A reset also clears any lockout and ends the user's open sessions.
            conn.execute("UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
                         (hash_password(body.password), user_id))
        if body.password or not body.is_active:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return one(conn.execute(f"SELECT {FIELDS} FROM users WHERE id = ?", (user_id,)))
