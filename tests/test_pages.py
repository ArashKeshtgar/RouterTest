"""Real selectors, tried on a copy of the page structure from a real capture."""

import pytest
from playwright.sync_api import sync_playwright

from routertest import admin, pages

DETAILS_HTML = """
<div class="left"><div class="text">
  <pv-text><div>Serial number</div></pv-text><pv-text><div>FAKE-SERIAL</div></pv-text>
</div></div>
<div class="left"><div class="text">
  <pv-text><div>MAC address</div></pv-text><pv-text><div>00:11:22:33:44:AA</div></pv-text>
</div></div>
<div class="left"><div class="text">
  <pv-text><div>Software version</div></pv-text><pv-text><div>FAKE-1.0</div></pv-text>
</div></div>
"""

CELLULAR_HTML = """
<pv-card id="imei-card"><pv-text id="imei-title"><div>IMEI</div></pv-text>
  <div class="list">
    <div class="left"><div class="text"><pv-text><div>IMEI</div></pv-text></div></div>
    <div class="right"><pv-text><div>000000000000001</div></pv-text></div>
  </div>
</pv-card>
"""


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page()
        browser.close()


@pytest.mark.parametrize("name", ["fastmile_12", "fastmile_3_2"])
def test_fastmile_details_are_read_from_their_labels(page, name):
    profile = pages.PROFILES[name]
    page.set_content(DETAILS_HTML)
    page.wait_for_selector(profile["details"])
    assert admin._read_fields(page, profile["fields"]) == {
        "serial": "FAKE-SERIAL",
        "mac": "00:11:22:33:44:AA",
        "firmware": "FAKE-1.0",
    }


def test_fastmile_imei_is_the_value_not_the_title(page):
    page.set_content(CELLULAR_HTML)
    fields = pages.PROFILES["fastmile_12"]["cellular_fields"]
    assert admin._read_fields(page, fields) == {"imei": "000000000000001"}


def test_error_dialog_selector_combines_with_logged_in(page):
    profile = pages.PROFILES["fastmile_12"]
    page.set_content("<div>Invalid login credentials. Login attempt failed 1 time</div>")
    page.wait_for_selector(f"{profile['logged_in']}, {profile['login_error']}")
    assert not page.is_visible(profile["logged_in"])
