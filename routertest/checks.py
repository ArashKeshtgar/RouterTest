"""Individual test steps. Each returns a CheckResult; none of them raise."""

import time
from contextlib import contextmanager
from dataclasses import dataclass

from . import admin
from .unit import Unit


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    seconds: float = 0.0


@contextmanager
def timed():
    box = {}
    start = time.perf_counter()
    yield box
    box["seconds"] = round(time.perf_counter() - start, 2)


def _reason(e: Exception) -> str:
    """First line of the error only - Playwright appends long call logs."""
    lines = str(e).strip().splitlines()
    return f"{type(e).__name__}: {lines[0] if lines else ''}"


def check_login(page, unit: Unit, profile: dict) -> CheckResult:
    with timed() as t:
        try:
            admin.login(page, unit, profile)
            ok, detail = True, "logged in"
        except Exception as e:
            ok, detail = False, f"login failed: {_reason(e)}"
    return CheckResult("login", ok, detail, t["seconds"])


def check_identity(page, unit: Unit, profile: dict) -> CheckResult:
    """Device-reported serial/MAC/IMEI must match the QR label."""
    with timed() as t:
        try:
            info = admin.read_device_info(page, unit, profile)
        except Exception as e:
            info, error = None, f"could not read device info: {_reason(e)}"

    if info is None:
        return CheckResult("identity", False, error, t["seconds"])

    expected = {
        "serial": unit.label.serial,
        "mac": unit.label.mac,
        "imei": unit.label.imei,
    }
    actual = {
        "serial": info["serial"],
        "mac": admin.normalize_mac(info["mac"]),
        "imei": info["imei"],
    }
    mismatches = [k for k in expected if expected[k] != actual[k]]
    if mismatches:
        return CheckResult(
            "identity", False, f"label mismatch: {', '.join(mismatches)}", t["seconds"]
        )
    return CheckResult(
        "identity", True, f"matches label, firmware {info['firmware']}", t["seconds"]
    )
