from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import connect, init_schema
from .routers import attendance, auth, dashboard, departments, employees, leaves, reports, users
from .security import user_from_token

# page path -> (html file, admin only)
PAGES = {
    "/": ("dashboard.html", False),
    "/employees": ("employees.html", False),
    "/departments": ("departments.html", False),
    "/attendance": ("attendance.html", False),
    "/leaves": ("leaves.html", False),
    "/reports": ("reports.html", False),
    "/users": ("users.html", True),
    "/account": ("account.html", False),
}

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; object-src 'none'; "
                               "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = connect()
    try:
        init_schema(conn)
        empty = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    finally:
        conn.close()
    if empty and config.SEED_ON_EMPTY:
        from .seed import seed
        seed()
    yield


app = FastAPI(title="Employee & Attendance Management System", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    headers = dict(SECURITY_HEADERS)
    if request.url.path in ("/docs", "/redoc"):
        # FastAPI's API docs load their UI from a CDN and use inline scripts.
        headers.pop("Content-Security-Policy")
    response.headers.update(headers)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


for r in (auth, users, departments, employees, attendance, leaves, reports, dashboard):
    app.include_router(r.router)

app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


def _session_user(request: Request) -> dict | None:
    conn = connect()
    try:
        return user_from_token(conn, request.cookies.get(config.COOKIE_NAME))
    finally:
        conn.close()


@app.get("/login", include_in_schema=False)
def login_page(request: Request):
    if _session_user(request):
        return RedirectResponse("/", status_code=303)
    return FileResponse(config.PAGES_DIR / "login.html")


def _page_handler(filename: str, admin_only: bool):
    def handler(request: Request):
        user = _session_user(request)
        if not user:
            return RedirectResponse("/login", status_code=303)
        if admin_only and user["role"] != "admin":
            return RedirectResponse("/", status_code=303)
        return FileResponse(config.PAGES_DIR / filename, headers={"Cache-Control": "no-store"})
    return handler


for path, (filename, admin_only) in PAGES.items():
    app.add_api_route(path, _page_handler(filename, admin_only), methods=["GET"], include_in_schema=False)
