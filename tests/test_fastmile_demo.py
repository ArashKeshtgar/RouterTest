"""The FastMile bookmarklet, run on a copy of the real page's structure."""

import importlib.util
import json
from pathlib import Path
from urllib.parse import unquote

import pytest
from playwright.sync_api import sync_playwright

LABEL = json.loads(Path("samples/fake_label.json").read_text(encoding="utf-8"))
SOURCE = Path("browser/fastmile_demo.js").read_text(encoding="utf-8")
ROUTER = "http://router.test/web_whw/"

APP = """<!doctype html><title>Router</title>
<div id="toast" style="display:none"><div>Invalid login credentials</div></div>
<div id="app"></div>
<script>
const app = document.getElementById('app');
const unit = UNIT;
window.signIns = 0; window.resets = 0; window.reboots = 0;
let loggedIn = unit.loggedIn;
const detail = (k, v) => `<div class="left"><div class="text"><pv-text><div>${k}</div></pv-text>
  <pv-text><div>${v}</div></pv-text></div></div>`;
const cell = (k, v) => `<div class="list"><div class="left"><div class="text"><pv-text><div>${k}</div>
  </pv-text></div></div><div class="right"><pv-text><div>${v}</div></pv-text></div></div>`;
const nav = '<div class="sidenav-logout flex-row__spacebetween"><div>Sign Out</div></div>';
function show(html) { app.innerHTML = nav + html; }
function login() {
  app.innerHTML = `<input id="username-login-value"><input id="passwordLoginAria" type="password">
    <button type="button" id="in" disabled>Sign in</button><div id="err"></div>`;
  const u = document.getElementById('username-login-value');
  const p = document.getElementById('passwordLoginAria');
  const button = document.getElementById('in');
  const change = () => { button.disabled = !(u.value && p.value); };
  u.addEventListener('input', change);
  p.addEventListener('input', change);
  button.onclick = () => {
    window.signIns++;
    if (u.value === unit.user && p.value === unit.password) {
      loggedIn = true;
      location.hash = '#/overview';
    } else {
      document.getElementById('err').innerHTML =
        '<div>Invalid login credentials. Login attempt failed 1 time</div>';
    }
  };
}
let drawing;
function overview() {
  show('<div>loading</div>');
  drawing = setTimeout(() => {
    show(`<h2>Network map</h2><div role="button" class="mapClickArea">Gateway</div>
      <div>5G+ Signal</div><div>${unit.signal}</div><div>RSRP</div><div>-82 dBm</div>
      <div>WiFi 2.4 GHz</div><div>Up, Auto</div><div>Channel 11</div>
      <div>WiFi 5 GHz</div><div>Up, Auto</div><div>Channel 64</div>
      <div>WiFi 6 GHz</div><div>Up, Auto</div><div>Channel 37</div>`);
    document.querySelector('.mapClickArea').onclick = details;
  }, 300);
}
function details() {
  show(`<button id="rebootButton">Reboot</button><button id="factorydefaultbtn">Reset</button>` +
    detail('Device name', unit.name) + detail('Serial number', unit.serial) +
    detail('MAC address', unit.mac) + detail('Software version', '1.2.3'));
  document.getElementById('factorydefaultbtn').onclick = () => window.resets++;
  document.getElementById('rebootButton').onclick = () => window.reboots++;
}
function cellular() {
  show(cell('Status', 'Valid') + '<pv-text id="imei-title"><div>IMEI</div></pv-text>' +
    cell('IMEI', unit.imei));
}
function route() {
  clearTimeout(drawing);
  if (!loggedIn) return login();
  if (location.hash === '#/wan/cellular-status') return cellular();
  overview();
}
window.addEventListener('hashchange', route);
route();
</script>"""


def built_bookmarklet():
    spec = importlib.util.spec_from_file_location("build", "browser/build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return build.bookmarklet(SOURCE)


def unit(**changes):
    mac = LABEL["23S"].replace(":", "")
    values = {
        "user": LABEL["U"],
        "password": LABEL["P"],
        "serial": LABEL["S"],
        "mac": ":".join(mac[i:i + 2] for i in range(0, 12, 2)),
        "imei": LABEL["IMEI"],
        "name": "FastMile 5G Gateway 12",
        "signal": "Connected",
        "loggedIn": False,
    }
    return {**values, **changes}


@pytest.fixture
def router():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def open_router(**changes):
            tab = browser.new_page()
            html = APP.replace("UNIT", json.dumps(unit(**changes)))
            tab.route(
                "http://router.test/**",
                lambda r: r.fulfill(body=html, content_type="text/html"),
            )
            tab.goto(ROUTER + "#/login")
            return tab

        yield open_router
        browser.close()


def run_demo(tab, code=SOURCE):
    tab.evaluate(code)
    # The scanner types like a keyboard and ends with Enter
    tab.locator("#rt-scan").press_sequentially(json.dumps(LABEL))
    tab.keyboard.press("Enter")
    tab.wait_for_selector("#rt-result", state="visible", timeout=20000)
    return tab.input_value("#rt-result")


def test_good_unit_passes_with_one_sign_in(router):
    tab = router()
    assert " | PASS | " in run_demo(tab)
    assert tab.evaluate("window.signIns") == 1


def test_built_bookmarklet_runs(router):
    code = unquote(built_bookmarklet().removeprefix("javascript:"))
    assert " | PASS | " in run_demo(router(), code)


def test_never_touches_reset_or_reboot(router):
    tab = router()
    run_demo(tab)
    assert tab.evaluate("[window.resets, window.reboots]") == [0, 0]


def test_changed_password_tells_operator_to_reset_and_tries_once(router):
    tab = router(password="changed-by-customer")
    assert "RESET BY HAND" in run_demo(tab)
    assert tab.evaluate("window.signIns") == 1


def test_already_logged_in_skips_sign_in(router):
    tab = router(loggedIn=True)
    assert " | PASS | " in run_demo(tab)
    assert tab.evaluate("window.signIns") == 0


@pytest.mark.parametrize(
    "change, row",
    [
        ({"serial": "OTHER-SERIAL"}, "Serial FAIL"),
        ({"imei": "000000000000009"}, "IMEI FAIL"),
        ({"mac": "AA:BB:CC:DD:EE:FF"}, "MAC FAIL"),
        ({"name": "FastMile 5G Gateway 3.2"}, "Model FAIL"),
        ({"signal": "Disconnected"}, "5G FAIL"),
    ],
)
def test_wrong_unit_fails_the_right_row(router, change, row):
    result = run_demo(router(**change))
    assert " | FAIL | " in result
    assert row in result


def test_result_to_copy_has_no_device_data(router):
    result = run_demo(router(serial="OTHER-SERIAL"))
    for secret in (LABEL["P"], LABEL["S"], LABEL["IMEI"], LABEL["KY"], "OTHER-SERIAL"):
        assert secret not in result


def test_password_is_not_left_in_the_scan_box(router):
    tab = router()
    run_demo(tab)
    assert tab.input_value("#rt-scan") == ""
