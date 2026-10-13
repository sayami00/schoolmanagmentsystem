"""API tests covering the PRD acceptance criteria. Run: python -m unittest -v"""
import os
import tempfile
import unittest
from datetime import date, timedelta

_tmp = tempfile.TemporaryDirectory()
os.environ["EAMS_DB_PATH"] = os.path.join(_tmp.name, "test.db")
os.environ["EAMS_SEED_ON_EMPTY"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402

config.PBKDF2_ITERATIONS = 1_000  # keep the suite fast; production uses 600k

from app.main import app  # noqa: E402

TODAY = date.today().isoformat()


class ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(app)
        cls._client_cm.__enter__()  # runs startup: schema + seed

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)

    def client(self, username=None, password=None):
        c = TestClient(app)
        if username:
            r = c.post("/api/auth/login", json={"username": username, "password": password})
            self.assertEqual(r.status_code, 200, r.text)
        return c

    def admin(self):
        return self.client("admin", "Admin@123")

    def hr(self):
        return self.client("hr", "Hr@12345")

    def new_department(self, c, code):
        r = c.post("/api/departments", json={"name": f"Dept {code}", "code": code})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def new_employee(self, c, code, dept_id, hire_date="2020-01-01", status="active"):
        r = c.post("/api/employees", json={
            "emp_code": code, "first_name": "Test", "last_name": code, "email": f"{code}@example.com",
            "department_id": dept_id, "hire_date": hire_date, "status": status})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]


class AuthTests(ApiTestCase):
    def test_unauthenticated_api_and_pages(self):
        c = self.client()
        self.assertEqual(c.get("/api/employees").status_code, 401)
        r = c.get("/employees", follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/login")

    def test_login_logout_and_headers(self):
        c = self.admin()
        r = c.get("/api/auth/me")
        self.assertEqual(r.json()["role"], "admin")
        self.assertIn("default-src 'self'", r.headers["content-security-policy"])
        self.assertEqual(c.post("/api/auth/logout").status_code, 200)
        self.assertEqual(c.get("/api/auth/me").status_code, 401)

    def test_lockout_after_five_failures(self):
        a = self.admin()
        a.post("/api/users", json={"username": "locktest", "full_name": "Lock Test", "role": "hr", "password": "Secret123"})
        c = self.client()
        codes = [c.post("/api/auth/login", json={"username": "locktest", "password": "wrong-pass1"}).status_code
                 for _ in range(5)]
        self.assertEqual(codes, [401, 401, 401, 401, 423])
        # Even the right password is refused while locked.
        r = c.post("/api/auth/login", json={"username": "locktest", "password": "Secret123"})
        self.assertEqual(r.status_code, 423)

    def test_unknown_user_generic_error(self):
        r = self.client().post("/api/auth/login", json={"username": "nobody", "password": "x"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["detail"], "Invalid username or password")

    def test_password_hash_not_plaintext_or_exposed(self):
        a = self.admin()
        users = a.get("/api/users").json()
        self.assertTrue(all("password_hash" not in u for u in users))
        from app.db import connect
        conn = connect()
        stored = conn.execute("SELECT password_hash FROM users WHERE username = 'admin'").fetchone()[0]
        conn.close()
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertNotIn("Admin@123", stored)

    def test_weak_password_rejected(self):
        r = self.admin().post("/api/users", json={"username": "weak", "full_name": "W", "role": "hr", "password": "abcdefgh"})
        self.assertEqual(r.status_code, 422)


class RoleTests(ApiTestCase):
    def test_hr_restrictions(self):
        hr, admin = self.hr(), self.admin()
        self.assertEqual(hr.get("/api/users").status_code, 403)
        self.assertEqual(hr.get("/users", follow_redirects=False).status_code, 303)
        dept = self.new_department(admin, "ROLE1")
        emp = self.new_employee(admin, "ROLE-E1", dept)
        self.assertEqual(hr.delete(f"/api/employees/{emp}").status_code, 403)
        self.assertEqual(admin.delete(f"/api/employees/{emp}").status_code, 200)
        self.assertEqual(hr.delete(f"/api/departments/{dept}").status_code, 403)

    def test_admin_cannot_demote_self(self):
        a = self.admin()
        me = a.get("/api/auth/me").json()
        r = a.put(f"/api/users/{me['id']}", json={"full_name": "X", "role": "hr", "is_active": True})
        self.assertEqual(r.status_code, 400)


class CrudTests(ApiTestCase):
    def test_department_conflicts_and_delete_guard(self):
        a = self.admin()
        dept = self.new_department(a, "DUP1")
        r = a.post("/api/departments", json={"name": "dept dup1", "code": "OTHER"})
        self.assertEqual(r.status_code, 409)
        r = a.post("/api/departments", json={"name": "Unique name", "code": "dup1"})
        self.assertEqual(r.status_code, 409)
        self.new_employee(a, "DUP-E1", dept)
        self.assertEqual(a.delete(f"/api/departments/{dept}").status_code, 409)

    def test_employee_conflicts_and_validation(self):
        a = self.admin()
        dept = self.new_department(a, "EMPV")
        self.new_employee(a, "EV-1", dept)
        r = a.post("/api/employees", json={"emp_code": "ev-1", "first_name": "A", "last_name": "B",
                                           "email": "other@example.com", "department_id": dept, "hire_date": "2021-01-01"})
        self.assertEqual(r.status_code, 409)
        r = a.post("/api/employees", json={"emp_code": "EV-2", "first_name": "A", "last_name": "B",
                                           "email": "not-an-email", "department_id": dept, "hire_date": "2021-01-01"})
        self.assertEqual(r.status_code, 422)

    def test_employee_search_treats_wildcards_literally(self):
        r = self.admin().get("/api/employees", params={"q": "%"})
        self.assertEqual(r.json()["total"], 0)

    def test_sql_injection_is_inert(self):
        r = self.admin().get("/api/employees", params={"q": "' OR 1=1 --"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total"], 0)


class AttendanceTests(ApiTestCase):
    def setUp(self):
        self.a = self.admin()
        self.dept = self.new_department(self.a, f"AT{self.id()[-4:].upper().replace('_', '')}")

    def test_rules(self):
        emp = self.new_employee(self.a, f"AT-{self.dept}", self.dept, hire_date="2024-06-01")
        future = (date.today() + timedelta(days=1)).isoformat()
        bad = [
            {"date": future, "records": [{"employee_id": emp, "status": "present"}]},
            {"date": "2024-05-01", "records": [{"employee_id": emp, "status": "present"}]},
            {"date": TODAY, "records": [{"employee_id": emp, "status": "present", "check_in": "10:00", "check_out": "09:00"}]},
            {"date": TODAY, "records": [{"employee_id": emp, "status": "absent", "check_in": "09:00"}]},
            {"date": TODAY, "records": [{"employee_id": emp, "status": "present", "check_in": "25:00"}]},
        ]
        for body in bad:
            self.assertEqual(self.a.put("/api/attendance", json=body).status_code, 422, body)

    def test_inactive_employee_rejected(self):
        emp = self.new_employee(self.a, f"IN-{self.dept}", self.dept, status="inactive")
        r = self.a.put("/api/attendance", json={"date": TODAY, "records": [{"employee_id": emp, "status": "present"}]})
        self.assertEqual(r.status_code, 422)

    def test_upsert_single_record(self):
        emp = self.new_employee(self.a, f"UP-{self.dept}", self.dept)
        for status in ("present", "late"):
            r = self.a.put("/api/attendance", json={"date": TODAY, "records": [
                {"employee_id": emp, "status": status, "check_in": "09:30", "check_out": "17:00"}]})
            self.assertEqual(r.status_code, 200, r.text)
        sheet = self.a.get("/api/attendance", params={"date": TODAY, "department_id": self.dept}).json()
        rows = [i for i in sheet["items"] if i["employee_id"] == emp]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "late")
        month = self.a.get(f"/api/attendance/employee/{emp}", params={"month": TODAY[:7]}).json()
        self.assertEqual(len(month["records"]), 1)


class LeaveTests(ApiTestCase):
    def test_leave_flow(self):
        a = self.admin()
        dept = self.new_department(a, "LV1")
        emp = self.new_employee(a, "LV-E1", dept)
        base = {"employee_id": emp, "leave_type": "annual"}
        r = a.post("/api/leaves", json=base | {"start_date": "2026-03-10", "end_date": "2026-03-05"})
        self.assertEqual(r.status_code, 422)
        r = a.post("/api/leaves", json=base | {"start_date": "2026-03-10", "end_date": "2026-03-12"})
        self.assertEqual(r.status_code, 201, r.text)
        leave = r.json()
        self.assertEqual((leave["status"], leave["days"]), ("pending", 3))
        r = a.post("/api/leaves", json=base | {"start_date": "2026-03-12", "end_date": "2026-03-14"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(a.post(f"/api/leaves/{leave['id']}/status", json={"status": "approved"}).json()["status"], "approved")
        self.assertEqual(a.post(f"/api/leaves/{leave['id']}/status", json={"status": "rejected"}).status_code, 409)
        r = a.put(f"/api/leaves/{leave['id']}", json=base | {"start_date": "2026-03-10", "end_date": "2026-03-11"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.hr().delete(f"/api/leaves/{leave['id']}").status_code, 403)


class ReportTests(ApiTestCase):
    def test_monthly_report_matches_rows_and_csv(self):
        a = self.admin()
        dept = self.new_department(a, "RPT")
        e1 = self.new_employee(a, "RPT-1", dept)
        e2 = self.new_employee(a, "RPT-2", dept)
        d1 = date.today().replace(day=1)
        d2 = d1 + timedelta(days=1) if d1 + timedelta(days=1) <= date.today() else d1
        a.put("/api/attendance", json={"date": d1.isoformat(), "records": [
            {"employee_id": e1, "status": "present"}, {"employee_id": e2, "status": "half_day"}]})
        if d2 != d1:
            a.put("/api/attendance", json={"date": d2.isoformat(), "records": [
                {"employee_id": e1, "status": "absent"}, {"employee_id": e2, "status": "on_leave"}]})
        r = a.get("/api/reports/monthly", params={"month": TODAY[:7], "department_id": dept}).json()
        by_id = {i["employee_id"]: i for i in r["items"]}
        self.assertEqual(by_id[e1]["present"], 1)
        self.assertEqual(by_id[e2]["half_day"], 1)
        if d2 != d1:
            self.assertEqual(by_id[e1]["absent"], 1)
            self.assertEqual(by_id[e1]["attendance_rate"], 50.0)
            self.assertEqual(by_id[e2]["attendance_rate"], 50.0)
        self.assertEqual(r["totals"]["days_marked"], sum(i["days_marked"] for i in r["items"]))

        csv_resp = a.get("/api/reports/monthly.csv", params={"month": TODAY[:7], "department_id": dept})
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("text/csv", csv_resp.headers["content-type"])
        lines = csv_resp.text.strip().splitlines()
        self.assertEqual(len(lines), 1 + len(r["items"]) + 1)  # header + rows + total
        self.assertEqual(a.get("/api/reports/monthly", params={"month": "2026-13"}).status_code, 422)

    def test_dashboard_sums(self):
        s = self.admin().get("/api/dashboard", params={"date": TODAY}).json()["summary"]
        parts = s["present"] + s["late"] + s["half_day"] + s["absent"] + s["on_leave"] + s["not_marked"]
        self.assertEqual(parts, s["headcount"])


if __name__ == "__main__":
    unittest.main()
