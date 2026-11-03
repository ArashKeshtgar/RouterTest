"""Drive the unit's web admin page with a real browser (Playwright)."""

import re

from playwright.sync_api import Page

from .unit import Unit

TIMEOUT_MS = 15_000


def login(page: Page, unit: Unit, profile: dict) -> None:
    page.goto(unit.admin_url + profile["login_path"], timeout=TIMEOUT_MS)
    page.fill(profile["username"], unit.label.admin_user)
    page.fill(profile["password"], unit.label.admin_password)
    page.click(profile["submit"])
    page.wait_for_selector(profile["logged_in"], timeout=TIMEOUT_MS)


def read_device_info(page: Page, unit: Unit, profile: dict) -> dict:
    page.goto(unit.admin_url + profile["info_path"], timeout=TIMEOUT_MS)
    return {
        name: page.inner_text(selector, timeout=TIMEOUT_MS).strip()
        for name, selector in profile["fields"].items()
    }


def normalize_mac(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", value).upper()
