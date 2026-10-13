# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

EAMS (Employee & Attendance Management System): FastAPI + SQLite (stdlib `sqlite3`, raw parameterised SQL, no ORM) backend, with plain HTML/CSS/vanilla JS frontend. No Node, no template engine, no build step. Specs: `docs/PRD.md` (product) and `docs/TRD.md` (data model, full API table, validation rules, report formulas). Check the TRD before changing API behavior.

## Commands

Windows venv lives in `.venv` (use `.venv\Scripts\python` / `.venv/Scripts/python`).

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://127.0.0.1:8000, Swagger at /docs
python -m app.seed                     # WIPES the DB and reseeds sample data
python -m unittest -v                  # all tests
python -m unittest tests.test_api.LeaveTests -v                       # one class
python -m unittest tests.test_api.AuthTests.test_lockout_after_five_failures   # one test
```

Seed logins: `admin` / `Admin@123` (admin), `hr` / `Hr@12345` (hr). There is no linter or formatter configured.

## Architecture

- **`app/main.py`**: Registers routers, adds the security-header middleware (strict CSP, so no inline script or style anywhere in pages; CSP is dropped only for `/docs` and `/redoc`), and mounts `/static`. HTML pages are served from the `PAGES` dict: each entry maps a path to a static shell plus an admin-only flag, and the handler redirects to `/login` when no session exists. A new page needs an entry in `PAGES`, an HTML shell in `static/pages/`, a script in `static/js/<page>.js`, and a `NAV` entry in `static/js/app.js`.
- **Startup (lifespan)**: Runs `schema.sql` (idempotent `CREATE ... IF NOT EXISTS`) and seeds sample data when the `users` table is empty and `EAMS_SEED_ON_EMPTY=1`. Schema changes go in `app/schema.sql`. There is no migration tool.
- **DB access (`app/db.py`)**: Each request gets its own connection through the `get_db` dependency. Connections run in autocommit mode (`isolation_level=None`), so wrap any multi-statement write in `with transaction(conn):` (`BEGIN IMMEDIATE`). Use the `rows()`/`one()` helpers to turn cursors into dicts. `config.db_path()` reads `EAMS_DB_PATH` on every call, and tests depend on that.
- **Auth (`app/security.py`)**: Uses server-side sessions. The cookie `eams_session` holds a random token, and the DB stores only its SHA-256. Routes guard access with the `Depends(current_user)` and `Depends(require_admin)` dependencies. Roles are enforced in the API, not only in the UI. Roles are `admin` (a superset of HR) and `hr`.
- **Routers (`app/routers/*.py`)**: Each router uses the prefix `/api/<resource>` and has Pydantic request models built from the shared annotated types in `app/validation.py` (`IsoDate`, `LongText`, code/email/phone validators, `parse_month`). Uniqueness violations are caught as `sqlite3.IntegrityError` and turned into `409`. Status codes follow the convention 401 unauthenticated, 403 wrong role, 404 missing, 409 conflict, 422 validation.
- **Frontend**: `static/js/app.js` provides shared helpers: `api()` (fetch wrapper that throws `ApiError` and redirects on 401), layout/nav, modals, toasts, and `esc()`. Page scripts render with `esc()` or `textContent`. Never interpolate unescaped user data into HTML.

## Conventions and invariants

- SQL always uses `?` placeholders. Dynamic sort and filter columns must come from fixed whitelists. Escape `LIKE` wildcards in search input.
- Dates are ISO `YYYY-MM-DD` text, times are `HH:MM`, and timestamps are ISO UTC (`security.iso()`). "Today" means the server's local date.
- Attendance has one row per `(employee_id, date)`. `PUT /api/attendance` is an atomic bulk upsert. Attendance requires an active employee, a date no later than today and no earlier than the hire date, and no times on absent or on-leave rows.
- Leave starts as `pending` and moves to `approved` or `rejected`. Only pending leave can be edited, and overlap with pending or approved leave is blocked.
- Report `attendance_rate` = (present + late + 0.5·half_day) / (days_marked − on_leave). CSV export must neutralise formula injection.

## Tests

`tests/test_api.py` uses `unittest` with FastAPI `TestClient`. At import time it sets `EAMS_DB_PATH` to a temp dir and lowers `config.PBKDF2_ITERATIONS` before importing `app.main`, so the env setup must stay above the app import. Tests share one seeded DB across classes. Use `new_department`/`new_employee` with unique codes rather than assuming a clean state.
