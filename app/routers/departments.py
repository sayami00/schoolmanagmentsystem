import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_db, one, rows
from ..security import current_user, require_admin
from ..validation import DeptCode, LongText, Name, now_iso

router = APIRouter(prefix="/api/departments", tags=["departments"], dependencies=[Depends(current_user)])

SELECT = """SELECT d.id, d.name, d.code, d.description, d.created_at, d.updated_at,
                   (SELECT COUNT(*) FROM employees e WHERE e.department_id = d.id) AS employee_count,
                   (SELECT COUNT(*) FROM employees e WHERE e.department_id = d.id AND e.status = 'active') AS active_count
              FROM departments d"""


class DepartmentIn(BaseModel):
    name: Name
    code: DeptCode
    description: LongText = ""


def _conflict(exc: sqlite3.IntegrityError) -> HTTPException:
    field = "code" if "code" in str(exc) else "name"
    return HTTPException(409, f"A department with this {field} already exists")


def _get(conn, dept_id: int) -> dict:
    dept = one(conn.execute(SELECT + " WHERE d.id = ?", (dept_id,)))
    if not dept:
        raise HTTPException(404, "Department not found")
    return dept


@router.get("")
def list_departments(conn: sqlite3.Connection = Depends(get_db)):
    return rows(conn.execute(SELECT + " ORDER BY d.name"))


@router.get("/{dept_id}")
def get_department(dept_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _get(conn, dept_id)


@router.post("", status_code=201)
def create_department(body: DepartmentIn, conn: sqlite3.Connection = Depends(get_db)):
    try:
        cur = conn.execute("INSERT INTO departments (name, code, description) VALUES (?, ?, ?)",
                           (body.name, body.code, body.description))
    except sqlite3.IntegrityError as exc:
        raise _conflict(exc)
    return _get(conn, cur.lastrowid)


@router.put("/{dept_id}")
def update_department(dept_id: int, body: DepartmentIn, conn: sqlite3.Connection = Depends(get_db)):
    _get(conn, dept_id)
    try:
        conn.execute("UPDATE departments SET name = ?, code = ?, description = ?, updated_at = ? WHERE id = ?",
                     (body.name, body.code, body.description, now_iso(), dept_id))
    except sqlite3.IntegrityError as exc:
        raise _conflict(exc)
    return _get(conn, dept_id)


@router.delete("/{dept_id}", dependencies=[Depends(require_admin)])
def delete_department(dept_id: int, conn: sqlite3.Connection = Depends(get_db)):
    dept = _get(conn, dept_id)
    if dept["employee_count"]:
        raise HTTPException(409, "Department still has employees; move or delete them first")
    conn.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
    return {"ok": True}
