# Employee & Attendance Management System (EAMS)

A small, self-contained web app for Admin and HR staff to manage employees and departments, mark daily attendance, record leave, and produce monthly attendance reports.

**Stack:** Python 3.10+, FastAPI, SQLite through the standard `sqlite3` module (direct, parameterised SQL with no ORM), and plain HTML, CSS and vanilla JavaScript. There is no Node.js, React, Vue or build step.

Product and technical specs live in [`docs/PRD.md`](docs/PRD.md) and [`docs/TRD.md`](docs/TRD.md).

## Quick start

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. On first start the database (`data/eams.db`) is created and filled with sample data.

| Username | Password | Role |
|----------|----------|------|
| `admin` | `Admin@123` | Admin |
| `hr` | `Hr@12345` | HR |

> Change these passwords (Account page, or System users as admin) before using the app with real data.

To reset the database to fresh sample data at any time (this **deletes all data**):

```bash
python -m app.seed
```

## Features

- **Login and roles.** Server-side sessions use HttpOnly, SameSite=Strict cookies and expire after 8 hours. An account locks for 15 minutes after 5 failed logins. Admins can do everything HR can, and can also manage system users and delete employees, departments and approved leave.
- **Departments.** Create, edit and delete. A department that still has employees cannot be deleted.
- **Employees.** Create, edit, search, filter, page through results, deactivate and delete. Employee codes and emails must be unique.
- **Daily attendance.** One sheet per day, optionally filtered by department. Statuses are Present, Late, Half day, Absent and On leave, with optional check-in/out times and notes. "Mark unmarked as present" fills empty rows. Employees on approved leave are pre-filled as On leave. Saving is a bulk, atomic upsert that keeps one record per employee per day.
- **Leave records.** Leave is recorded as pending, then approved or rejected. Overlapping leave is blocked, and only pending leave can be edited.
- **Monthly report.** Per-employee counts, approved leave days and attendance rate, with totals and CSV export.
- **Dashboard.** Shows the day's KPIs, a 7-day attendance-rate trend, a per-department rate and breakdown, and recent leave.
- **Responsive UI.** Works down to phone width: the sidebar becomes a drawer and tables stack into cards. Supports light and dark mode.

## Security notes

- Passwords are hashed with PBKDF2-HMAC-SHA256 (600k iterations, per-user salt) and compared in constant time. Hashes are never returned by the API.
- Session tokens are random 256-bit values. Only their SHA-256 hash is stored.
- Every SQL statement uses `?` placeholders, and search input has its `LIKE` wildcards escaped.
- Every API route checks the session and role, not just the UI.
- The UI escapes all user data. A strict Content-Security-Policy is set (no inline script or style), along with `X-Frame-Options: DENY` and `nosniff`.
- CSV export neutralises spreadsheet formula injection.
- When serving over HTTPS, set `EAMS_COOKIE_SECURE=1`.

## Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `EAMS_DB_PATH` | `data/eams.db` | SQLite file location |
| `EAMS_COOKIE_SECURE` | `0` | Set `1` behind HTTPS |
| `EAMS_SESSION_HOURS` | `8` | Session lifetime |
| `EAMS_SEED_ON_EMPTY` | `1` | Seed sample data when the DB has no users |

## Tests

```bash
python -m unittest -v
```

The tests run against a temporary database and cover authentication and lockout, role enforcement, uniqueness conflicts, attendance rules and upsert, leave overlap and review, report and CSV totals, and dashboard invariants.

## Project layout

```
app/
  main.py          FastAPI app, security headers, page routes, startup
  config.py        settings
  db.py            sqlite3 connection, transactions, schema init
  schema.sql       tables, constraints, indexes
  security.py      password hashing, sessions, auth dependencies
  validation.py    shared field validators
  seed.py          sample data
  routers/         auth, users, departments, employees, attendance, leaves, reports, dashboard
static/
  pages/*.html     page shells
  js/app.js        shared helpers (API, layout, dialogs, toasts)
  js/<page>.js     page logic
  css/style.css
tests/test_api.py
docs/PRD.md, docs/TRD.md
```

API docs are generated automatically at `/docs` (Swagger UI) while the server is running.

## Known MVP limits

- Employees cannot log in themselves.
- There is no holiday calendar or leave balance tracking.
- Approved leave days are counted as calendar days.
- "Today" means the server's local date.
