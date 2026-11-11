"""The station (routertest/station.py) against the Nokia-like mock router that the
Chrome demo tests use: same page structure as the Gateway 12 captures, a confirm
dialog after Factory default > Reset, a restart, and a working Sign Out."""

import asyncio
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from routertest.station import Station, Timing, create_app, extract_label, mask
from test_fastmile_demo import APP, CHROME_BLOCKED_PORTS, LABEL, unit as router_state

FAST = Timing(ready_s=15, logged_in_wait_s=0.6, login_wait_s=10, action_s=10, settle_s=0,
              connect_s=4, recheck_s=0.05, drop_s=10, restart_s=20, poll_s=0.1, frame_s=0.2,
              answer_s=30)


class Router:
    """The mock router: keeps its state here, so a restart or a logout sticks."""

    def __init__(self, **changes):
        self.state = router_state(**changes)
        self.counts = {"signIns": 0, "resets": 0, "reboots": 0, "cancels": 0}
        self.down = 0
        router = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                router.answer(self)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        while self.server.server_address[1] in CHROME_BLOCKED_PORTS:
            self.server.server_close()
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

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
        if "/tell/" in request.path:
            self.tell(request.path.rsplit("/", 1)[-1])
            body = b"ok"
        elif self.down:
            self.down -= 1
            request.close_connection = True
            request.connection.shutdown(socket.SHUT_RDWR)
            return
        elif request.path == "/":
            request.send_response(302)
            request.send_header("Location", "/web_whw/")
            request.send_header("Content-Length", "0")
            request.end_headers()
            return
        else:
            body = APP.replace("UNIT", json.dumps(self.state)).encode("utf-8")
        request.send_response(200)
        request.send_header("Content-Type", "text/html; charset=utf-8")
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)


def operator(question, step):
    if "light green" in question:
        return "Green"
    if "Visual" in question:
        return "Pass"
    return "Done"


def run(router, tmp_path, reset=True, answer=operator, on_prompt=None, label=LABEL):
    st = Station(router.url, timing=FAST, out_dir=tmp_path)
    st.start()
    try:
        ok, error = st.scan(json.dumps(label), reset=reset)
        assert ok, error
        answered = set()
        deadline = time.time() + 120
        while time.time() < deadline:
            s = st.state()
            prompt = s["prompt"]
            if prompt and prompt["id"] not in answered:
                answered.add(prompt["id"])
                if on_prompt:
                    on_prompt(st, prompt)
                st.answer(answer(prompt["question"], s["steps"]), prompt["id"])
            if not s["busy"] and s["result"]:
                return st, s
            time.sleep(0.05)
        raise AssertionError("the station did not finish: %s" % st.state()["log"][-5:])
    finally:
        st.shutdown()


def names(s):
    return {step["name"]: step["status"] for step in s["steps"]}


@pytest.fixture
def router():
    made = []

    def make(**changes):
        made.append(Router(**changes))
        return made[-1]

    yield make
    for r in made:
        r.server.shutdown()


def test_good_unit_runs_every_step_and_passes(router, tmp_path):
    r = router()
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    steps = names(s)
    for step in ("Login", "Model", "Serial", "MAC", "Factory reset", "Restart", "Login after reset",
                 "Green light", "IMEI", "SIM", "5G", "Wi-Fi 2.4", "Wi-Fi 5", "Wi-Fi 6",
                 "Wi-Fi name", "Visual"):
        assert steps[step] == "PASS", (step, steps)
    assert r.counts["signIns"] == 2 and r.counts["resets"] == 1
    log = "\n".join(s["log"])
    assert 'CLICK: confirm "Reset"' in log
    assert 'new buttons on the router page: "Cancel", "Reset"' in log
    assert "around them: Cancel | Reset" in log
    # After the restart the login is a fresh page load, not a left-over session
    assert "signing it out" not in log and "CLICK: Sign out" not in log


def test_log_and_report_hold_no_password_or_full_identifiers(router, tmp_path):
    r = router()
    st, s = run(r, tmp_path)
    log_files = list(Path(tmp_path).glob("*-log.txt"))
    assert len(log_files) == 1
    text = log_files[0].read_text() + "\n".join(s["log"])
    for secret in (LABEL["P"], LABEL["KY"], LABEL["S"], LABEL["IMEI"], LABEL["23S"]):
        assert secret not in text
    assert s["result"]["report"].endswith(".html")


def test_live_view_has_pictures_of_the_router_page(router, tmp_path):
    r = router()
    st, s = run(r, tmp_path)
    assert s["frame_id"] > 0
    assert st.frame_bytes()[:3] == b"\xff\xd8\xff"  # JPEG


def test_wrong_unit_fails_and_is_never_reset(router, tmp_path):
    r = router(serial="OTHER-SERIAL")
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "FAIL"
    assert "does not match the label" in s["result"]["why"]
    assert names(s)["Serial"] == "FAIL"
    assert r.counts["resets"] == 0 and r.counts["signIns"] == 1


def test_unit_left_logged_in_is_signed_out_then_tested(router, tmp_path):
    r = router(loggedIn=True)
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    assert any("signing it out (1)" in line for line in s["log"])
    assert r.counts["signIns"] == 2


def test_changed_password_is_not_tested_not_failed(router, tmp_path):
    r = router(password="changed-by-customer")
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "NOT TESTED"
    assert "refused the label login" in s["result"]["why"]
    assert r.counts["signIns"] == 1 and r.counts["resets"] == 0


def test_run_without_reset_skips_it(router, tmp_path):
    r = router()
    st, s = run(r, tmp_path, reset=False)
    assert s["result"]["status"] == "PASS"
    assert names(s)["Factory reset"] == "SKIP"
    assert r.counts["resets"] == 0 and r.counts["signIns"] == 1


def test_operator_saying_not_green_fails_the_unit(router, tmp_path):
    r = router()
    st, s = run(r, tmp_path, answer=lambda q, steps: "Not green" if "green" in q else operator(q, steps))
    assert s["result"]["status"] == "FAIL"
    assert names(s)["Green light"] == "FAIL"


def test_unknown_confirm_is_done_by_the_operator_through_the_live_view(router, tmp_path):
    # The real confirm dialog is not captured yet. When its button is not one the
    # station knows, the operator clicks it on the live view, which reaches the router.
    r = router(confirm="Erase everything")

    def click_confirm(st, prompt):
        if "Confirm the reset" not in prompt["question"]:
            return
        box = asyncio.run_coroutine_threadsafe(st.page.locator("#yes").bounding_box(), st.loop).result(10)
        st.click((box["x"] + box["width"] / 2) / 1280, (box["y"] + box["height"] / 2) / 800)
        time.sleep(0.5)

    st, s = run(r, tmp_path, on_prompt=click_confirm)
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    assert r.counts["resets"] == 1
    assert any("OPERATOR CLICK" in line for line in s["log"])


def test_scan_with_scanner_noise_is_read():
    label = extract_label("]" + json.dumps(LABEL) + "\r\n")
    assert label.serial == LABEL["S"]


def test_mask_hides_label_values_and_numbers():
    label = extract_label(json.dumps(LABEL))
    text = mask("serial %s on port 3 wifi %s" % (LABEL["S"], LABEL["ID"]), label)
    assert LABEL["S"] not in text and LABEL["ID"] not in text and "3" not in text


def test_web_page_and_bad_scan(tmp_path):
    st = Station("http://127.0.0.1:9", timing=FAST, out_dir=tmp_path)  # never started
    client = create_app(st).test_client()
    page = client.get("/").get_data(as_text=True)
    assert 'id="scan"' in page and 'id="view"' in page
    reply = client.post("/scan", json={"raw": "not a label"}).get_json()
    assert reply["ok"] is False
    state = client.get("/state").get_json()
    assert state["busy"] is False and state["result"]["status"] == "SCAN AGAIN"
    assert client.get("/frame.jpg").status_code == 204
    assert client.post("/click", json={"x": "a"}).status_code == 400
