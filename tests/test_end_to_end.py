"""Full run against the mock admin page in a background thread."""

import json
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from routertest import checks, pages, qr, report
from routertest.mock_server import create_app
from routertest.unit import Unit

LABEL = json.loads(Path("samples/fake_label.json").read_text(encoding="utf-8"))


@pytest.fixture
def mock_url():
    servers = []

    def start(**app_kwargs):
        server = make_server("127.0.0.1", 0, create_app(LABEL, **app_kwargs))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for s in servers:
        s.shutdown()


def run(url, label_json):
    unit = Unit(slot=1, label=qr.parse(json.dumps(label_json)), admin_url=url)
    profile = pages.get("mock")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        unit.results.append(checks.check_login(page, unit, profile))
        if unit.results[-1].passed:
            unit.results.append(checks.check_identity(page, unit, profile))
        browser.close()
    return unit


def test_good_unit_passes(mock_url, tmp_path):
    unit = run(mock_url(), LABEL)
    assert unit.passed, unit.results
    csv_path, html_path = report.write([unit], tmp_path)
    assert "PASS" in csv_path.read_text()
    assert "1 of 1 unit(s) passed" in html_path.read_text()


def test_wrong_password_fails_login(mock_url):
    unit = run(mock_url(), {**LABEL, "P": "wrong"})
    assert not unit.passed
    assert unit.results[0].name == "login" and not unit.results[0].passed


def test_label_mismatch_fails_identity(mock_url):
    unit = run(mock_url(identity_override={"imei": "000000000000999"}), LABEL)
    identity = unit.results[-1]
    assert identity.name == "identity" and not identity.passed
    assert "imei" in identity.detail


def test_real_profile_refuses_until_filled_in():
    with pytest.raises(NotImplementedError):
        pages.get("real")
