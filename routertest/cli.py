"""Operator entry point: scan a QR, the tool runs the checks and writes a report.

    python -m routertest.cli --mock     # against the fake admin page (start it first)
    python -m routertest.cli --real     # against a unit on 192.168.1.1
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import checks, pages, qr, report
from .unit import Unit

MOCK_URL = "http://127.0.0.1:7357"
SHOW_SLOW_MS = 800


def ask_manual_reset() -> None:
    print("  Login rejected: the previous customer changed the admin password.")
    print("  Factory-reset this unit by hand with the button on the back.")
    input("  When the LED is green again, press Enter: ")


def run_steps(page, unit: Unit, profile: dict, ask_operator) -> None:
    login = checks.check_login(page, unit, profile)
    if login.needs_manual_reset:
        reset = checks.check_manual_reset(page, unit, profile, ask_operator)
        unit.results.append(reset)
        if not reset.passed:
            return
        login = checks.check_login(page, unit, profile)
    unit.results.append(login)
    if not login.passed:
        return
    unit.results.append(checks.check_identity(page, unit, profile))
    # A failed unit keeps its state so someone can look at why it failed
    if unit.passed:
        unit.results.append(checks.check_factory_reset(page, unit, profile))


def run_unit(unit: Unit, profile: dict, headless: bool) -> None:
    with sync_playwright() as p:
        # The mock answers instantly, so a visible run needs slowing to be watchable
        browser = p.chromium.launch(headless=headless, slow_mo=0 if headless else SHOW_SLOW_MS)
        page = browser.new_page()
        try:
            run_steps(page, unit, profile, ask_manual_reset)
            if not headless:
                input("Test finished. Press Enter to close the browser: ")
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Gateway functional test")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mock", action="store_true", help="use the fake admin page")
    mode.add_argument("--real", action="store_true", help="use a real unit")
    parser.add_argument("--url", help="override admin URL")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()

    url = args.url or (MOCK_URL if args.mock else "http://192.168.1.1")

    raw = input("Scan QR code: ")
    try:
        label = qr.parse(raw)
    except qr.QRError as e:
        print(f"FAIL - {e}")
        raise SystemExit(1)
    print(f"Unit: {label.masked()}")

    try:
        profile = pages.get("mock") if args.mock else pages.for_model(label.model)
    except (pages.UnknownModel, NotImplementedError) as e:
        print(f"FAIL - {e}")
        raise SystemExit(1)

    unit = Unit(slot=1, label=label, admin_url=url)
    run_unit(unit, profile, headless=not args.show_browser)

    for r in unit.results:
        print(f"  {r.status}  {r.name:<14} {r.seconds:>6}s  {r.detail}")
    print("UNIT PASS" if unit.passed else "UNIT FAIL")

    csv_path, html_path = report.write([unit], Path(args.out))
    print(f"Report: {html_path}")


if __name__ == "__main__":
    main()
