"""Drive the unit's web admin page with a real browser (Playwright)."""

import re
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .unit import Unit

TIMEOUT_MS = 15_000
REBOOT_TIMEOUT_MS = 180_000


class LoginRejected(Exception):
    """The page answered and refused the label's credentials."""


def login(page: Page, unit: Unit, profile: dict) -> None:
    page.goto(unit.admin_url + profile["login_path"], timeout=TIMEOUT_MS)
    page.fill(profile["username"], unit.label.admin_user)
    page.fill(profile["password"], unit.label.admin_password)
    page.click(profile["submit"])
    # Whichever appears first decides it. No answer at all is a timeout, not a
    # rejection: a unit that never responded must not be sent for a manual reset.
    page.wait_for_selector(
        f"{profile['logged_in']}, {profile['login_error']}", timeout=TIMEOUT_MS
    )
    if not page.is_visible(profile["logged_in"]):
        raise LoginRejected("page refused the label credentials")


def wait_until_up(
    page: Page, unit: Unit, profile: dict, timeout_ms: int = REBOOT_TIMEOUT_MS
) -> None:
    """Keep trying the login page until the unit answers after a reboot."""
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        try:
            page.goto(unit.admin_url + profile["login_path"], timeout=TIMEOUT_MS)
            page.wait_for_selector(profile["username"], timeout=TIMEOUT_MS)
            return
        except PlaywrightError:
            if time.monotonic() >= deadline:
                raise
            page.wait_for_timeout(2_000)


def factory_reset(page: Page, profile: dict) -> None:
    open_details(page, profile)
    page.click(profile["reset_button"], timeout=TIMEOUT_MS)


def open_details(page: Page, profile: dict) -> None:
    """Device details is reached by clicking, it has no URL of its own."""
    if not page.is_visible(profile["details"]):
        page.click(profile["open_details"], timeout=TIMEOUT_MS)
    page.wait_for_selector(profile["details"], timeout=TIMEOUT_MS)


def read_device_info(page: Page, profile: dict) -> dict:
    open_details(page, profile)
    info = {}
    for name, selector in profile["fields"].items():
        # The real page draws empty placeholders first and fills them in later
        page.wait_for_selector(f"{selector}:not(:empty)", timeout=TIMEOUT_MS)
        info[name] = page.inner_text(selector).strip()
    return info


def normalize_mac(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", value).upper()
