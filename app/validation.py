"""Shared field types and validators for request bodies."""
import re
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import HTTPException
from pydantic import AfterValidator, BeforeValidator, StringConstraints

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
PHONE_RE = re.compile(r"^[0-9+()\- ]{6,20}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _strip(v):
    return v.strip() if isinstance(v, str) else v


def _check_iso_date(v: str) -> str:
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise ValueError("must be a date in YYYY-MM-DD format")


def _check_time(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not TIME_RE.match(v):
        raise ValueError("must be a time in HH:MM format")
    return v


def _check_email(v: str) -> str:
    if not EMAIL_RE.match(v):
        raise ValueError("is not a valid email address")
    return v.lower()


def _check_code(v: str) -> str:
    if not CODE_RE.match(v):
        raise ValueError("may contain only letters, digits, '-' and '_'")
    return v.upper()


def _check_phone(v: str) -> str:
    if v and not PHONE_RE.match(v):
        raise ValueError("may contain only digits, spaces, + - ( ) and be 6-20 characters")
    return v


def check_password_strength(v: str) -> str:
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("must contain at least one letter and one digit")
    return v


Stripped = BeforeValidator(_strip)

Name = Annotated[str, Stripped, StringConstraints(min_length=1, max_length=100)]
ShortText = Annotated[str, Stripped, StringConstraints(max_length=100)]
LongText = Annotated[str, Stripped, StringConstraints(max_length=500)]
IsoDate = Annotated[str, Stripped, AfterValidator(_check_iso_date)]
Time = Annotated[str | None, Stripped, AfterValidator(_check_time)]
Email = Annotated[str, Stripped, StringConstraints(max_length=254), AfterValidator(_check_email)]
DeptCode = Annotated[str, Stripped, StringConstraints(min_length=2, max_length=10), AfterValidator(_check_code)]
EmpCode = Annotated[str, Stripped, StringConstraints(min_length=2, max_length=20), AfterValidator(_check_code)]
Phone = Annotated[str, Stripped, AfterValidator(_check_phone)]
Username = Annotated[str, Stripped, StringConstraints(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128), AfterValidator(check_password_strength)]


def parse_month(month: str | None) -> str:
    """Validate a YYYY-MM query value; default to the current month."""
    if not month:
        return date.today().strftime("%Y-%m")
    if not MONTH_RE.match(month):
        raise HTTPException(422, "month must be in YYYY-MM format")
    return month


def parse_date(value: str | None, field: str = "date") -> str:
    if not value:
        return date.today().isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(422, f"{field} must be in YYYY-MM-DD format")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
