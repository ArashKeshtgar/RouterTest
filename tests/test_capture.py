"""The page capture must find the selectors and hide device data."""

import importlib.util
import json
import threading
from pathlib import Path
from urllib.parse import unquote

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from routertest.mock_server import create_app

LABEL = json.loads(Path("samples/fake_label.json").read_text(encoding="utf-8"))
SOURCE = Path("browser/capture.js").read_text(encoding="utf-8")


def built_bookmarklet():
    spec = importlib.util.spec_from_file_location("build", "browser/build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return build.bookmarklet(SOURCE)


@pytest.fixture
def page():
    server = make_server("127.0.0.1", 0, create_app(LABEL))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tab = browser.new_page()
        tab.goto(f"http://127.0.0.1:{server.server_port}/")
        yield tab
        browser.close()
    server.shutdown()


def capture(page, code=SOURCE):
    page.evaluate(code)
    return page.input_value("#rt-capture-output")


def log_in(page):
    page.fill("#username", LABEL["U"])
    page.fill("#password", LABEL["P"])
    page.click("#login-btn")
    page.click("#device-card")
    page.wait_for_selector("#device-info")


def test_login_page_lists_selectors_but_not_typed_password(page):
    page.fill("#password", "typed-secret-123")
    output = capture(page)
    for selector in ("#username", "#password", "#login-btn"):
        assert selector in output
    assert "typed-secret-123" not in output


def test_details_page_hides_device_data(page):
    log_in(page)
    output = capture(page)
    assert "#serial" in output and "#factory-reset" in output
    assert "div#device-info > p" in output
    for secret in (LABEL["S"], "00:11:22:33:44:AA"):
        assert secret not in output


def test_capture_is_read_only_and_leaves_page_alone(page):
    requests = []
    page.on("request", lambda r: requests.append(r))
    capture(page)
    assert requests == []
    assert page.is_visible("#username")


def test_built_bookmarklet_runs(page):
    code = unquote(built_bookmarklet().removeprefix("javascript:"))
    assert "#username" in capture(page, code)
