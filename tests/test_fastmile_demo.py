"""The FastMile test station, run on a copy of the real page's structure. The login,
overview, details and cellular pages follow the Gateway 12 captures v1 to v5.
The router's own address redirects to its login page, as the operator sees it.
The reset confirm dialog and the restart timing are still guesses."""

import importlib.util
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import pytest
from playwright.sync_api import sync_playwright

LABEL = json.loads(Path("samples/fake_label.json").read_text(encoding="utf-8"))
SOURCE = Path("browser/fastmile_demo.js").read_text(encoding="utf-8")


def fast(code):
    for old, new in (
        ("var POLL_MS = 3000", "var POLL_MS = 50"),
        ("var READY_MS = 300000", "var READY_MS = 1500"),
        ("var REOPEN_MS = 20000", "var REOPEN_MS = 500"),
        ("var RECHECK_MS = 5000", "var RECHECK_MS = 20"),
        ("var GREEN_MS = 120000", "var GREEN_MS = 30"),
        ("var SETTLE_MS = 20000", "var SETTLE_MS = 0"),
        ("var SESSION_MS = 8000", "var SESSION_MS = 400"),
        ("var CONNECT_MS = 120000", "var CONNECT_MS = 1000"),
        ("var LOGIN_WAIT_MS = 90000", "var LOGIN_WAIT_MS = 1000"),
    ):
        code = code.replace(old, new)
    return code


FAST = fast(SOURCE)

APP = """<!doctype html><title>Router</title>
<div id="app"></div>
<script>
const app = document.getElementById('app');
const unit = UNIT;
const tell = (name) => fetch('/tell/' + name);
let loggedIn = unit.loggedIn;
const detail = (k, v) => `<div class="left"><div class="text"><pv-text><div>${k}</div></pv-text>
  <pv-text><div>${v}</div></pv-text></div></div>`;
const cell = (k, v) => `<div class="list"><div class="left"><div class="text"><pv-text><div>${k}</div>
  </pv-text></div></div><div class="right"><pv-text><div>${v}</div></pv-text></div></div>`;
const nav = '<div class="sidenav-logout flex-row__spacebetween"><div>Sign Out</div></div>';
function show(html) { app.innerHTML = nav + html; }
function login() {
  app.innerHTML = `<div class="pos-relative">English</div><pv-text><div>Username</div></pv-text>
    <input id="username-login-value"><pv-text><div>Password</div></pv-text>
    <input id="passwordLoginAria" type="password">
    <pv-vector name="input_eye_show" role="button"></pv-vector>
    <button type="button" id="in" disabled><span>Sign in</span></button>
    <div style="display:none"><div>Request timeout</div><button type="button"></button></div>
    <div id="err"></div><pv-text role="link"><div>Recommended browsers</div></pv-text>`;
  const u = document.getElementById('username-login-value');
  const p = document.getElementById('passwordLoginAria');
  const button = document.getElementById('in');
  const change = () => { button.disabled = !(u.value && p.value); };
  u.addEventListener('input', change);
  p.addEventListener('input', change);
  button.onclick = () => {
    tell('signIns');
    if (u.value === unit.user && p.value === unit.password) {
      tell('loggedIn');
      loggedIn = true;
      location.hash = '#/overview';
      if (location.hash === '#/overview') route();
    } else {
      document.getElementById('err').innerHTML =
        '<div>Invalid login credentials. Login attempt failed 1 time</div>' +
        '<button type="button"><span>Okay</span></button>';
    }
  };
}
let drawing;
function overview() {
  show('<div>loading</div>');
  drawing = setTimeout(() => {
    show(`<h2>Network map</h2><div role="button" class="mapClickArea">Gateway</div>
      <div>5G+ Signal</div><div id="signal">${unit.signal}</div><div>RSRP</div><div>-82 dBm</div>
      <div>WiFi 2.4 GHz</div><div>Up, Auto</div><div>Channel 11</div>
      <div>WiFi 5 GHz</div><div>Up, Auto</div><div>Channel 64</div>
      <div>WiFi 6 GHz</div><div>Up, Auto</div><div>Channel 37</div>
      <pv-wifi-card class="home-wifi--card"><div>${unit.ssid}</div>
        <div>Home Network - 2.4 GHz / 5 GHz / 6 GHz</div></pv-wifi-card>`);
    document.querySelector('.mapClickArea').onclick = details;
    if (unit.flapping) {
      let n = 0;
      setInterval(() => {
        const signal = document.getElementById('signal');
        if (signal) signal.textContent = 'Searching ' + n++;
      }, 5);
    }
  }, 300);
}
function details() {
  show(`<pv-vector name="arrow_left" role="button"></pv-vector>
    <pv-text id="reboot"><div>Reboot</div></pv-text>
    <pv-button id="rebootButton"><button type="button"><span>Reboot</span></button></pv-button>
    <pv-text id="factorydefault"><div>Factory default</div></pv-text>
    <pv-button id="factorydefaultbtn"><button type="button"><span>Reset</span></button></pv-button>` +
    detail('Device name', unit.name) + detail('Serial number', unit.serial) +
    detail('MAC address', unit.mac) + detail('Software version', '1.2.3'));
  document.querySelector('#factorydefaultbtn button').onclick = askToConfirm;
  document.querySelector('#rebootButton button').onclick = () => tell('reboots');
}
function askToConfirm() {
  const dialog = document.createElement('div');
  dialog.innerHTML = `<button id="no">Cancel</button><button id="yes">${unit.confirm}</button>`;
  app.appendChild(dialog);
  document.getElementById('no').onclick = () => tell('cancels');
  document.getElementById('yes').onclick = () => { tell('resets'); tell('restart'); };
}
function cellular() {
  show(cell('SIM', 'ROGERS') + cell('Type', 'Removable') + cell('Status', 'Valid') +
    '<pv-card id="imei-card"><pv-text id="imei-title"><h2>IMEI</h2></pv-text>' +
    cell('IMEI', unit.imei) + '</pv-card>');
}
function route() {
  clearTimeout(drawing);
  if (!loggedIn && unit.flash && location.hash !== '#/login') {
    show('<div role="button" class="mapClickArea">Gateway</div>');
    drawing = setTimeout(login, unit.flash);
    return;
  }
  if (!loggedIn) return login();
  if (location.hash === '#/wan/cellular-status') return cellular();
  overview();
}
window.addEventListener('hashchange', route);
route();
</script>"""

OTHER_ROUTER_PAGE = "<title>Router</title><p>Please wait</p>"
UNREADY_PAGE = '<title>x</title><p>Starting up 12345</p><input id="other-user" value="secret-value">'


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
        "ssid": LABEL["ID"],
        "loggedIn": False,
        "confirm": "Reset",
    }
    return {**values, **changes}


class Bench:
    """A mock router and the tab the demo starts from. The router keeps its state
    here, so it survives the page being opened again, as on the real unit."""

    def __init__(self, context, changes, block_frames=False):
        self.state = unit(**changes)
        self.counts = {"signIns": 0, "resets": 0, "reboots": 0, "cancels": 0}
        self.down = 0
        self.off = False
        self.block_frames = block_frames
        self.page_html = None
        self.home = "/web_whw/#/login"
        self.login_page = OTHER_ROUTER_PAGE
        self.downloads = []
        self.context = context
        self.station = None
        bench = self

        class Router(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                bench.answer(self)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Router)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.address = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.first = context.new_page()
        self.first.goto(self.address + "/web_whw/#/login")

    def tell(self, name):
        if name == "loggedIn":
            self.state["loggedIn"] = True
        elif name == "logout":
            self.state["loggedIn"] = False
        elif name == "restart":
            self.down = 3
            self.state["loggedIn"] = False
        else:
            self.counts[name] += 1

    def answer(self, request):
        name = request.path.rsplit("/", 1)[-1]
        if "/tell/" in request.path:
            self.tell(name)
            body = b"ok"
        elif self.off or self.down:
            self.down = max(self.down - 1, 0)
            request.close_connection = True
            request.connection.shutdown(socket.SHUT_RDWR)
            return
        elif request.path == "/":
            request.send_response(302)
            request.send_header("Location", self.home)
            request.send_header("Content-Length", "0")
            request.end_headers()
            return
        else:
            page = self.login_page if request.path == "/login" else self.page_html
            body = (page or APP.replace("UNIT", json.dumps(self.state))).encode("utf-8")
        request.send_response(200)
        request.send_header("Content-Type", "text/html; charset=utf-8")
        request.send_header("Content-Length", str(len(body)))
        if self.block_frames:
            request.send_header("X-Frame-Options", "DENY")
        request.end_headers()
        request.wfile.write(body)

    def open_station(self, code=FAST):
        with self.context.expect_page() as opened:
            self.first.evaluate(code)
        self.station = opened.value
        self.station.on("download", lambda d: self.downloads.append(d))
        self.station.wait_for_selector("#rt-scan")
        return self.station

    def scan(self, label=LABEL):
        self.station.locator("#rt-scan").press_sequentially(json.dumps(label))

    def finished(self):
        self.station.wait_for_selector("#rt-result", state="visible", timeout=20000)
        return self.station.input_value("#rt-result")

    def run(self, code=FAST):
        if not self.station:
            self.open_station(code)
        self.scan()
        self.station.wait_for_selector("#rt-result", state="hidden", timeout=5000)
        return self.finished()

    def saved(self, ending):
        self.station.wait_for_timeout(300)
        return [d for d in self.downloads if d.suggested_filename.endswith(ending)]

    def log(self):
        return Path(self.saved(".txt")[-1].path()).read_text(encoding="utf-8")


@pytest.fixture
def router():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def open_router(block_frames=False, **changes):
            return Bench(browser.new_context(), changes, block_frames)

        yield open_router
        browser.close()


def test_good_unit_passes_with_a_sign_in_each_side_of_the_reset(router):
    bench = router()
    assert " | PASS | " in bench.run()
    assert bench.counts["signIns"] == 2


def test_built_bookmarklet_runs(router):
    code = unquote(built_bookmarklet().removeprefix("javascript:"))
    assert " | PASS | " in router().run(fast(code))


def test_station_opens_in_its_own_tab_and_waits_for_a_scan(router):
    bench = router()
    station = bench.open_station()
    assert station.title() == "Router test station"
    station.wait_for_selector("#rt-link.up")
    station.wait_for_timeout(500)
    assert station.get_attribute("#rt-frame", "src") is None
    assert bench.first.url == bench.address + "/web_whw/#/login"
    bench.scan()
    station.wait_for_function(
        "document.getElementById('rt-frame').contentWindow.location.pathname === '/web_whw/'")


def test_nothing_touches_the_router_before_a_scan(router):
    bench = router()
    station = bench.open_station()
    station.wait_for_selector("#rt-link.up")
    bench.off = True
    station.wait_for_selector("#rt-link.down")
    bench.off = False
    station.wait_for_selector("#rt-link.up")
    station.wait_for_timeout(300)
    text = station.inner_text("#rt-log")
    assert "CLICK" not in text and "TRYING" not in text
    assert "no test is running. Last click by the demo: none since this page opened" in text
    assert bench.first.url == bench.address + "/web_whw/#/login"
    assert bench.counts == {"signIns": 0, "resets": 0, "reboots": 0, "cancels": 0}


def test_every_click_is_in_the_log_and_the_reset_is_named(router):
    bench = router()
    bench.run()
    log = bench.log()
    clicks = [line.split("CLICK: ")[1] for line in log.splitlines() if "CLICK: " in line]
    assert clicks == ["Sign in", "the device on the Network map, to open its details",
                      "Factory default > Reset", 'confirm button "Reset"', "Sign in"]
    assert "FACTORY RESET: pressed by the demo at " in log


def test_a_run_that_never_reaches_the_reset_says_so(router):
    bench = router(serial="OTHER-SERIAL")
    bench.run()
    assert "FACTORY RESET: not pressed by the demo in this run" in bench.log()


def test_opening_the_bookmark_again_keeps_the_same_station(router):
    bench = router()
    bench.open_station()
    bench.first.evaluate(FAST)
    bench.station.wait_for_timeout(200)
    assert len(bench.context.pages) == 2


def test_on_another_site_it_goes_to_the_router_and_does_not_start(router):
    bench = router()
    messages = []
    bench.first.on("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    bench.context.route("http://192.168.1.1/", lambda r: r.fulfill(body="router", content_type="text/html"))
    bench.first.goto(bench.address.replace("127.0.0.1", "localhost") + "/web_whw/#/login")
    with bench.first.expect_navigation():
        bench.first.evaluate(FAST)
    assert "click the bookmark again" in messages[0]
    assert bench.first.url == "http://192.168.1.1/"
    assert len(bench.context.pages) == 1


def test_blocked_pop_up_takes_over_the_tab(router):
    bench = router()
    bench.first.evaluate("window.open = () => null")
    bench.first.evaluate(FAST)
    bench.first.wait_for_selector("#rt-scan")
    bench.station = bench.first
    bench.first.on("download", lambda d: bench.downloads.append(d))
    assert " | PASS | " in bench.run()


def test_opened_on_another_router_page_it_finds_the_login(router):
    bench = router()
    bench.first.goto(bench.address + "/login")
    assert " | PASS | " in bench.run()
    assert "opened from /login" in bench.log()


def test_router_address_that_leads_nowhere_falls_back_to_the_known_login(router):
    bench = router()
    bench.home = "/login"
    assert " | PASS | " in bench.run(FAST.replace("var REOPEN_MS = 500", "var REOPEN_MS = 200"))
    log = bench.log()
    assert "no login box on page /login" in log
    assert "open " + bench.address + "/web_whw/#/login" in log


def test_buttons_of_the_reset_dialog_are_written_down(router):
    bench = router()
    bench.run()
    assert "buttons after Reset: Cancel, Reset" in bench.log()


def test_order_is_identity_then_reset_then_functional(router):
    bench = router()
    result = bench.run()
    steps = ["Serial PASS", "Factory reset PASS", "Back up PASS", "Login PASS", "Green light", "IMEI PASS"]
    places = [result.rindex(step) if step == "Login PASS" else result.index(step) for step in steps]
    assert places == sorted(places)
    assert [bench.counts[k] for k in ("resets", "reboots", "cancels")] == [1, 0, 0]


def test_waits_for_a_router_that_is_slow_to_come_up(router):
    bench = router()
    bench.open_station()
    bench.station.wait_for_selector("#rt-link.up")
    bench.off = True
    bench.station.wait_for_selector("#rt-link.down")
    bench.scan()
    bench.station.wait_for_timeout(400)
    bench.off = False
    assert " | PASS | " in bench.finished()
    assert "router stopped answering" in bench.log()


def test_router_that_stays_off_says_why(router):
    bench = router()
    bench.open_station()
    bench.station.wait_for_selector("#rt-link.up")
    bench.off = True
    bench.station.wait_for_selector("#rt-link.down")
    result = bench.run()
    assert " | NOT TESTED | " in result
    assert "not answering" in result
    log = bench.log()
    assert "RESULT: NOT TESTED" in log and "WHY: " in log and "DO NEXT: " in log


def test_page_without_a_login_box_says_what_it_saw(router):
    bench = router()
    bench.page_html = UNREADY_PAGE
    result = bench.run()
    assert " | NOT TESTED | " in result
    assert "login box never appeared" in result
    log = bench.log()
    assert 'field: input id="other-user" type="text"' in log
    assert "page text: Starting up ***" in log
    assert "no login box on page" in log
    assert "secret-value" not in log
    for fact in ("PC id ", "Chrome/", bench.address):
        assert fact in log
    assert [bench.counts[k] for k in ("signIns", "resets")] == [0, 0]
    assert [t["FieldValue"] for t in json.loads(Path(bench.saved(".json")[-1].path()).read_text())["Transactions"]] == [
        "NOT-RUN", "NOT-RUN", "PENDING"]


def test_router_that_refuses_to_show_in_a_page_runs_in_the_first_tab(router):
    bench = router(block_frames=True)
    assert " | PASS | " in bench.run(FAST.replace("var READY_MS = 1500", "var READY_MS = 8000"))
    assert "using the tab the demo was opened from" in bench.log()


def test_reading_that_keeps_changing_is_unstable(router):
    result = router(flapping=True).run()
    assert "5G UNSTABLE" in result
    assert " | FAIL | " in result


def test_reading_that_settles_after_a_change_is_accepted(router):
    bench = router()
    bench.open_station(FAST.replace("var RECHECK_MS = 20", "var RECHECK_MS = 60"))
    bench.scan()
    assert " | PASS | " in bench.finished()


def test_green_button_is_recorded(router):
    bench = router()
    bench.open_station(FAST.replace("var GREEN_MS = 30", "var GREEN_MS = 20000"))
    bench.scan()
    bench.station.click("#rt-green", timeout=20000)
    assert "Green light PASS" in bench.finished()


def test_green_button_not_pressed_is_noted_and_the_test_goes_on(router):
    result = router().run()
    assert "Green light INFO" in result and " | PASS | " in result


def test_other_model_is_not_touched(router):
    bench = router()
    bench.open_station()
    bench.scan({**LABEL, "N": "5G16-12W-A"})
    assert "Gateway 3.2 5G" in bench.finished()
    assert bench.counts["signIns"] == 0


def test_stop_button_ends_a_waiting_test(router):
    bench = router()
    bench.page_html = UNREADY_PAGE
    bench.open_station(FAST.replace("var READY_MS = 1500", "var READY_MS = 30000"))
    bench.scan()
    bench.station.click("#rt-stop")
    assert "Stopped by the operator" in bench.finished()


def test_cut_off_run_leaves_its_log(router):
    bench = router()
    bench.page_html = UNREADY_PAGE
    bench.open_station(FAST.replace("var READY_MS = 1500", "var READY_MS = 30000"))
    bench.scan()
    bench.station.wait_for_timeout(300)
    bench.station.close()
    bench.open_station()
    assert "cut off before a result" in bench.station.inner_text("#rt-log")


def test_stats_count_real_results_only(router):
    bench = router()
    bench.run()
    assert bench.station.inner_text("#rt-count") == "1"
    assert bench.station.inner_text("#rt-rate") == "100%"
    bench.scan({**LABEL, "N": "5G16-12W-A"})
    bench.station.wait_for_timeout(300)
    assert bench.station.inner_text("#rt-count") == "1"


@pytest.mark.parametrize(
    "change",
    [{"serial": "OTHER-SERIAL"}, {"mac": "AA:BB:CC:DD:EE:FF"}, {"name": "FastMile 5G Gateway 3.2"}],
)
def test_wrong_identity_is_never_reset(router, change):
    bench = router(**change)
    assert "not reset" in bench.run()
    assert bench.counts["resets"] == 0


def test_scanning_again_does_not_reset_twice(router):
    bench = router()
    bench.run()
    assert " | PASS | " in bench.run()
    assert bench.counts["resets"] == 1


def test_hand_reset_unit_is_not_reset_again(router):
    bench = router(password="changed-by-customer")
    assert "refused the label" in bench.run()
    bench.state["password"] = LABEL["P"]
    assert " | PASS | " in bench.run()
    assert bench.counts["resets"] == 0


def test_unknown_confirm_button_is_not_guessed(router):
    bench = router(confirm="Erase everything")
    result = bench.run(FAST.replace("var WAIT_MS = 30000", "var WAIT_MS = 1000"))
    assert " | NOT TESTED | " in result
    assert "no known confirm button" in result
    assert [bench.counts[k] for k in ("resets", "cancels")] == [0, 0]


def test_changed_password_tells_operator_to_reset_and_tries_once(router):
    bench = router(password="changed-by-customer")
    assert " | NOT TESTED | " in bench.run()
    assert "Reset the unit by hand" in bench.station.inner_text("#rt-next")
    assert bench.counts["signIns"] == 1


# As on the bench: the router will not show in a frame, its address leads to /web_whw/,
# and the first tab already sits on the login page
NO_FRAMES = FAST.replace("var READY_MS = 1500", "var READY_MS = 8000").replace(
    "var REOPEN_MS = 500", "var REOPEN_MS = 5000")


def bench_router(router, **changes):
    bench = router(block_frames=True, **changes)
    bench.home = "/web_whw/"
    return bench


def test_page_already_on_the_login_box_is_used_at_once(router):
    bench = bench_router(router)
    assert " | PASS | " in bench.run(NO_FRAMES)
    assert "no login box on page" not in bench.log()


def test_logged_in_page_that_flashes_before_the_login_page_is_not_trusted(router):
    bench = bench_router(router, flash=100)
    bench.run(NO_FRAMES)
    bench.state["loggedIn"] = False
    assert " | PASS | " in bench.run()
    assert "already logged in" not in bench.log()
    assert bench.counts["signIns"] == 3


def test_router_going_back_to_login_during_the_identity_check_is_logged_in_again(router):
    bench = bench_router(router, flash=1500)
    bench.run(NO_FRAMES.replace("var SESSION_MS = 400", "var SESSION_MS = 50"))
    bench.state["loggedIn"] = False
    signs = bench.counts["signIns"]
    result = bench.run()
    assert " | PASS | " in result
    assert "The router went back to its login page. Logging in again (2 of 3)" in bench.log()
    assert bench.counts["signIns"] == signs + 1
    assert bench.counts["resets"] == 1


def test_router_lost_during_the_tests_is_logged_in_again_and_finished(router):
    bench = router()
    bench.open_station()
    bench.station.evaluate("""() => {
      const frame = document.getElementById('rt-frame');
      let done = false;
      setInterval(() => {
        const page = frame.contentWindow;
        if (!done && page.location.hash === '#/wan/cellular-status' && page.document.querySelector('#imei-card')) {
          done = true;
          fetch('/tell/logout');
          page.eval('loggedIn = false; route()');
        }
      }, 20);
    }""")
    result = bench.run()
    assert " | PASS | " in result
    assert "Logging in again (2 of 3)" in bench.log()
    assert bench.counts["resets"] == 1


def test_a_stop_during_the_tests_never_fails_the_unit(router):
    bench = router()
    bench.open_station(FAST.replace("var WAIT_MS = 30000", "var WAIT_MS = 1500"))
    bench.station.evaluate("""() => {
      const frame = document.getElementById('rt-frame');
      setInterval(() => {
        const page = frame.contentWindow;
        if (page.location.hash === '#/wan/cellular-status') page.document.getElementById('app').innerHTML = '';
      }, 20);
    }""")
    bench.scan()
    result = bench.finished()
    assert " | NOT TESTED | " in result
    assert "TESTING NOT-RUN" in bench.log()


def test_reset_page_clears_the_screen_and_leaves_the_router_alone(router):
    bench = router(signal="Searching")
    bench.run()
    resets = bench.counts["resets"]
    assert bench.station.is_enabled("#rt-clear")
    bench.station.click("#rt-clear")
    assert bench.station.inner_text("#rt-big") == "READY"
    assert bench.station.inner_text("#rt-unit") == ""
    assert not bench.station.is_visible("#rt-result")
    assert bench.station.locator("#rt-steps li.done, #rt-steps li.failed").count() == 0
    assert bench.counts["resets"] == resets
    assert " | " in bench.run()
    assert bench.counts["resets"] == resets


def test_reset_page_is_off_while_a_test_runs(router):
    bench = router()
    bench.page_html = UNREADY_PAGE
    bench.open_station(FAST.replace("var READY_MS = 1500", "var READY_MS = 30000"))
    bench.scan()
    assert bench.station.is_disabled("#rt-clear")
    bench.station.click("#rt-stop")
    bench.finished()
    assert bench.station.is_enabled("#rt-clear")


def test_a_login_the_demo_did_not_make_is_not_trusted(router):
    bench = router(loggedIn=True)
    result = bench.run()
    assert " | NOT TESTED | The router answers, but the login box never appeared." in result
    assert bench.counts["signIns"] == 0 and bench.counts["resets"] == 0


@pytest.mark.parametrize(
    "change, row",
    [
        ({"serial": "OTHER-SERIAL"}, "Serial FAIL"),
        ({"imei": "000000000000009"}, "IMEI FAIL"),
        ({"mac": "AA:BB:CC:DD:EE:FF"}, "MAC FAIL"),
        ({"name": "FastMile 5G Gateway 3.2"}, "Model FAIL"),
        ({"signal": "Disconnected"}, "5G FAIL"),
        ({"ssid": "Customer changed this"}, "Wi-Fi name FAIL"),
    ],
)
def test_wrong_unit_fails_the_right_row(router, change, row):
    result = router(**change).run()
    assert " | FAIL | " in result
    assert row in result


def test_result_to_copy_has_no_device_data(router):
    result = router(serial="OTHER-SERIAL").run()
    for secret in (LABEL["P"], LABEL["S"], LABEL["IMEI"], LABEL["KY"], "OTHER-SERIAL"):
        assert secret not in result


def test_password_is_not_left_in_the_scan_box(router):
    bench = router()
    bench.run()
    assert bench.station.input_value("#rt-scan") == ""


def stations(bench):
    bench.run()
    last = bench.saved(".json")[-1]
    assert last.suggested_filename.startswith("DO-NOT-UPLOAD-olp-result-")
    content = Path(last.path()).read_text(encoding="utf-8")
    data = json.loads(content)
    assert data["SerialNumber"] == LABEL["IMEI"]
    assert LABEL["P"] not in content and LABEL["KY"] not in content
    return [(t["TransactionType"], t["FieldKey"], t["FieldValue"]) for t in data["Transactions"]]


def test_json_has_the_three_stations_after_a_pass(router):
    assert stations(router()) == [
        ("ROUTER-DATA-WIPE", "RESULT", "PASS"),
        ("ROUTER-TESTING", "RESULT", "PASS"),
        ("ROUTER-REFURB", "RESULT", "PENDING"),
    ]


def test_json_after_a_functional_fail_keeps_the_wipe(router):
    assert [s[2] for s in stations(router(signal="Disconnected"))] == ["PASS", "FAIL-FAIL", "PENDING"]


def test_json_after_wrong_identity_shows_no_wipe(router):
    assert [s[2] for s in stations(router(serial="OTHER-SERIAL"))] == ["NOT-RUN", "FAIL-FAIL", "PENDING"]


def test_visual_check_choice_goes_in_a_new_json(router):
    bench = router()
    bench.run()
    with bench.station.expect_download() as download:
        bench.station.click("#rt-visual-pass")
    data = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert data["Transactions"][2]["FieldValue"] == "PASS"


def test_log_file_is_saved_with_every_step(router):
    bench = router()
    bench.run()
    name = bench.saved(".txt")[-1].suggested_filename
    log = bench.log()
    assert name.startswith("fastmile-demo-log-")
    for step in ("TEST: Router ready", "CLICK: Sign in", "CHECK: IMEI PASS", "CHECK: Serial PASS", "RESULT: PASS"):
        assert step in log


def test_log_is_saved_before_the_reset_button_is_pressed(router):
    bench = router()
    bench.run()
    first = Path(bench.saved(".txt")[0].path()).read_text(encoding="utf-8")
    assert "clicking Factory default > Reset" in first
    assert "RESULT" not in first


def test_log_has_no_device_data(router):
    bench = router(serial="OTHER-SERIAL")
    bench.run()
    log = bench.log()
    assert "RESULT: FAIL" in log
    for secret in (LABEL["P"], LABEL["KY"], LABEL["S"], LABEL["IMEI"], LABEL["IMEI"][-4:], "SERIAL"):
        assert secret not in log
