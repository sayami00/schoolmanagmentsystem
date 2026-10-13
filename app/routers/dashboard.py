import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from ..db import get_db, one, rows
from ..security import current_user
from ..validation import parse_date
from .reports import attendance_rate

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(current_user)])

COUNTS = """COUNT(e.id) AS headcount,
            COALESCE(SUM(a.status = 'present'), 0)  AS present,
            COALESCE(SUM(a.status = 'late'), 0)     AS late,
            COALESCE(SUM(a.status = 'half_day'), 0) AS half_day,
            COALESCE(SUM(a.status = 'absent'), 0)   AS absent,
            COALESCE(SUM(a.status = 'on_leave'), 0) AS on_leave,
            COUNT(a.id) AS marked"""


def _with_rate(r: dict) -> dict:
    r["not_marked"] = r["headcount"] - r["marked"]
    r["attendance_rate"] = attendance_rate(r["present"], r["late"], r["half_day"], r["marked"], r["on_leave"])
    return r


@router.get("")
def dashboard(day: str | None = Query(None, alias="date"), conn: sqlite3.Connection = Depends(get_db)):
    day = parse_date(day)
    base = """FROM employees e
              LEFT JOIN attendance a ON a.employee_id = e.id AND a.date = ?
             WHERE e.status = 'active' AND e.hire_date <= ?"""

    summary = _with_rate(one(conn.execute(f"SELECT {COUNTS} {base}", (day, day))))
    summary["pending_leaves"] = conn.execute("SELECT COUNT(*) FROM leaves WHERE status = 'pending'").fetchone()[0]
    summary["departments"] = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]

    departments = [_with_rate(r) for r in rows(conn.execute(
        f"""SELECT d.id, d.name, {COUNTS}
              FROM departments d
              LEFT JOIN employees e ON e.department_id = d.id AND e.status = 'active' AND e.hire_date <= ?
              LEFT JOIN attendance a ON a.employee_id = e.id AND a.date = ?
             GROUP BY d.id ORDER BY d.name""", (day, day)))]

    end = date.fromisoformat(day)
    trend = []
    for offset in range(6, -1, -1):
        d = (end - timedelta(days=offset)).isoformat()
        r = _with_rate(one(conn.execute(f"SELECT {COUNTS} {base}", (d, d))))
        trend.append({"date": d, "attendance_rate": r["attendance_rate"], "marked": r["marked"],
                      "headcount": r["headcount"]})

    recent_leaves = rows(conn.execute(
        """SELECT l.id, e.first_name || ' ' || e.last_name AS employee_name, l.leave_type,
                  l.start_date, l.end_date, l.status
             FROM leaves l JOIN employees e ON e.id = l.employee_id
            ORDER BY l.created_at DESC, l.id DESC LIMIT 6"""))

    return {"date": day, "summary": summary, "departments": departments, "trend": trend,
            "recent_leaves": recent_leaves}
