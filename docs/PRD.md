# PRD — Employee & Attendance Management System (EAMS)

## 1. Problem & Goal
Small and mid-size organisations track employees, attendance and leave in spreadsheets. Data drifts, duplicates appear, and monthly reporting takes hours. EAMS gives Admin and HR staff one secure web app to keep the employee register, mark daily attendance, record leave and produce monthly reports.

**MVP success:** an HR user can mark attendance for every active employee in under 2 minutes per day and export a month's report in one click.

## 2. Users & Roles
| Role | Who | Permissions |
|------|-----|-------------|
| Admin | Owner / IT | Everything HR can do, plus: manage system users (Admin/HR accounts), delete employees and departments, delete any leave record |
| HR | HR officer | Manage employees and departments (create/edit), mark attendance, record and review leave, view dashboard and reports |

Employees do **not** log in in the MVP (out of scope; see §7).

## 3. Core Workflows
1. **Login** — User enters username + password. Five consecutive failures lock the account for 15 minutes. Successful login creates an 8-hour session (HttpOnly cookie). Logout ends the session server-side.
2. **Department management** — Create, edit, list departments (name, code, description). A department that still has employees cannot be deleted.
3. **Employee management** — Create, edit, search, filter (department, status), deactivate, delete (Admin). Employee code and email are unique. Inactive employees disappear from the daily attendance sheet but keep their history.
4. **Daily attendance** — HR picks a date (today by default, never future) and optionally a department. The sheet lists every active employee hired on or before that date with any saved record. Employees on approved leave are pre-filled as *On leave*. HR sets status (Present, Late, Half day, Absent, On leave), optional check-in/out times and notes, then saves the whole sheet in one action. "Mark all present" speeds up the common case. Re-saving overwrites (one record per employee per day).
5. **Leave records** — HR records a leave request (employee, type, start, end, reason). It starts *Pending*. HR/Admin approve or reject it. Only pending leaves can be edited. Overlapping pending/approved leaves for the same employee are rejected.
6. **Monthly report** — Pick month (+ optional department). Per employee: Present, Late, Half day, Absent, On leave, days marked, approved leave days, attendance rate. Export as CSV.
7. **Dashboard** — For a chosen day (default today): headcount, present, late, absent, on leave, not yet marked, pending leave requests; 7-day attendance-rate trend; per-department rate; recent leave requests.
8. **User management (Admin)** — Create HR/Admin users, reset passwords, activate/deactivate. An admin cannot deactivate or demote themself. Every user can change their own password.

## 4. Pages
| Path | Page | Roles |
|------|------|-------|
| `/login` | Login | public |
| `/` | Dashboard | Admin, HR |
| `/employees` | Employee list + add/edit modal | Admin, HR |
| `/departments` | Department list + add/edit modal | Admin, HR |
| `/attendance` | Daily attendance sheet | Admin, HR |
| `/leaves` | Leave records + add/edit modal, approve/reject | Admin, HR |
| `/reports` | Monthly report + CSV export | Admin, HR |
| `/users` | System users | Admin |
| `/account` | Change own password | Admin, HR |

## 5. Non-functional Requirements
- Responsive: usable from 360 px phone width to desktop.
- Security: salted PBKDF2 password hashes, parameterised SQL only, server-side sessions, role checks on every API route, output escaping in the UI, security headers (CSP, no framing).
- Zero-config start: SQLite file, sample data seeded on first run.
- Stack constraint: Python, FastAPI, SQLite via `sqlite3` (no ORM), HTML/CSS/vanilla JS. No Node, React or Vue.

## 6. Acceptance Criteria
- **AC1** Wrong password returns a generic error; the 5th consecutive failure locks the account for 15 minutes.
- **AC2** Any API call without a valid session returns 401; any page redirects to `/login`.
- **AC3** HR receives 403 on `/api/users*` and on employee/department delete.
- **AC4** Duplicate department name/code or employee code/email returns 409 with a readable message.
- **AC5** Deleting a department that has employees returns 409.
- **AC6** Attendance for a future date, a date before hire date, or an inactive employee returns 422.
- **AC7** Saving attendance twice for the same employee/date updates the single existing record.
- **AC8** Check-out earlier than check-in, or times on an Absent/On-leave record, returns 422.
- **AC9** Leave with end < start, or overlapping an existing pending/approved leave, returns 422/409.
- **AC10** Monthly report counts match the stored attendance rows; CSV contains the same rows.
- **AC11** Dashboard numbers for a day add up: present + late + half day + absent + on leave + not marked = active headcount.
- **AC12** All pages render without horizontal scroll at 360 px width.
- **AC13** Passwords are never stored or returned in plain text.

## 7. Out of Scope (MVP)
Employee self-service login, payroll, shift scheduling, holiday calendars, leave balances/accrual, biometric/device integration, email notifications, multi-tenant.
