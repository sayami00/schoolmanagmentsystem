import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from ..db import get_db, one, rows
from ..security import current_user
from ..validation import IsoDate, LongText, now_iso, parse_month

router = APIRouter(prefix="/api/leaves", tags=["leaves"])

LeaveType = Literal["annual", "sick", "casual", "unpaid", "other"]

SELECT = """SELECT l.id, l.employee_id, e.emp_code, e.first_name || ' ' || e.last_name AS employee_name,
                   d.name AS department_name, l.leave_type, l.start_date, l.end_date,
                   CAST(julianday(l.end_date) - julianday(l.start_date) + 1 AS INTEGER) AS days,
                   l.reason, l.status, l.reviewed_at, r.full_name AS reviewed_by_name,
                   l.created_at, c.full_name AS created_by_name
              FROM leaves l
              JOIN employees e ON e.id = l.employee_id
              JOIN departments d ON d.id = e.department_id
              LEFT JOIN users r ON r.id = l.reviewed_by
              LEFT JOIN users c ON c.id = l.created_by"""


class LeaveIn(BaseModel):
    employee_id: int
    leave_type: LeaveType
    start_date: IsoDate
    end_date: IsoDate
    reason: LongText = ""

    @model_validator(mode="after")
    def _range(self):
        if self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        if (date.fromisoformat(self.end_date) - date.fromisoformat(self.start_date)).days > 365:
            raise ValueError("A single leave cannot span more than 366 days")
        return self


class StatusIn(BaseModel):
    status: Literal["approved", "rejected"]


def _get(conn, leave_id: int) -> dict:
    leave = one(conn.execute(SELECT + " WHERE l.id = ?", (leave_id,)))
    if not leave:
        raise HTTPException(404, "Leave record not found")
    return leave


def _validate(conn, body: LeaveIn, exclude_id: int | None = None) -> None:
    emp = one(conn.execute("SELECT id, status FROM employees WHERE id = ?", (body.employee_id,)))
    if not emp:
        raise HTTPException(422, "Employee does not exist")
    if emp["status"] != "active":
        raise HTTPException(422, "Leave can only be recorded for active employees")
    overlap = one(conn.execute(
        """SELECT start_date, end_date, status FROM leaves
            WHERE employee_id = ? AND status IN ('pending', 'approved') AND id != ?
              AND start_date <= ? AND end_date >= ? LIMIT 1""",
        (body.employee_id, exclude_id or 0, body.end_date, body.start_date)))
    if overlap:
        raise HTTPException(409, f"Overlaps an existing {overlap['status']} leave "
                                 f"({overlap['start_date']} to {overlap['end_date']})")


@router.get("")
def list_leaves(status: Literal["pending", "approved", "rejected", ""] = "",
                employee_id: int | None = None, month: str | None = None,
                _: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    where, params = [], []
    if status:
        where.append("l.status = ?")
        params.append(status)
    if employee_id:
        where.append("l.employee_id = ?")
        params.append(employee_id)
    if month:
        month = parse_month(month)
        where.append("l.start_date <= ? AND l.end_date >= ?")
        params += [f"{month}-31", f"{month}-01"]
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return rows(conn.execute(SELECT + clause + " ORDER BY l.start_date DESC, l.id DESC LIMIT 500", params))


@router.post("", status_code=201)
def create_leave(body: LeaveIn, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    _validate(conn, body)
    cur = conn.execute(
        "INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, created_by) VALUES (?, ?, ?, ?, ?, ?)",
        (body.employee_id, body.leave_type, body.start_date, body.end_date, body.reason, user["id"]))
    return _get(conn, cur.lastrowid)


@router.put("/{leave_id}")
def update_leave(leave_id: int, body: LeaveIn, _: dict = Depends(current_user),
                 conn: sqlite3.Connection = Depends(get_db)):
    if _get(conn, leave_id)["status"] != "pending":
        raise HTTPException(409, "Only pending leave records can be edited")
    _validate(conn, body, exclude_id=leave_id)
    conn.execute(
        """UPDATE leaves SET employee_id = ?, leave_type = ?, start_date = ?, end_date = ?, reason = ?, updated_at = ?
            WHERE id = ?""",
        (body.employee_id, body.leave_type, body.start_date, body.end_date, body.reason, now_iso(), leave_id))
    return _get(conn, leave_id)


@router.post("/{leave_id}/status")
def set_status(leave_id: int, body: StatusIn, user: dict = Depends(current_user),
               conn: sqlite3.Connection = Depends(get_db)):
    if _get(conn, leave_id)["status"] != "pending":
        raise HTTPException(409, "Leave has already been reviewed")
    stamp = now_iso()
    conn.execute("UPDATE leaves SET status = ?, reviewed_by = ?, reviewed_at = ?, updated_at = ? WHERE id = ?",
                 (body.status, user["id"], stamp, stamp, leave_id))
    return _get(conn, leave_id)


@router.delete("/{leave_id}")
def delete_leave(leave_id: int, user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    leave = _get(conn, leave_id)
    if leave["status"] == "approved" and user["role"] != "admin":
        raise HTTPException(403, "Only an admin can delete an approved leave")
    conn.execute("DELETE FROM leaves WHERE id = ?", (leave_id,))
    return {"ok": True}
