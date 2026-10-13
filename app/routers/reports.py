import calendar
import csv
import io
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Query, Response

from ..db import get_db, rows
from ..security import current_user
from ..validation import parse_month

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(current_user)])

STATUSES = ("present", "late", "half_day", "absent", "on_leave")


def attendance_rate(present: int, late: int, half_day: int, marked: int, on_leave: int) -> float | None:
    """Share of working (non-leave) marked days attended; half days count as 0.5."""
    base = marked - on_leave
    if base <= 0:
        return None
    return round((present + late + 0.5 * half_day) / base * 100, 1)


def month_bounds(month: str) -> tuple[str, str]:
    year, mon = map(int, month.split("-"))
    return f"{month}-01", f"{month}-{calendar.monthrange(year, mon)[1]:02d}"


def build_monthly_report(conn: sqlite3.Connection, month: str, department_id: int | None) -> dict:
    first, last = month_bounds(month)
    params: list = [first, last, last]
    dept_clause = ""
    if department_id:
        dept_clause = " AND e.department_id = ?"
        params.append(department_id)

    sums = ", ".join(f"COALESCE(SUM(a.status = '{s}'), 0) AS {s}" for s in STATUSES)
    items = rows(conn.execute(
        f"""SELECT e.id AS employee_id, e.emp_code, e.first_name || ' ' || e.last_name AS name,
                   d.name AS department_name, e.status AS employee_status, {sums}, COUNT(a.id) AS days_marked
              FROM employees e
              JOIN departments d ON d.id = e.department_id
              LEFT JOIN attendance a ON a.employee_id = e.id AND a.date BETWEEN ? AND ?
             WHERE e.hire_date <= ?{dept_clause}
             GROUP BY e.id
            HAVING e.status = 'active' OR COUNT(a.id) > 0
             ORDER BY d.name, e.first_name, e.last_name""",
        params))

    # Approved leave days that fall inside the month, per employee.
    leave_days: dict[int, int] = {}
    for lv in rows(conn.execute(
            "SELECT employee_id, start_date, end_date FROM leaves "
            "WHERE status = 'approved' AND start_date <= ? AND end_date >= ?", (last, first))):
        start = max(date.fromisoformat(lv["start_date"]), date.fromisoformat(first))
        end = min(date.fromisoformat(lv["end_date"]), date.fromisoformat(last))
        leave_days[lv["employee_id"]] = leave_days.get(lv["employee_id"], 0) + (end - start).days + 1

    totals = {s: 0 for s in STATUSES} | {"days_marked": 0, "approved_leave_days": 0}
    for it in items:
        it["approved_leave_days"] = leave_days.get(it["employee_id"], 0)
        it["attendance_rate"] = attendance_rate(it["present"], it["late"], it["half_day"],
                                                it["days_marked"], it["on_leave"])
        for key in totals:
            totals[key] += it[key]
    totals["attendance_rate"] = attendance_rate(totals["present"], totals["late"], totals["half_day"],
                                                totals["days_marked"], totals["on_leave"])
    return {"month": month, "department_id": department_id, "items": items, "totals": totals}


@router.get("/monthly")
def monthly(month: str | None = None, department_id: int | None = None, conn: sqlite3.Connection = Depends(get_db)):
    return build_monthly_report(conn, parse_month(month), department_id)


def _cell(value) -> str:
    # Neutralise spreadsheet formula injection.
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/monthly.csv")
def monthly_csv(month: str | None = None, department_id: int | None = Query(None),
                conn: sqlite3.Connection = Depends(get_db)):
    report = build_monthly_report(conn, parse_month(month), department_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Employee code", "Name", "Department", "Present", "Late", "Half day", "Absent", "On leave",
                "Days marked", "Approved leave days", "Attendance rate %"])
    for it in report["items"]:
        w.writerow([_cell(it["emp_code"]), _cell(it["name"]), _cell(it["department_name"]), it["present"],
                    it["late"], it["half_day"], it["absent"], it["on_leave"], it["days_marked"],
                    it["approved_leave_days"], "" if it["attendance_rate"] is None else it["attendance_rate"]])
    t = report["totals"]
    w.writerow(["", "TOTAL", "", t["present"], t["late"], t["half_day"], t["absent"], t["on_leave"],
                t["days_marked"], t["approved_leave_days"], "" if t["attendance_rate"] is None else t["attendance_rate"]])
    return Response(
        content="﻿" + buf.getvalue(),  # BOM so Excel detects UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="attendance-{report["month"]}.csv"'},
    )
