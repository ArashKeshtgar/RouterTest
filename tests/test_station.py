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

FAST = Timing(login_try_s=2, relogin_s=20, ready_s=15, logged_in_wait_s=0.6, login_wait_s=10, action_s=10, settle_s=0,
              connect_s=4, recheck_s=0.05, drop_s=10, restart_s=20, poll_s=0.1, frame_s=0.2,
              answer_s=30)


class Router:
    """The mock router: keeps its state here, so a restart or a logout sticks."""

    def __init__(self, **changes):
        self.state = router_state(**changes)
        self.counts = {"signIns": 0, "resets": 0, "reboots": 0, "cancels": 0, "ignored": 0, "skips": 0}
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
            # Back up, the unit opens its start page (5G shown, no login) as the real one
            self.state["guest"] = True
            self.state["ignoreSignIns"] = self.state.get("ignoreAfterRestart", 0)
            self.state["askNewPassword"] = self.state.get("newPasswordAfterRestart", False)
        elif name == "ignored":
            self.counts["ignored"] += 1
            self.state["ignoreSignIns"] -= 1
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
                 "IMEI", "SIM", "5G", "Wi-Fi 2.4", "Wi-Fi 5", "Wi-Fi 6",
                 "Wi-Fi name", "Visual"):
        assert steps[step] == "PASS", (step, steps)
    # One login before the reset, one after it for SIM (Cellular Status is behind it)
    assert r.counts["signIns"] == 2 and r.counts["resets"] == 1
    # SIM and 5G are tested after the reset: the station waits for the unit to come
    # back and connect 5G (the green light), logs in and reads SIM: no question
    order = [st["name"] for st in s["steps"]]
    assert order[-5:] == ["Factory reset", "Restart", "5G", "Login after reset", "SIM"]
    assert "Green light" not in steps
    assert order.index("Wi-Fi name") < order.index("Factory reset")
    # A stopwatch on every step, and the step times add up to the total
    assert all("secs" in step for step in s["steps"])
    assert abs(sum(step["secs"] for step in s["steps"]) - s["result"]["seconds"]) <= len(s["steps"])
    log = "\n".join(s["log"])
    assert "TIME: Total" in log and "RESULT: PASS, total time" in log
    assert 'CLICK: confirm "Reset"' in log
    assert 'new buttons on the router page: "Cancel", "Reset"' in log
    assert "around them: Cancel | Reset" in log
    # After the restart the login is a fresh page load, not a left-over session
    assert "signing it out" not in log and "CLICK: Sign out" not in log


def test_logged_out_unit_on_prelogin_is_not_taken_for_logged_in(router, tmp_path):
    # The bench unit on 2026-11-11: #/login lands on /prelogin, whose side menu
    # holds "Sign in". The station used to sign that "out" twice and give up;
    # Maintenance on the side menu is what opens the login box.
    r = router(guest=True)
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    log = "\n".join(s["log"])
    assert "CLICK: Maintenance on the side menu" in log
    assert "signing it out" not in log and "CLICK: Sign out" not in log
    assert r.counts["signIns"] == 2


def test_confirm_dialog_without_button_elements_is_still_confirmed(router, tmp_path):
    # Bench 2026-11-11: after Reset the station saw "new buttons: none", because it
    # only looked for <button>. A role=button confirm must be found and pressed.
    r = router(divDialog=True)
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    log = "\n".join(s["log"])
    assert 'CLICK: confirm "Reset"' in log
    assert r.counts["resets"] == 1
    assert list(Path(tmp_path).glob("*-reset-dialog.png"))


def test_reset_confirm_in_the_browser_box_is_answered_without_asking(router, tmp_path):
    # The real Gateway 12 (doFactoryDefault in its app) asks with window.confirm.
    # Playwright pressed Cancel on it by itself, so nothing ever happened on the bench.
    r = router(nativeConfirm=True)
    asked = []
    st, s = run(r, tmp_path, on_prompt=lambda st, p: asked.append(p["question"]))
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    assert r.counts["resets"] == 1 and r.counts["cancels"] == 0
    assert not [q for q in asked if "confirm" in q.lower()]
    log = "\n".join(s["log"])
    assert "SAW: browser confirm box" in log
    assert "CLICK: OK on the factory reset question" in log


def test_a_stopped_test_leaves_no_step_running(router, tmp_path):
    def stop_at_first_question(st, prompt):
        st.stop()

    r = router(nativeConfirm=True)
    st, s = run(r, tmp_path, on_prompt=stop_at_first_question)
    assert s["result"]["status"] == "NOT TESTED"
    assert "RUN" not in {step["status"] for step in s["steps"]}
    assert any(step["status"] == "STOPPED" for step in s["steps"])


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
    # Without a reset, SIM and 5G are still tested, on the logged-in unit
    assert names(s)["SIM"] == "PASS" and names(s)["5G"] == "PASS"


def test_operator_saying_the_unit_looks_wrong_fails_it_and_it_is_not_reset(router, tmp_path):
    r = router()
    st, s = run(r, tmp_path, answer=lambda q, steps: "Fail" if "Visual" in q else operator(q, steps))
    assert s["result"]["status"] == "FAIL"
    assert names(s)["Visual"] == "FAIL" and r.counts["resets"] == 0


def test_the_only_question_is_the_visual_check(router, tmp_path):
    r = router(nativeConfirm=True)
    asked = []
    st, s = run(r, tmp_path, on_prompt=lambda st, p: asked.append(p["question"]))
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    assert len(asked) == 1 and "Visual" in asked[0]


def test_sign_in_with_no_answer_after_the_restart_is_sent_again(router, tmp_path):
    # Bench 2026-11-11, twice: 4 s after the unit came back, Sign in got no answer
    # for 90 s. The login service is not ready yet; a fresh Sign in works later.
    r = router(nativeConfirm=True, ignoreAfterRestart=2)
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    assert r.counts["ignored"] == 2 and r.counts["signIns"] == 2
    log = "\n".join(s["log"])
    assert "signing in again" in log and "CLICK: Sign in (try 3)" in log
    assert names(s)["Login after reset"] == "PASS" and names(s)["SIM"] == "PASS"
    assert list(Path(tmp_path).glob("*-login-no-answer.png"))


def test_new_password_box_after_the_reset_is_skipped(router, tmp_path):
    r = router(nativeConfirm=True, newPasswordAfterRestart=True)
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "PASS", s["log"][-8:]
    assert r.counts["skips"] == 1
    log = "\n".join(s["log"])
    assert "a box after Sign in: Change password" in log and 'CLICK: "Skip" on that box' in log


def test_sign_in_that_never_answers_stops_with_a_picture(router, tmp_path):
    r = router(nativeConfirm=True, ignoreAfterRestart=99)
    st, s = run(r, tmp_path)
    assert s["result"]["status"] == "NOT TESTED"
    assert "no answer after Sign in" in s["result"]["why"]
    assert list(Path(tmp_path).glob("*-login-no-answer.png"))


def test_unknown_confirm_stops_without_asking_the_operator(router, tmp_path):
    # The operator is never asked to confirm the reset: a confirm the station does
    # not know stops the test, with a picture of the page for working it out
    r = router(confirm="Erase everything")
    asked = []
    st, s = run(r, tmp_path, on_prompt=lambda st, p: asked.append(p["question"]))
    assert s["result"]["status"] == "NOT TESTED"
    assert "no confirm" in s["result"]["why"]
    assert r.counts["resets"] == 0 and not [q for q in asked if "confirm" in q.lower()]
    assert list(Path(tmp_path).glob("*-reset-dialog.png"))


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
