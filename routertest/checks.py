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
    skipped: bool = False
    needs_manual_reset: bool = False

    @property
    def status(self) -> str:
        if self.skipped:
            return "SKIP"
        return "PASS" if self.passed else "FAIL"


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
    rejected = False
    with timed() as t:
        try:
            admin.login(page, unit, profile)
            ok, detail = True, "logged in"
        except admin.LoginRejected:
            ok, rejected = False, True
            detail = "label credentials rejected"
        except Exception as e:
            ok, detail = False, f"login failed: {_reason(e)}"
    return CheckResult("login", ok, detail, t["seconds"], needs_manual_reset=rejected)


def check_manual_reset(page, unit: Unit, profile: dict, ask_operator) -> CheckResult:
    """The previous customer changed the admin password, so the tool cannot get
    in: the operator resets the unit by hand, then the tool waits for it to return.

    The time includes the operator's part, so the report shows what these units cost.
    """
    with timed() as t:
        ask_operator()
        try:
            admin.wait_until_up(page, unit, profile)
            unit.manually_reset = True
            ok, detail = True, "admin password had been changed; reset by operator"
        except Exception as e:
            ok, detail = False, f"unit did not come back: {_reason(e)}"
    return CheckResult("manual_reset", ok, detail, t["seconds"])


def check_factory_reset(page, unit: Unit, profile: dict) -> CheckResult:
    if unit.manually_reset:
        return CheckResult(
            "factory_reset", True, "already reset by operator", skipped=True
        )
    with timed() as t:
        try:
            admin.factory_reset(page, unit, profile)
            ok, detail = True, "reset started"
        except Exception as e:
            ok, detail = False, f"reset failed: {_reason(e)}"
    return CheckResult("factory_reset", ok, detail, t["seconds"])


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
