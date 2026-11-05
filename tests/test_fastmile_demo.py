"""The FastMile bookmarklet, run on a copy of the real page's structure."""

import importlib.util
import json
from pathlib import Path
from urllib.parse import unquote

import pytest
from playwright.sync_api import sync_playwright

LABEL = json.loads(Path("samples/fake_label.json").read_text(encoding="utf-8"))
SOURCE = Path("browser/fastmile_demo.js").read_text(encoding="utf-8")


def fast(code):
    return code.replace("var POLL_MS = 3000", "var POLL_MS = 50").replace(
        "var SETTLE_MS = 20000", "var SETTLE_MS = 0"
    )


FAST = fast(SOURCE)
ROUTER = "http://router.test/web_whw/"

APP = """<!doctype html><title>Router</title>
<div id="toast" style="display:none"><div>Invalid login credentials</div></div>
<div id="app"></div>
<script>
const app = document.getElementById('app');
const unit = UNIT;
window.signIns = 0; window.resets = 0; window.reboots = 0; window.cancels = 0;
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
  show(`<pv-button id="rebootButton"><button>Reboot</button></pv-button>
    <pv-button id="factorydefaultbtn"><button>Reset</button></pv-button>` +
    detail('Device name', unit.name) + detail('Serial number', unit.serial) +
    detail('MAC address', unit.mac) + detail('Software version', '1.2.3'));
  document.querySelector('#factorydefaultbtn button').onclick = askToConfirm;
  document.querySelector('#rebootButton button').onclick = () => window.reboots++;
}
function askToConfirm() {
  const dialog = document.createElement('div');
  dialog.innerHTML = `<button id="no">Cancel</button><button id="yes">${unit.confirm}</button>`;
  app.appendChild(dialog);
  document.getElementById('no').onclick = () => window.cancels++;
  document.getElementById('yes').onclick = () => { window.resets++; loggedIn = false; fetch('/restart-now'); };
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
        "confirm": "Reset",
    }
    return {**values, **changes}


@pytest.fixture
def router():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def open_router(**changes):
            tab = browser.new_page()
            html = APP.replace("UNIT", json.dumps(unit(**changes)))
            down = {"requests": 0}

            def serve(route):
                if route.request.url.endswith("/restart-now"):
                    down["requests"] = 3
                if down["requests"] and not route.request.url.endswith("/restart-now"):
                    down["requests"] -= 1
                    return route.abort()
                return route.fulfill(body=html, content_type="text/html")

            tab.route("http://router.test/**", serve)
            tab.goto(ROUTER + "#/login")
            return tab

        yield open_router
        browser.close()


def run_demo(tab, code=FAST):
    tab.evaluate(code)
    # The scanner types like a keyboard and ends with Enter
    tab.locator("#rt-scan").press_sequentially(json.dumps(LABEL))
    tab.keyboard.press("Enter")
    tab.wait_for_selector("#rt-result", state="visible", timeout=20000)
    return tab.input_value("#rt-result")


def test_good_unit_passes_with_a_sign_in_each_side_of_the_reset(router):
    tab = router()
    assert " | PASS | " in run_demo(tab)
    assert tab.evaluate("window.signIns") == 2


def test_built_bookmarklet_runs(router):
    code = unquote(built_bookmarklet().removeprefix("javascript:"))
    assert " | PASS | " in run_demo(router(), fast(code))


def test_reset_comes_first_after_login(router):
    tab = router()
    result = run_demo(tab)
    assert result.index("Factory reset PASS") < result.index("Back up PASS") < result.index("IMEI")
    assert tab.evaluate("[window.resets, window.reboots, window.cancels]") == [1, 0, 0]


def test_scanning_again_does_not_reset_twice(router):
    tab = router()
    run_demo(tab)
    assert " | PASS | " in run_demo(tab)
    assert tab.evaluate("window.resets") == 1


def test_hand_reset_unit_is_not_reset_again(router):
    tab = router(password="changed-by-customer")
    run_demo(tab)
    assert "reload" in run_demo(tab)
    tab.evaluate(f"unit.password = {json.dumps(LABEL['P'])}")
    tab.evaluate("document.getElementById('err').innerHTML = ''")
    assert " | PASS | " in run_demo(tab)
    assert tab.evaluate("window.resets") == 0


def test_unknown_confirm_button_is_not_guessed(router):
    tab = router(confirm="Erase everything")
    code = FAST.replace("var WAIT_MS = 30000", "var WAIT_MS = 3000")
    result = run_demo(tab, code)
    assert "CHECK RESET BY HAND" in result
    assert tab.evaluate("[window.resets, window.cancels]") == [0, 0]


def test_changed_password_tells_operator_to_reset_and_tries_once(router):
    tab = router(password="changed-by-customer")
    assert "RESET BY HAND" in run_demo(tab)
    assert tab.evaluate("window.signIns") == 1


def test_already_logged_in_skips_sign_in(router):
    tab = router(loggedIn=True)
    assert " | PASS | " in run_demo(tab)
    assert tab.evaluate("window.signIns") == 1


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


def saved_log(tab):
    downloads = []
    tab.on("download", lambda d: downloads.append(d))
    run_demo(tab)
    tab.wait_for_timeout(500)
    last = downloads[-1]
    return last.suggested_filename, Path(last.path()).read_text(encoding="utf-8")


def test_log_file_is_saved_with_every_step(router):
    name, log = saved_log(router())
    assert name.startswith("fastmile-demo-log-") and name.endswith(".txt")
    for step in ("clicked Sign in", "IMEI: PASS", "Serial: PASS", "RESULT: PASS"):
        assert step in log


def test_log_has_no_device_data(router):
    _, log = saved_log(router(serial="OTHER-SERIAL"))
    assert "RESULT: FAIL" in log
    for secret in (LABEL["P"], LABEL["KY"], LABEL["S"], LABEL["IMEI"], LABEL["IMEI"][-4:], "SERIAL"):
        assert secret not in log


def test_log_says_where_a_stuck_run_stopped(router):
    tab = router(loggedIn=True)
    tab.evaluate(FAST.replace("var WAIT_MS = 30000", "var WAIT_MS = 1000"))
    tab.add_style_tag(content=".mapClickArea { display: none }")
    with tab.expect_download() as download:
        tab.locator("#rt-scan").press_sequentially(json.dumps(LABEL))
    log = Path(download.value.path()).read_text(encoding="utf-8")
    assert "map on page: false" in log
    assert "page: /web_whw/#/overview" in log
