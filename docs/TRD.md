# TRD — Employee & Attendance Management System (EAMS)

## 1. Architecture
```
Browser (HTML + CSS + vanilla JS, fetch JSON)
        │  same-origin, session cookie
        ▼
FastAPI (uvicorn)
  ├─ page routes  → serve static HTML (session-guarded, redirect to /login)
  ├─ /api/*       → JSON REST, Pydantic validation, role checks
  └─ /static/*    → CSS / JS
        │  sqlite3, parameterised SQL, one connection per request
        ▼
SQLite file (data/eams.db, WAL, foreign_keys=ON)
```
No ORM, no template engine, no build step. Pages are static HTML shells; JS fetches data from the API and renders it, escaping all user text.

### Layout
```
app/
  main.py         app factory, middleware, page routes, startup
  config.py       env-driven settings
  db.py           connection dependency, schema init, transactions
  schema.sql      DDL
  security.py     password hashing, sessions, auth dependencies
  validation.py   shared Pydantic models/validators
  seed.py         sample data (python -m app.seed)
  routers/        auth, users, departments, employees, attendance, leaves, reports, dashboard
static/
  css/style.css
  js/app.js       shared: api(), layout/nav, modal, toast, escape helpers
  js/<page>.js    one per page
  pages/*.html    page shells
tests/test_api.py unittest + FastAPI TestClient
```

## 2. Data Model (SQLite)
| Table | Columns | Constraints |
|-------|---------|-------------|
| users | id, username, full_name, password_hash, role, is_active, failed_attempts, locked_until, created_at | username UNIQUE NOCASE; role ∈ {admin, hr} |
| sessions | token_hash (PK), user_id, expires_at, created_at | FK users ON DELETE CASCADE; only SHA-256 of token stored |
| departments | id, name, code, description, created_at, updated_at | name, code UNIQUE NOCASE |
| employees | id, emp_code, first_name, last_name, email, phone, department_id, designation, hire_date, status, created_at, updated_at | emp_code, email UNIQUE NOCASE; FK departments ON DELETE RESTRICT; status ∈ {active, inactive} |
| attendance | id, employee_id, date, status, check_in, check_out, notes, marked_by, created_at, updated_at | UNIQUE(employee_id, date); FK employees ON DELETE CASCADE; status ∈ {present, late, half_day, absent, on_leave}; CHECK check_out > check_in |
| leaves | id, employee_id, leave_type, start_date, end_date, reason, status, reviewed_by, reviewed_at, created_by, created_at, updated_at | FK employees CASCADE; type ∈ {annual, sick, casual, unpaid, other}; status ∈ {pending, approved, rejected}; CHECK end_date ≥ start_date |

Dates are ISO `YYYY-MM-DD` text, times `HH:MM`, timestamps ISO UTC. Indexes on `attendance(date)`, `leaves(employee_id, start_date, end_date)`, `employees(department_id)`.

## 3. Security
- **Passwords:** PBKDF2-HMAC-SHA256, 600 000 iterations, 16-byte random salt, stored as `pbkdf2_sha256$iter$salt$hash`; compared with `hmac.compare_digest`. Policy: 8–128 chars, at least one letter and one digit.
- **Sessions:** `secrets.token_urlsafe(32)` in cookie `eams_session` (HttpOnly, SameSite=Strict, Secure when `EAMS_COOKIE_SECURE=1`), 8 h TTL; DB stores SHA-256 of token. Logout/password change deletes sessions.
- **Lockout:** 5 failed logins → `locked_until = now + 15 min`.
- **CSRF:** SameSite=Strict cookie + API accepts JSON bodies only (no form posts).
- **SQL:** every query uses `?` placeholders; dynamic sort/filter columns come from fixed whitelists.
- **XSS:** UI renders user text via `textContent` / `esc()`; CSP `default-src 'self'` with no inline script/style.
- **Headers:** CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`.

## 4. API (all JSON; `401` unauthenticated, `403` wrong role, `404` missing, `409` conflict, `422` validation)
| Method & path | Role | Purpose |
|---|---|---|
| POST `/api/auth/login` | public | `{username, password}` → sets cookie, returns user |
| POST `/api/auth/logout` | any | end session |
| GET `/api/auth/me` | any | current user |
| POST `/api/auth/change-password` | any | `{current_password, new_password}` |
| GET / POST `/api/users` | admin | list / create user |
| PUT `/api/users/{id}` | admin | update name, role, active, optional new password |
| GET / POST `/api/departments` | hr+ | list (with employee counts) / create |
| GET / PUT `/api/departments/{id}` | hr+ | read / update |
| DELETE `/api/departments/{id}` | admin | delete (409 if employees) |
| GET `/api/employees?q&department_id&status&page&page_size` | hr+ | paginated search |
| POST `/api/employees` | hr+ | create |
| GET / PUT `/api/employees/{id}` | hr+ | read / update |
| DELETE `/api/employees/{id}` | admin | delete (cascades attendance & leaves) |
| GET `/api/attendance?date&department_id` | hr+ | daily sheet |
| PUT `/api/attendance` | hr+ | bulk upsert `{date, records:[{employee_id,status,check_in,check_out,notes}]}` (atomic) |
| DELETE `/api/attendance/{id}` | hr+ | remove a record |
| GET `/api/attendance/employee/{id}?month` | hr+ | one employee's month |
| GET `/api/leaves?status&employee_id&month` | hr+ | list |
| POST `/api/leaves` | hr+ | create (pending) |
| PUT `/api/leaves/{id}` | hr+ | edit pending leave |
| POST `/api/leaves/{id}/status` | hr+ | `{status: approved\|rejected}` from pending |
| DELETE `/api/leaves/{id}` | hr: pending/rejected; admin: any | delete |
| GET `/api/reports/monthly?month&department_id` | hr+ | report JSON |
| GET `/api/reports/monthly.csv?month&department_id` | hr+ | CSV download |
| GET `/api/dashboard?date` | hr+ | KPIs, 7-day trend, departments, recent leaves |

## 5. Validation Rules
- Strings trimmed; required fields non-empty; lengths capped (names 100, notes 500, etc.).
- Department code: 2–10 chars `[A-Za-z0-9_-]`, stored upper-case.
- Employee code: 2–20 chars `[A-Za-z0-9_-]`; email: basic RFC-shaped regex, stored lower-case; phone: optional, `[0-9+()\- ]{6,20}`.
- Dates must parse as ISO; attendance date ≤ today and ≥ employee hire date; employee must be active.
- Times `HH:MM` 00:00–23:59; check-out requires check-in and must be later; Absent/On leave records cannot carry times.
- Leave: end ≥ start, span ≤ 366 days, no overlap with the employee's pending/approved leaves.
- Report month `YYYY-MM`.
- Errors return FastAPI's standard `{"detail": ...}`; the UI shows the message.

## 6. Report Calculations
- `days_marked` = attendance rows in month.
- `attendance_rate` = (present + late + 0.5 × half_day) ÷ (days_marked − on_leave), shown as %, `—` when divisor is 0.
- `approved_leave_days` = calendar days of approved leaves intersecting the month.
- Dashboard `not_marked` = active employees hired on/before the date with no row for that date.

## 7. Config (env vars)
`EAMS_DB_PATH` (default `data/eams.db`), `EAMS_COOKIE_SECURE` (`0`/`1`), `EAMS_SESSION_HOURS` (8), `EAMS_SEED_ON_EMPTY` (`1`).

## 8. Testing
`python -m unittest` runs API tests against a temp DB: auth + lockout, role enforcement, CRUD conflicts, attendance rules and upsert, leave overlap, report totals, dashboard sum invariant.
