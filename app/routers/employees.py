import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..db import get_db, one, rows
from ..security import current_user, require_admin
from ..validation import Email, EmpCode, IsoDate, Name, Phone, ShortText, now_iso

router = APIRouter(prefix="/api/employees", tags=["employees"], dependencies=[Depends(current_user)])

SELECT = """SELECT e.id, e.emp_code, e.first_name, e.last_name, e.email, e.phone, e.department_id,
                   d.name AS department_name, e.designation, e.hire_date, e.status, e.created_at, e.updated_at
              FROM employees e JOIN departments d ON d.id = e.department_id"""


class EmployeeIn(BaseModel):
    emp_code: EmpCode
    first_name: Name
    last_name: Name
    email: Email
    phone: Phone = ""
    department_id: int
    designation: ShortText = ""
    hire_date: IsoDate
    status: Literal["active", "inactive"] = "active"


def _get(conn, emp_id: int) -> dict:
    emp = one(conn.execute(SELECT + " WHERE e.id = ?", (emp_id,)))
    if not emp:
        raise HTTPException(404, "Employee not found")
    return emp


def _check_department(conn, dept_id: int) -> None:
    if not one(conn.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))):
        raise HTTPException(422, "Department does not exist")


def _conflict(exc: sqlite3.IntegrityError) -> HTTPException:
    field = "employee code" if "emp_code" in str(exc) else "email"
    return HTTPException(409, f"Another employee already uses this {field}")


@router.get("")
def list_employees(
    q: str = Query("", max_length=100),
    department_id: int | None = None,
    status: Literal["active", "inactive", ""] = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_db),
):
    where, params = [], []
    if q.strip():
        # Escape LIKE wildcards so user input matches literally.
        term = q.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        like = f"%{term}%"
        cols = ["e.emp_code", "e.first_name", "e.last_name", "e.email", "e.designation",
                "(e.first_name || ' ' || e.last_name)"]
        where.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '!'" for c in cols) + ")")
        params += [like] * 6
    if department_id:
        where.append("e.department_id = ?")
        params.append(department_id)
    if status:
        where.append("e.status = ?")
        params.append(status)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(
        "SELECT COUNT(*) FROM employees e JOIN departments d ON d.id = e.department_id" + clause, params
    ).fetchone()[0]
    items = rows(conn.execute(SELECT + clause + " ORDER BY e.first_name, e.last_name LIMIT ? OFFSET ?",
                              params + [page_size, (page - 1) * page_size]))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{emp_id}")
def get_employee(emp_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _get(conn, emp_id)


@router.post("", status_code=201)
def create_employee(body: EmployeeIn, conn: sqlite3.Connection = Depends(get_db)):
    _check_department(conn, body.department_id)
    try:
        cur = conn.execute(
            """INSERT INTO employees (emp_code, first_name, last_name, email, phone, department_id,
                                      designation, hire_date, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.emp_code, body.first_name, body.last_name, body.email, body.phone, body.department_id,
             body.designation, body.hire_date, body.status))
    except sqlite3.IntegrityError as exc:
        raise _conflict(exc)
    return _get(conn, cur.lastrowid)


@router.put("/{emp_id}")
def update_employee(emp_id: int, body: EmployeeIn, conn: sqlite3.Connection = Depends(get_db)):
    _get(conn, emp_id)
    _check_department(conn, body.department_id)
    try:
        conn.execute(
            """UPDATE employees SET emp_code = ?, first_name = ?, last_name = ?, email = ?, phone = ?,
                      department_id = ?, designation = ?, hire_date = ?, status = ?, updated_at = ?
                WHERE id = ?""",
            (body.emp_code, body.first_name, body.last_name, body.email, body.phone, body.department_id,
             body.designation, body.hire_date, body.status, now_iso(), emp_id))
    except sqlite3.IntegrityError as exc:
        raise _conflict(exc)
    return _get(conn, emp_id)


@router.delete("/{emp_id}", dependencies=[Depends(require_admin)])
def delete_employee(emp_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _get(conn, emp_id)
    conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    return {"ok": True}
