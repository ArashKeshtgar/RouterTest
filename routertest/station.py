"""Test station: a local page that runs the whole unit test with Playwright.

    python -m routertest.station                  # then open http://127.0.0.1:7360
    python -m routertest.station --show-browser   # also show the router browser window

The operator scans (or pastes) the unit's QR label into the station page. An
invisible Playwright browser does every step on the router's admin page, and the
station page shows what that browser sees, live; a click on that view is passed
on to the router page. The operator only answers what a person must: is the
light green, and does the unit look right.

Steps: label -> login -> model, serial and MAC against the label -> Factory
default > Reset and its confirm -> wait for the restart -> login again -> green
light -> IMEI, SIM, 5G and Wi-Fi, each read twice -> visual check -> report.

Every selector comes from routertest/pages.py. The page logic (a login that is
not ours, the login form lingering after Sign in, values read by their visible
label) follows what the Chrome demo in browser/ learned on real units. Nothing
leaves this PC: the station listens on 127.0.0.1 only, and the log holds no
password and only the last four characters of serials, MACs and IMEIs.
"""

import argparse
import asyncio
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request
from playwright.async_api import async_playwright

from . import pages, qr, report
from .checks import CheckResult
from .unit import Unit

PORT = 7360
VIEW = {"width": 1280, "height": 800}
# Texts a reset confirm button can have. The real dialog is not captured yet, so
# the station only clicks when exactly one new button says one of these.
CONFIRM_WORDS = {"reset", "ok", "confirm", "yes", "factory reset"}


@dataclass
class Timing:
    ready_s: float = 300  # router answering and showing its login box
    logged_in_wait_s: float = 20  # a login that is not ours, before signing it out
    login_wait_s: float = 90  # after Sign in
    action_s: float = 30  # a page part to appear
    settle_s: float = 20  # the web page answers before the login service is ready
    connect_s: float = 120  # values that move while a fresh unit connects
    recheck_s: float = 5  # between the two readings of a result
    drop_s: float = 120  # router going down after the reset is confirmed
    restart_s: float = 300  # router coming back
    poll_s: float = 1
    frame_s: float = 0.7
    answer_s: float = 900  # operator questions


class Stop(Exception):
    """The run cannot go on. Says nothing about the unit, so never a FAIL."""

    def __init__(self, why: str, next_step: str = ""):
        super().__init__(why)
        self.next_step = next_step


def extract_label(raw: str) -> qr.Label:
    """Scanners can wrap the JSON in a prefix or a suffix: read the outer {...}."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise qr.QRError("no label found in the scan")
    return qr.parse(raw[start : end + 1])


def last4(value) -> str:
    return "..." + str(value)[-4:]


def normalize_mac(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", value or "").upper()


def mask(text: str, label: qr.Label | None = None) -> str:
    """Hide label values, then every word with a digit (serials, MACs, IPs)."""
    out = str(text or "")
    if label:
        for secret in (label.ssid, label.wifi_key, label.admin_user, label.admin_password,
                       label.serial, label.mac, label.imei):
            if secret and len(secret) >= 3:
                out = out.replace(secret, "***")
    return " ".join("***" if re.search(r"\d", w) else w for w in out.split())[:300]


# Runs in the router page. Walks open shadow roots like the Chrome demo does.
READ_JS = r"""(arg) => {
  const all = [];
  const walk = (root) => root.querySelectorAll('*').forEach((el) => {
    all.push(el);
    if (el.shadowRoot) walk(el.shadowRoot);
  });
  walk(document);
  const visible = (el) => { const b = el.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
  const text = (el) => (el.textContent || '').replace(/\s+/g, ' ').trim();
  const up = (el, test) => {
    while (el) { if (el.nodeType === 1 && test(el)) return el; el = el.parentNode || el.host; }
    return null;
  };
  const leaves = all.filter((el) => !el.children.length && text(el) && visible(el) &&
    !['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName));
  const buttons = all.filter((el) => el.tagName === 'BUTTON' && visible(el));
  if (arg.kind === 'value') {
    // Details rows put the value in the next pv-text, Cellular Status rows in .right
    for (const el of leaves.filter((e) => text(e) === arg.label)) {
      const pv = up(el, (e) => e.tagName === 'PV-TEXT');
      const next = pv && pv.nextElementSibling;
      if (next && next.tagName === 'PV-TEXT' && text(next)) return text(next);
      const left = up(el, (e) => e.classList && e.classList.contains('left'));
      const right = left && left.nextElementSibling;
      if (right && right.classList.contains('right') && text(right)) return text(right);
    }
    return '';
  }
  if (arg.kind === 'after') {
    // Overview rows have no fixed shape: the value is the next text on the page
    const re = new RegExp(arg.pattern);
    for (let i = 0; i < leaves.length - 1; i++) if (re.test(text(leaves[i]))) return text(leaves[i + 1]);
    return '';
  }
  if (arg.kind === 'wifi') {
    const card = all.find((el) => el.tagName === 'PV-WIFI-CARD' && visible(el));
    const names = leaves.filter((el) => card && card.contains(el));
    return names.length ? text(names[0]) : '';
  }
  if (arg.kind === 'mark') {
    buttons.forEach((el) => el.setAttribute('data-rt-old', '1'));
    return '';
  }
  if (arg.kind === 'new') {
    // The dialog is the smallest box that holds all the new buttons; its text is
    // what the dialog says (visible text only, never script or style contents)
    const fresh = buttons.filter((el) => !el.hasAttribute('data-rt-old'));
    let box = fresh[0] || null;
    while (box && box.parentElement && !fresh.every((b) => box.contains(b))) box = box.parentElement;
    const words = box ? leaves.filter((el) => box.contains(el)).map(text).join(' | ') : '';
    return { buttons: fresh.map(text), around: words.slice(0, 400) };
  }
  return '';
}"""


class Station:
    def __init__(self, router_url: str = "http://192.168.1.1", timing: Timing | None = None,
                 out_dir: Path = Path("reports"), headless: bool = True):
        self.router = router_url.rstrip("/")
        self.t = timing or Timing()
        self.out_dir = Path(out_dir)
        self.headless = headless
        self.lock = threading.Lock()
        self.busy = False
        self.cancel = False
        self.steps: list[dict] = []
        self.lines: list[str] = []
        self.checks: list[CheckResult] = []
        self.prompt: dict | None = None
        self.prompt_id = 0
        self.result: dict | None = None
        self.unit_text = ""
        self.frame = b""
        self.frame_id = 0
        self.loop: asyncio.AbstractEventLoop | None = None
        self.browser = None
        self.context = None
        self.page = None
        self.profile: dict = {}
        self._answer: asyncio.Future | None = None
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self.log("STATION", "router at " + self.router)

    # ---------------------------------------------------------------- threads
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(60):
            raise RuntimeError("the browser did not start")

    def shutdown(self) -> None:
        if self.loop and self._stopped:
            self.loop.call_soon_threadsafe(self._stopped.set)
        if self._thread:
            self._thread.join(20)

    def _run_loop(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    _stopped: asyncio.Event | None = None

    async def _main(self) -> None:
        self._stopped = asyncio.Event()
        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=self.headless)
            frames = asyncio.create_task(self._frames())
            self._ready.set()
            await self._stopped.wait()
            frames.cancel()
            await self.browser.close()

    async def _frames(self) -> None:
        """Keep a recent picture of the router page for the station's live view."""
        while True:
            page = self.page
            if page is not None and not page.is_closed():
                try:
                    shot = await page.screenshot(type="jpeg", quality=55, timeout=5000)
                    with self.lock:
                        self.frame = shot
                        self.frame_id += 1
                except Exception:
                    pass
            await asyncio.sleep(self.t.frame_s)

    # ------------------------------------------------- called by the web page
    def scan(self, raw: str, reset: bool = True) -> tuple[bool, str]:
        with self.lock:
            if self.busy:
                return False, "A test is running."
        try:
            label = extract_label(raw)
        except qr.QRError as e:
            with self.lock:
                self.result = {"status": "SCAN AGAIN", "why": "Could not read the label: " + str(e),
                               "next": "Click the scan box and scan the QR on the back of the unit again."}
            return False, str(e)
        with self.lock:
            self.busy, self.cancel = True, False
            self.steps, self.checks, self.result, self.prompt = [], [], None, None
        asyncio.run_coroutine_threadsafe(self._run(label, reset), self.loop)
        return True, ""

    def answer(self, value: str, prompt_id: int | None = None) -> None:
        fut = self._answer
        if fut is None or (prompt_id is not None and prompt_id != self.prompt_id):
            return
        self.loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(value))

    def stop(self) -> None:
        with self.lock:
            self.cancel = True
        self.answer("stop")

    def click(self, fx: float, fy: float) -> None:
        """A click on the live view, as fractions of its width and height."""
        page = self.page
        if page is None or self.loop is None:
            return

        async def go():
            x, y = fx * VIEW["width"], fy * VIEW["height"]
            self.log("OPERATOR CLICK", "on the router view at %d,%d" % (x, y))
            await page.mouse.click(x, y)

        asyncio.run_coroutine_threadsafe(go(), self.loop)

    def state(self) -> dict:
        with self.lock:
            return {
                "busy": self.busy,
                "unit": self.unit_text,
                "steps": [dict(s) for s in self.steps],
                "log": self.lines[-250:],
                "prompt": dict(self.prompt, id=self.prompt_id) if self.prompt else None,
                "result": dict(self.result) if self.result else None,
                "frame_id": self.frame_id,
            }

    def frame_bytes(self) -> bytes:
        with self.lock:
            return self.frame

    # ---------------------------------------------------------------- records
    def log(self, kind: str, text: str) -> None:
        line = "[%s] %s: %s" % (datetime.now().strftime("%H:%M:%S"), kind, text)
        with self.lock:
            self.lines.append(line)
            self.lines = self.lines[-600:]
        print(line, flush=True)

    def step(self, name: str, status: str = "RUN", detail: str = "") -> None:
        with self.lock:
            for s in self.steps:
                if s["name"] == name:
                    s.update(status=status, detail=detail)
                    return
            self.steps.append({"name": name, "status": status, "detail": detail})

    def check(self, name: str, passed: bool, detail: str = "", status: str | None = None,
              skipped: bool = False) -> bool:
        status = status or ("SKIP" if skipped else "PASS" if passed else "FAIL")
        self.step(name, status, detail)
        self.checks.append(CheckResult(name, passed or skipped, detail, skipped=skipped))
        self.log("CHECK", name + " " + status + (" (" + detail + ")" if detail else ""))
        return passed

    async def ask(self, question: str, choices: list[str]) -> str:
        self._answer = self.loop.create_future()
        with self.lock:
            self.prompt_id += 1
            self.prompt = {"question": question, "choices": choices}
        self.log("ASK", question)
        try:
            value = await asyncio.wait_for(self._answer, self.t.answer_s)
        except asyncio.TimeoutError:
            raise Stop("No answer from the operator.", "Scan again when you are ready.")
        finally:
            with self.lock:
                self.prompt = None
            self._answer = None
        if value == "stop":
            raise Stop("Stopped by the operator.", "Scan again when you are ready.")
        self.log("ANSWER", value)
        return value

    # ------------------------------------------------------------ page helpers
    def _check_cancel(self) -> None:
        if self.cancel:
            raise Stop("Stopped by the operator.", "Scan again when you are ready.")

    def route(self) -> str:
        url = self.page.url if self.page else ""
        return url[len(self.router):] if url.startswith(self.router) else url

    async def visible(self, selector: str) -> bool:
        try:
            return await self.page.locator(selector).first.is_visible()
        except Exception:
            return False

    async def js(self, kind: str, **arg):
        try:
            return await self.page.evaluate(READ_JS, {"kind": kind, **arg}) or ""
        except Exception:
            return ""

    async def value(self, label: str) -> str:
        return await self.js("value", label=label)

    async def after(self, pattern: str) -> str:
        return await self.js("after", pattern=pattern)

    async def until(self, what: str, read, timeout_s: float):
        end = time.monotonic() + timeout_s
        while True:
            self._check_cancel()
            value = await read()
            if value:
                return value
            if time.monotonic() > end:
                raise Stop("Timed out waiting for " + what + ".", "Look at the router view, then scan again.")
            await asyncio.sleep(0.25)

    async def settled(self, read, good):
        """A fresh unit is still connecting: give a bad value time to change."""
        end = time.monotonic() + self.t.connect_s
        value = await read()
        while not good(value) and time.monotonic() < end:
            self._check_cancel()
            await asyncio.sleep(self.t.poll_s)
            value = await read()
        return value

    async def read_twice(self, read, good) -> tuple[str, bool]:
        """Two equal readings make a result; when they differ the third decides."""
        first = await self.settled(read, good)
        await asyncio.sleep(self.t.recheck_s)
        second = await read()
        if first == second:
            return second, True
        self.log("SAW", "two different readings, reading a third time")
        await asyncio.sleep(self.t.recheck_s)
        third = await read()
        return third, third == second

    def _probe(self) -> int:
        try:
            with urllib.request.urlopen(self.router + "/", timeout=3) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return 0

    async def answers(self) -> bool:
        return await asyncio.to_thread(self._probe) > 0

    async def wait_link(self, up: bool, timeout_s: float, why: str, next_step: str) -> None:
        end = time.monotonic() + timeout_s
        while True:
            self._check_cancel()
            if await self.answers() == up:
                return
            if time.monotonic() > end:
                raise Stop(why, next_step)
            await asyncio.sleep(self.t.poll_s)

    async def open(self, path: str) -> None:
        end = time.monotonic() + self.t.ready_s
        while True:
            self._check_cancel()
            try:
                await self.page.goto(self.router + path, wait_until="domcontentloaded",
                                     timeout=self.t.action_s * 1000)
                return
            except Exception:
                if time.monotonic() > end:
                    raise Stop("The router is not answering.", "Check the power, the cable and the LAN port.")
                await asyncio.sleep(self.t.poll_s * 2)

    # ------------------------------------------------------------------ steps
    async def sign_in(self, label: qr.Label, name: str) -> bool:
        """True when logged in with the label, False when the label is refused."""
        P = self.profile
        self.step(name, "RUN", "waiting for the login box")
        # Load the app fresh: from another #/ page of the same app only the hash
        # would change, and the old page would still believe it is logged in
        await self.page.goto("about:blank")
        await self.open(P["login_path"])
        end = time.monotonic() + self.t.ready_s
        in_since, outs = None, 0
        while True:
            self._check_cancel()
            if await self.visible(P["username"]):
                break
            # A logged-out unit flashes its logged-in page for under a second. One
            # that stays logged in was left so by someone else: sign it out, then
            # log in with the label so the label's own password is checked.
            if await self.visible(P["logged_in"]):
                in_since = in_since or time.monotonic()
                if time.monotonic() - in_since >= self.t.logged_in_wait_s:
                    if outs >= 2:
                        raise Stop("The unit is already logged in and did not sign out.",
                                   "Click Sign out on the router view, then scan again.")
                    outs += 1
                    self.log("SAW", "the unit was already logged in, not by this station: "
                                    "signing it out (%d)" % outs)
                    await self.page.locator(P["logged_in"]).first.click(timeout=self.t.action_s * 1000)
                    self.log("CLICK", "Sign out")
                    in_since = None
            else:
                in_since = None
            if time.monotonic() > end:
                raise Stop("The router answers, but the login box never appeared.",
                           "Look at the router view on this page.")
            await asyncio.sleep(0.5)
        self.log("SAW", "login box found, page " + self.route())
        await self.page.fill(P["username"], label.admin_user)
        await self.page.fill(P["password"], label.admin_password)
        self.log("TRYING", "filled username and password from the label")
        await self.page.locator(P["submit"]).first.click(timeout=self.t.action_s * 1000)
        self.log("CLICK", "Sign in")
        # The form stays up for a moment after Sign in, so wait for an answer
        # instead of looking at the form
        try:
            await self.page.locator(P["logged_in"] + ", " + P["login_error"]).first.wait_for(
                timeout=self.t.login_wait_s * 1000)
        except Exception:
            raise Stop("The router gave no answer after Sign in.", "Scan again when the router is up.")
        return await self.visible(P["logged_in"])

    async def open_details(self) -> None:
        P = self.profile
        if await self.visible(P["details"]):
            return
        await self.open(P["overview_path"])
        await self.page.locator(P["open_details"]).first.click(timeout=self.t.action_s * 1000)
        self.log("CLICK", "the device on the Network map, to open its details")
        await self.page.locator(P["details"]).first.wait_for(timeout=self.t.action_s * 1000)

    async def identity(self, label: qr.Label) -> bool:
        L = self.profile["labels"]
        self.step("Model", "RUN", "opening device details")
        await self.open_details()
        await self.until("the serial number on the router page", lambda: self.value(L["serial"]),
                         self.t.action_s)
        name, ok = await self.read_twice(lambda: self.value(L["model"]), bool)
        good = self.check("Model", ok and name == self.profile["model_name"],
                          name or "not found")
        serial, ok = await self.read_twice(lambda: self.value(L["serial"]), bool)
        same = ok and serial == label.serial
        good = self.check("Serial", same, "" if same else
                          "unit %s, label %s" % (last4(serial), last4(label.serial))) and good
        mac, ok = await self.read_twice(lambda: self.value(L["mac"]), bool)
        same = ok and normalize_mac(mac) == label.mac
        good = self.check("MAC", same, "" if same else
                          "unit %s, label %s" % (last4(normalize_mac(mac)), last4(label.mac))) and good
        self.check("Software", True, await self.value(L["software"]) or "not found", status="INFO")
        return good

    async def reset(self, label: qr.Label) -> bool:
        """Factory default > Reset, then its confirm. False when the operator skips."""
        P = self.profile
        self.step("Factory reset", "RUN", "pressing Factory default > Reset")
        await self.open_details()
        await self.page.locator(P["reset_button"]).first.wait_for(timeout=self.t.action_s * 1000)
        await self.js("mark")
        await self.page.locator(P["reset_button"]).first.click(timeout=self.t.action_s * 1000)
        self.log("CLICK", "Factory default > Reset")
        found = {"buttons": [], "around": ""}
        end = time.monotonic() + min(self.t.action_s, 8)
        while time.monotonic() < end and not found["buttons"]:
            await asyncio.sleep(0.3)
            found = await self.js("new") or found
        if found["buttons"]:
            await asyncio.sleep(0.3)
            found = await self.js("new") or found
        self.log("SAW", "new buttons on the router page: " +
                 (", ".join('"%s"' % mask(b) for b in found["buttons"]) or "none"))
        if found["buttons"]:
            self.log("SAW", "around them: " + (mask(found["around"], label) or "(no text)"))
        confirm = [b.strip() for b in found["buttons"] if b.strip().lower() in CONFIRM_WORDS]
        if len(confirm) == 1:
            await self.page.locator("button:not([data-rt-old])").filter(
                has_text=re.compile(r"^\s*" + re.escape(confirm[0]) + r"\s*$")).first.click(
                timeout=self.t.action_s * 1000)
            self.log("CLICK", 'confirm "%s"' % confirm[0])
        elif found["buttons"] or await self.answers():
            choice = await self.ask("Confirm the reset on the router view (click its confirm "
                                    "button there), then press Done.", ["Done", "Skip reset"])
            if choice == "Skip reset":
                self.check("Factory reset", True, "skipped by the operator", skipped=True)
                return False
        self.step("Factory reset", "RUN", "waiting for the router to restart")
        await self.wait_link(False, self.t.drop_s, "The router did not restart after the reset.",
                             "Look at the router view: was the reset confirmed?")
        self.check("Factory reset", True, "router went down")
        self.step("Restart", "RUN", "waiting for the router to come back")
        await self.wait_link(True, self.t.restart_s, "The router did not come back after the reset.",
                             "Check the power and the light.")
        await asyncio.sleep(self.t.settle_s)
        self.check("Restart", True, "back up")
        return True

    async def green(self) -> None:
        P = self.profile
        self.step("Green light", "RUN", "waiting for 5G")
        await self.open(P["overview_path"])
        signal = await self.settled(lambda: self.after(P["overview_rows"]["5g"]),
                                    lambda v: v == "Connected")
        self.log("SAW", "5G signal: " + (signal or "not found"))
        seen = await self.ask("Look at the unit. Is the light green?", ["Green", "Not green"])
        self.check("Green light", seen == "Green", "operator saw it" if seen == "Green" else "operator: not green")

    async def functional(self, label: qr.Label) -> None:
        P, L, rows = self.profile, self.profile["labels"], self.profile["overview_rows"]
        self.step("IMEI", "RUN", "opening Cellular Status")
        await self.open(P["cellular_path"])
        await self.until("the IMEI", lambda: self.value(L["imei"]), self.t.action_s)
        imei, ok = await self.read_twice(lambda: self.value(L["imei"]), bool)
        same = ok and imei == label.imei
        self.check("IMEI", same, "" if same else "gave two different answers" if not ok else
                   "unit %s, label %s" % (last4(imei), last4(label.imei)))
        sim, ok = await self.read_twice(lambda: self.value(L["sim"]), lambda v: v == "Valid")
        self.check("SIM", ok and sim == "Valid", sim or "not found")
        self.step("5G", "RUN", "opening Overview")
        await self.open(P["overview_path"])
        signal, ok = await self.read_twice(lambda: self.after(rows["5g"]), lambda v: v == "Connected")
        self.check("5G", ok and signal == "Connected", signal or "not found")
        for band in ("2.4", "5", "6"):
            pattern = rows["wifi_" + band]
            state, ok = await self.read_twice(lambda p=pattern: self.after(p), lambda v: v.startswith("Up"))
            self.check("Wi-Fi " + band, ok and state.startswith("Up"), state or "not found")
        ssid, ok = await self.read_twice(lambda: self.js("wifi"), lambda v: v == label.ssid)
        same = ok and ssid == label.ssid
        self.check("Wi-Fi name", same, "" if same else "does not match label")

    async def visual(self) -> None:
        seen = await self.ask("Visual inspection: does the unit look right?", ["Pass", "Fail"])
        self.check("Visual", seen == "Pass", "operator")

    # -------------------------------------------------------------------- run
    async def _run(self, label: qr.Label, do_reset: bool) -> None:
        started = time.monotonic()
        first = len(self.lines)
        status, why, next_step = "PASS", "", ""
        with self.lock:
            self.unit_text = "%s · serial %s · IMEI %s" % (label.model, last4(label.serial), last4(label.imei))
        self.log("TEST", "label scanned, model " + label.model)
        try:
            name = pages.MODELS.get(label.model)
            if name != "gateway_12_fastmile":
                raise Stop("Model %s is not supported by the station yet." % label.model,
                           "Test this unit by hand.")
            self.profile = pages.PROFILES[name]
            self.check("Label", True, label.model)
            if self.context:
                await self.context.close()
            # A fresh browser profile each unit: no login is left over from the last one
            self.context = await self.browser.new_context(viewport=VIEW)
            self.page = await self.context.new_page()
            if not await self.sign_in(label, "Login"):
                self.check("Login", False, "label rejected")
                raise Stop("The router refused the label login. The previous customer changed it.",
                           "Reset the unit by hand with the button on the back, then scan again.")
            self.check("Login", True)
            if not await self.identity(label):
                status, why = "FAIL", "The unit does not match the label. It was not reset."
                next_step = "Check that this QR belongs to this unit."
                return
            if not do_reset:
                self.check("Factory reset", True, "not asked for on this run", skipped=True)
            elif await self.reset(label):
                if not await self.sign_in(label, "Login after reset"):
                    self.check("Login after reset", False, "label rejected after the reset")
                    status, why, next_step = "FAIL", "The label was rejected after the reset.", "Check the unit by hand."
                    return
                self.check("Login after reset", True)
            await self.green()
            await self.functional(label)
            await self.visual()
            failed = [c.name for c in self.checks if not c.passed]
            if failed:
                status, why, next_step = "FAIL", failed[0] + " did not pass.", "Check that part of the unit."
        except Stop as e:
            status, why, next_step = "NOT TESTED", str(e), e.next_step
            self.log("SAW", "stopped: " + why)
        except Exception as e:
            first_line = (str(e).strip().splitlines() or [""])[0]
            status, why = "NOT TESTED", "%s: %s" % (type(e).__name__, mask(first_line, label))
            next_step = "Read the log, then scan again."
            self.log("SAW", "stopped: " + why)
        finally:
            seconds = round(time.monotonic() - started)
            self.log("RESULT", "%s in %ss" % (status, seconds))
            if why:
                self.log("WHY", why)
            report_path = self._write_report(label, first)
            with self.lock:
                self.result = {"status": status, "why": why, "next": next_step,
                               "seconds": seconds, "report": report_path}
                self.busy = False

    def _write_report(self, label: qr.Label, first_line: int) -> str:
        try:
            unit = Unit(slot=1, label=label, admin_url=self.router)
            unit.results = list(self.checks)
            _, html_path = report.write([unit], self.out_dir)
            with self.lock:
                lines = self.lines[first_line:]
            html_path.with_name(html_path.stem + "-log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            return str(html_path)
        except Exception as e:
            self.log("SAW", "could not write the report: " + type(e).__name__)
            return ""


PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Router test station</title>
<style>
:root{--line:#d9dde3;--soft:#f3f5f8;--text:#17212f;--muted:#5b6675;--good:#0a7a2f;--goodbg:#e4f5e9;
--bad:#b00020;--badbg:#fde8ec;--warn:#8a5a00;--warnbg:#fdf2d8;--busy:#124191;--busybg:#e6edfa}
*{box-sizing:border-box}html,body{margin:0;background:#e9ecf1;color:var(--text);font:14px Arial,sans-serif}
button{font:inherit;padding:8px 14px;border:1px solid var(--line);border-radius:6px;background:#fff;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.top{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;background:#fff;border-bottom:1px solid var(--line)}
.top b{font-size:16px}.top small{color:var(--muted);margin-left:8px}
.main{display:grid;grid-template-columns:minmax(360px,1fr) minmax(0,1.6fr);gap:14px;padding:14px}
.panel{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
label{color:var(--muted)}.row{display:flex;gap:8px;margin-top:6px}
#scan{flex:1;font:14px Consolas,monospace;padding:9px;border:2px solid var(--busy);border-radius:6px}
#unit{color:var(--muted);margin-top:8px;min-height:18px}
#card{margin-top:12px;border-radius:8px;padding:12px;background:var(--soft)}
#big{font-size:26px;font-weight:bold}#why{margin-top:4px}#next{margin-top:4px;color:var(--muted)}
#card.PASS{background:var(--goodbg);color:var(--good)}#card.FAIL{background:var(--badbg);color:var(--bad)}
#card.NOTTESTED,#card.SCANAGAIN{background:var(--warnbg);color:var(--warn)}#card.RUN{background:var(--busybg);color:var(--busy)}
#ask{display:none;margin-top:12px;padding:12px;border:2px solid var(--warn);border-radius:8px;background:var(--warnbg)}
#ask b{display:block;margin-bottom:8px}#ask button{margin-right:8px;font-size:16px;padding:10px 18px}
ol{list-style:none;padding:0;margin:12px 0 0}li{display:flex;justify-content:space-between;gap:8px;padding:6px 8px;border-bottom:1px solid var(--line)}
li .s{font-weight:bold;min-width:52px;text-align:right}li.PASS .s{color:var(--good)}li.FAIL .s{color:var(--bad)}li.RUN .s{color:var(--busy)}
li .d{color:var(--muted);flex:1;margin-left:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.view{position:relative}#view{width:100%;border:1px solid var(--line);border-radius:6px;cursor:crosshair;background:#fafafa;min-height:200px}
.view small{color:var(--muted)}
#log{margin-top:12px;height:220px;overflow:auto;background:#0f1722;color:#d6e2f0;font:11px Consolas,monospace;padding:8px;border-radius:6px;white-space:pre-wrap}
</style></head><body>
<div class="top"><div><b>Router test station</b><small>Playwright runs the router; you scan and answer.</small></div>
<div><label><input type="checkbox" id="doreset" checked> Factory reset the unit</label>
<button id="stop" disabled>Stop test</button></div></div>
<div class="main">
<div class="panel">
<label for="scan">Scan or paste the QR label (the scan starts the test)</label>
<div class="row"><input id="scan" autocomplete="off" autofocus><button id="start">Start</button></div>
<div id="unit"></div>
<div id="card"><div id="big">READY</div><div id="why">Waiting for a scan.</div><div id="next"></div></div>
<div id="ask"><b id="q"></b><div id="choices"></div></div>
<ol id="steps"></ol>
</div>
<div class="panel view">
<small>Live view of the router page. A click here is passed on to the router.</small>
<img id="view" alt="router view">
<div id="log"></div>
</div></div>
<script>
const $ = (id) => document.getElementById(id);
let frame = -1, askId = -1, busy = false;
async function post(path, body) {
  const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
  return r.json();
}
function balanced(s) { let d = 0; for (const c of s) { if (c === '{') d++; else if (c === '}') d--; } return d === 0; }
async function send() {
  const raw = $('scan').value; $('scan').value = '';
  if (!raw.trim()) return;
  await post('/scan', {raw: raw, reset: $('doreset').checked});
  poll();
}
$('scan').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); send(); } });
$('scan').addEventListener('input', () => { const v = $('scan').value; if (v.includes('}') && balanced(v.slice(v.indexOf('{')))) send(); });
$('start').onclick = send;
$('stop').onclick = () => post('/stop');
$('view').addEventListener('click', (e) => {
  const r = $('view').getBoundingClientRect();
  post('/click', {x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height});
});
function render(s) {
  busy = s.busy;
  $('stop').disabled = !s.busy; $('start').disabled = s.busy; $('scan').disabled = s.busy;
  $('unit').textContent = s.unit || '';
  const card = $('card'); let cls = '', big = 'READY', why = 'Waiting for a scan.', next = '';
  if (s.busy) { cls = 'RUN'; big = 'TESTING'; why = (s.steps.length ? s.steps[s.steps.length - 1].name : ''); }
  else if (s.result) { cls = s.result.status.replace(/ /g, ''); big = s.result.status; why = s.result.why || ''; next = s.result.next || ''; }
  card.className = cls; $('big').textContent = big; $('why').textContent = why; $('next').textContent = next;
  $('steps').innerHTML = '';
  for (const st of s.steps) {
    const li = document.createElement('li'); li.className = st.status;
    li.innerHTML = '<span></span><span class="d"></span><span class="s"></span>';
    li.children[0].textContent = st.name; li.children[1].textContent = st.detail; li.children[2].textContent = st.status;
    $('steps').appendChild(li);
  }
  const ask = $('ask');
  if (s.prompt) {
    ask.style.display = 'block';
    if (s.prompt.id !== askId) {
      askId = s.prompt.id; $('q').textContent = s.prompt.question; $('choices').innerHTML = '';
      for (const c of s.prompt.choices) {
        const b = document.createElement('button'); b.textContent = c;
        b.onclick = () => post('/answer', {value: c, id: s.prompt.id});
        $('choices').appendChild(b);
      }
    }
  } else { ask.style.display = 'none'; askId = -1; }
  const log = $('log'); const atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 20;
  log.textContent = s.log.join('\n'); if (atEnd) log.scrollTop = log.scrollHeight;
  if (s.frame_id !== frame) { frame = s.frame_id; $('view').src = '/frame.jpg?n=' + frame; }
  if (!s.busy && !s.prompt && document.activeElement !== $('scan')) $('scan').focus();
}
async function poll() { try { render(await (await fetch('/state')).json()); } catch (e) {} }
setInterval(poll, 600); poll();
</script></body></html>
"""


def create_app(station: Station) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return Response(PAGE, mimetype="text/html")

    @app.get("/state")
    def state():
        return jsonify(station.state())

    @app.get("/frame.jpg")
    def frame():
        data = station.frame_bytes()
        if not data:
            return Response(status=204)
        return Response(data, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.post("/scan")
    def scan():
        body = request.get_json(silent=True) or {}
        ok, error = station.scan(str(body.get("raw", "")), bool(body.get("reset", True)))
        return jsonify(ok=ok, error=error)

    @app.post("/answer")
    def answer():
        body = request.get_json(silent=True) or {}
        station.answer(str(body.get("value", "")), body.get("id"))
        return jsonify(ok=True)

    @app.post("/click")
    def click():
        body = request.get_json(silent=True) or {}
        try:
            x, y = float(body["x"]), float(body["y"])
        except (KeyError, TypeError, ValueError):
            return jsonify(ok=False), 400
        if 0 <= x <= 1 and 0 <= y <= 1:
            station.click(x, y)
        return jsonify(ok=True)

    @app.post("/stop")
    def stop():
        station.stop()
        return jsonify(ok=True)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Router test station")
    parser.add_argument("--router", default="http://192.168.1.1", help="router admin address")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--out", default="reports", help="where reports and logs go")
    parser.add_argument("--show-browser", action="store_true",
                        help="also show the router browser in its own window")
    args = parser.parse_args()
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    station = Station(args.router, out_dir=Path(args.out), headless=not args.show_browser)
    station.start()
    print("Station ready: open http://127.0.0.1:%d in Chrome" % args.port, flush=True)
    try:
        create_app(station).run(host="127.0.0.1", port=args.port, threaded=True)
    finally:
        station.shutdown()


if __name__ == "__main__":
    main()
