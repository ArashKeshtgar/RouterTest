"""Full run against the mock admin page in a background thread."""

import json
import threading
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from routertest import cli, pages, qr, report
from routertest.mock_server import create_app
from routertest.unit import Unit

LABEL = json.loads(Path("samples/fake_label.json").read_text(encoding="utf-8"))
states = {}


@pytest.fixture
def mock_url():
    servers = []

    def start(**app_kwargs):
        app = create_app(LABEL, **app_kwargs)
        server = make_server("127.0.0.1", 0, app)
        states[f"http://127.0.0.1:{server.server_port}"] = app.config["STATE"]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for s in servers:
        s.shutdown()


def press_reset_button(url):
    def ask_operator():
        urllib.request.urlopen(url + "/hardware-reset").read()
    return ask_operator


def never_asked():
    raise AssertionError("operator should not have been asked to reset")


def run(url, label_json, ask_operator=never_asked):
    unit = Unit(slot=1, label=qr.parse(json.dumps(label_json)), admin_url=url)
    profile = pages.get("mock")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        cli.run_steps(page, unit, profile, ask_operator)
        browser.close()
    return unit


def statuses(unit):
    return [(r.name, r.status) for r in unit.results]


def test_good_unit_passes(mock_url, tmp_path):
    url = mock_url()
    unit = run(url, LABEL)
    assert unit.passed, unit.results
    assert unit.results[-1].name == "factory_reset"
    assert states[url]["software_resets"] == 1
    csv_path, html_path = report.write([unit], tmp_path)
    assert "PASS" in csv_path.read_text()
    assert "1 of 1 unit(s) passed" in html_path.read_text()


def test_changed_password_asks_operator_and_skips_software_reset(mock_url, tmp_path):
    url = mock_url(customer_password="set-by-customer")
    unit = run(url, LABEL, press_reset_button(url))
    assert unit.passed, unit.results
    assert statuses(unit) == [
        ("manual_reset", "PASS"),
        ("login", "PASS"),
        ("identity", "PASS"),
        ("factory_reset", "SKIP"),
    ]
    assert states[url]["hardware_resets"] == 1
    assert states[url]["software_resets"] == 0
    csv_path, _ = report.write([unit], tmp_path)
    assert "SKIP" in csv_path.read_text()


def test_still_rejected_after_manual_reset_fails(mock_url):
    url = mock_url()
    unit = run(url, {**LABEL, "P": "wrong"}, press_reset_button(url))
    assert not unit.passed
    assert statuses(unit) == [("manual_reset", "PASS"), ("login", "FAIL")]


def test_unreachable_unit_fails_without_asking_for_reset():
    # Nothing listens here: a dead unit must not be sent for a manual reset
    unit = run("http://127.0.0.1:9", LABEL)
    assert statuses(unit) == [("login", "FAIL")]
    assert "label credentials" not in unit.results[0].detail


def test_label_mismatch_fails_identity(mock_url):
    url = mock_url(identity_override={"imei": "000000000000999"})
    unit = run(url, LABEL)
    identity = unit.results[-1]
    assert identity.name == "identity" and not identity.passed
    assert "imei" in identity.detail
    assert states[url]["software_resets"] == 0


def test_real_profile_refuses_until_filled_in():
    with pytest.raises(NotImplementedError):
        pages.for_model("5G31-03W-B")


def test_unknown_model_is_refused():
    with pytest.raises(pages.UnknownModel, match="XYZ-1"):
        pages.for_model("XYZ-1")
