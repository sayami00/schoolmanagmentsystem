"""Sample data. Run `python -m app.seed` to (re)create the database with demo records.

WARNING: this deletes all existing data in the configured database.
"""
import random
from datetime import date, timedelta

from .db import connect, init_schema, transaction
from .security import hash_password

DEPARTMENTS = [
    ("Engineering", "ENG", "Product development and IT operations"),
    ("Human Resources", "HR", "People operations, hiring and payroll"),
    ("Finance", "FIN", "Accounting, budgeting and audit"),
    ("Sales & Marketing", "SALES", "Revenue, partnerships and brand"),
    ("Customer Support", "SUP", "Customer success and helpdesk"),
]

EMPLOYEES = [
    # first, last, dept code, designation
    ("Aarav", "Shrestha", "ENG", "Engineering Manager"),
    ("Sita", "Gurung", "ENG", "Senior Developer"),
    ("Rohan", "Karki", "ENG", "Backend Developer"),
    ("Priya", "Thapa", "ENG", "Frontend Developer"),
    ("Daniel", "Okafor", "ENG", "QA Engineer"),
    ("Mei", "Lin", "ENG", "DevOps Engineer"),
    ("Anita", "Rai", "HR", "HR Manager"),
    ("Kiran", "Magar", "HR", "Recruiter"),
    ("Laura", "Bennett", "FIN", "Finance Manager"),
    ("Suresh", "Adhikari", "FIN", "Accountant"),
    ("Nisha", "Joshi", "FIN", "Payroll Officer"),
    ("Carlos", "Mendes", "SALES", "Sales Lead"),
    ("Bikash", "Tamang", "SALES", "Account Executive"),
    ("Emma", "Wright", "SALES", "Marketing Specialist"),
    ("Rajesh", "Poudel", "SALES", "Business Analyst"),
    ("Fatima", "Khan", "SUP", "Support Lead"),
    ("Hari", "Bhandari", "SUP", "Support Agent"),
    ("Grace", "Kim", "SUP", "Support Agent"),
    ("Manish", "Lama", "SUP", "Support Agent"),
    ("Olivia", "Brown", "ENG", "UI/UX Designer"),
]

USERS = [
    ("admin", "System Administrator", "admin", "Admin@123"),
    ("hr", "Anita Rai (HR)", "hr", "Hr@12345"),
]

HISTORY_DAYS = 60


def seed(reset: bool = False) -> None:
    rng = random.Random(42)
    today = date.today()
    conn = connect()
    try:
        init_schema(conn)
        with transaction(conn):
            if reset:
                for table in ("sessions", "attendance", "leaves", "employees", "departments", "users"):
                    conn.execute(f"DELETE FROM {table}")
                conn.execute("DELETE FROM sqlite_sequence")

            for username, name, role, pwd in USERS:
                conn.execute("INSERT INTO users (username, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
                             (username, name, role, hash_password(pwd)))
            admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]

            dept_ids = {}
            for name, code, desc in DEPARTMENTS:
                cur = conn.execute("INSERT INTO departments (name, code, description) VALUES (?, ?, ?)",
                                   (name, code, desc))
                dept_ids[code] = cur.lastrowid

            emp_ids = []
            for i, (first, last, dept, title) in enumerate(EMPLOYEES, start=1):
                hire = today - timedelta(days=rng.randint(120, 1500))
                if i == 20:  # one recent joiner to show hire-date handling
                    hire = today - timedelta(days=20)
                status = "inactive" if i == 15 else "active"
                cur = conn.execute(
                    """INSERT INTO employees (emp_code, first_name, last_name, email, phone, department_id,
                                              designation, hire_date, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"EMP{i:03d}", first, last, f"{first}.{last}@example.com".lower(),
                     f"+977 98{rng.randint(10000000, 99999999)}", dept_ids[dept], title, hire.isoformat(), status))
                emp_ids.append((cur.lastrowid, hire, status))

            # Leaves: a few approved in the past, one current, some pending/rejected.
            leave_plan = [
                (0, "annual", -25, -23, "approved", "Family function"),
                (3, "sick", -12, -11, "approved", "Fever"),
                (8, "casual", -5, -5, "approved", "Personal errand"),
                (11, "annual", -1, 2, "approved", "Vacation"),
                (16, "sick", 0, 0, "approved", "Medical appointment"),
                (5, "annual", 7, 11, "pending", "Trip abroad"),
                (12, "casual", 3, 3, "pending", "Bank work"),
                (17, "unpaid", 14, 18, "pending", "Personal reasons"),
                (9, "other", -40, -39, "rejected", "Overlaps quarter close"),
            ]
            approved: dict[int, set[date]] = {}
            for idx, ltype, s, e, status, reason in leave_plan:
                emp_id = emp_ids[idx][0]
                start, end = today + timedelta(days=s), today + timedelta(days=e)
                conn.execute(
                    """INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, status,
                                           reviewed_by, reviewed_at, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (emp_id, ltype, start.isoformat(), end.isoformat(), reason, status,
                     admin_id if status != "pending" else None,
                     (start - timedelta(days=3)).isoformat() + "T09:00:00Z" if status != "pending" else None,
                     admin_id))
                if status == "approved":
                    approved.setdefault(emp_id, set()).update(start + timedelta(days=n) for n in range((end - start).days + 1))

            # Attendance for weekdays over the last HISTORY_DAYS. Today is only partly marked
            # (whatever the weekday) so the dashboard shows both marked and pending staff.
            for back in range(HISTORY_DAYS, -1, -1):
                day = today - timedelta(days=back)
                if day.weekday() >= 5 and back:
                    continue
                for emp_id, hire, status in emp_ids:
                    if hire > day or (status == "inactive" and back < 30):
                        continue
                    if back == 0 and rng.random() < 0.3:
                        continue
                    if day in approved.get(emp_id, ()):
                        conn.execute("INSERT INTO attendance (employee_id, date, status, marked_by) VALUES (?, ?, 'on_leave', ?)",
                                     (emp_id, day.isoformat(), admin_id))
                        continue
                    roll = rng.random()
                    if roll < 0.78:
                        st, cin, cout = "present", f"0{rng.randint(8, 9)}:{rng.choice(['00', '05', '10', '15', '20'])}", f"{rng.randint(17, 18)}:{rng.choice(['00', '15', '30'])}"
                    elif roll < 0.88:
                        st, cin, cout = "late", f"10:{rng.randint(0, 5)}{rng.randint(0, 9)}", "18:30"
                    elif roll < 0.93:
                        st, cin, cout = "half_day", "09:00", "13:00"
                    else:
                        st, cin, cout = "absent", None, None
                    conn.execute(
                        "INSERT INTO attendance (employee_id, date, status, check_in, check_out, marked_by) VALUES (?, ?, ?, ?, ?, ?)",
                        (emp_id, day.isoformat(), st, cin, cout, admin_id))
    finally:
        conn.close()


if __name__ == "__main__":
    seed(reset=True)
    print("Database seeded. Logins: admin / Admin@123 (Admin), hr / Hr@12345 (HR)")
