import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from ..db import get_db, one, rows, transaction
from ..security import current_user
from ..validation import IsoDate, LongText, Time, now_iso, parse_date, parse_month

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

Status = Literal["present", "late", "half_day", "absent", "on_leave"]


class AttendanceRecord(BaseModel):
    employee_id: int
    status: Status
    check_in: Time = None
    check_out: Time = None
    notes: LongText = ""

    @model_validator(mode="after")
    def _times(self):
        if self.status in ("absent", "on_leave") and (self.check_in or self.check_out):
            raise ValueError("Absent / On leave records cannot have check-in or check-out times")
        if self.check_out and not self.check_in:
            raise ValueError("Check-out requires a check-in time")
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValueError("Check-out must be later than check-in")
        return self


class AttendanceSheetIn(BaseModel):
    date: IsoDate
    records: list[AttendanceRecord] = Field(min_length=1, max_length=2000)


@router.get("")
def get_daily_sheet(
    day: str | None = Query(None, alias="date"),  # aliased so it does not shadow datetime.date
    department_id: int | None = None,
    _: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    day = parse_date(day)
    params: list = [day, day, day, day]
    dept_clause = ""
    if department_id:
        dept_clause = " AND e.department_id = ?"
        params.append(department_id)
    items = rows(conn.execute(
        f"""SELECT e.id AS employee_id, e.emp_code, e.first_name || ' ' || e.last_name AS name,
                   e.designation, d.name AS department_name,
                   a.id AS record_id, a.status, a.check_in, a.check_out, a.notes,
                   (SELECT l.leave_type FROM leaves l
                     WHERE l.employee_id = e.id AND l.status = 'approved'
                       AND l.start_date <= ? AND l.end_date >= ? LIMIT 1) AS leave_type
              FROM employees e
              JOIN departments d ON d.id = e.department_id
              LEFT JOIN attendance a ON a.employee_id = e.id AND a.date = ?
             WHERE e.status = 'active' AND e.hire_date <= ?{dept_clause}
             ORDER BY d.name, e.first_name, e.last_name""",
        params))
    return {"date": day, "editable": day <= date.today().isoformat(), "items": items}


@router.put("")
def save_sheet(body: AttendanceSheetIn, user: dict = Depends(current_user),
               conn: sqlite3.Connection = Depends(get_db)):
    if body.date > date.today().isoformat():
        raise HTTPException(422, "Attendance cannot be recorded for a future date")
    ids = [r.employee_id for r in body.records]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Each employee may appear only once per sheet")

    placeholders = ",".join("?" * len(ids))
    employees = {r["id"]: r for r in rows(conn.execute(
        f"SELECT id, first_name || ' ' || last_name AS name, status, hire_date FROM employees WHERE id IN ({placeholders})",
        ids))}
    for emp_id in ids:
        emp = employees.get(emp_id)
        if not emp:
            raise HTTPException(422, f"Employee #{emp_id} does not exist")
        if emp["status"] != "active":
            raise HTTPException(422, f"{emp['name']} is inactive; attendance cannot be recorded")
        if emp["hire_date"] > body.date:
            raise HTTPException(422, f"{emp['name']} was hired on {emp['hire_date']}, after {body.date}")

    stamp = now_iso()
    with transaction(conn):
        for r in body.records:
            conn.execute(
                """INSERT INTO attendance (employee_id, date, status, check_in, check_out, notes, marked_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (employee_id, date) DO UPDATE SET
                       status = excluded.status, check_in = excluded.check_in, check_out = excluded.check_out,
                       notes = excluded.notes, marked_by = excluded.marked_by, updated_at = ?""",
                (r.employee_id, body.date, r.status, r.check_in, r.check_out, r.notes, user["id"], stamp))
    return {"ok": True, "saved": len(body.records)}


@router.delete("/{record_id}")
def delete_record(record_id: int, _: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    if not one(conn.execute("SELECT id FROM attendance WHERE id = ?", (record_id,))):
        raise HTTPException(404, "Attendance record not found")
    conn.execute("DELETE FROM attendance WHERE id = ?", (record_id,))
    return {"ok": True}


@router.get("/employee/{emp_id}")
def employee_month(emp_id: int, month: str | None = None, _: dict = Depends(current_user),
                   conn: sqlite3.Connection = Depends(get_db)):
    month = parse_month(month)
    emp = one(conn.execute(
        "SELECT id, emp_code, first_name || ' ' || last_name AS name FROM employees WHERE id = ?", (emp_id,)))
    if not emp:
        raise HTTPException(404, "Employee not found")
    records = rows(conn.execute(
        "SELECT id, date, status, check_in, check_out, notes FROM attendance "
        "WHERE employee_id = ? AND substr(date, 1, 7) = ? ORDER BY date", (emp_id, month)))
    return {"employee": emp, "month": month, "records": records}
