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


def run_unit(unit: Unit, profile: dict, headless: bool) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            login = checks.check_login(page, unit, profile)
            unit.results.append(login)
            if login.passed:
                unit.results.append(checks.check_identity(page, unit, profile))
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

    profile = pages.get("mock" if args.mock else "real")
    url = args.url or (MOCK_URL if args.mock else "http://192.168.1.1")

    raw = input("Scan QR code: ")
    try:
        label = qr.parse(raw)
    except qr.QRError as e:
        print(f"FAIL - {e}")
        raise SystemExit(1)
    print(f"Unit: {label.masked()}")

    unit = Unit(slot=1, label=label, admin_url=url)
    run_unit(unit, profile, headless=not args.show_browser)

    for r in unit.results:
        print(f"  {'PASS' if r.passed else 'FAIL'}  {r.name:<10} {r.seconds:>6}s  {r.detail}")
    print("UNIT PASS" if unit.passed else "UNIT FAIL")

    csv_path, html_path = report.write([unit], Path(args.out))
    print(f"Report: {html_path}")


if __name__ == "__main__":
    main()
