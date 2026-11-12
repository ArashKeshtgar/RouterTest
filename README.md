# RouterTest

Demo tool that automates the functional test of 5G gateway units
(Nokia FastMile 5G Gateway 12 and 3.2), which today is done by hand: scan the label QR, log in to
the admin page, check the unit, factory-reset it, record the result.

**Status: phase 1 - runs against a mock admin page. Not yet validated on a real unit.**

## What it does today

| Step | Status |
|---|---|
| Read the QR label (barcode scanner types JSON) and validate it | done |
| Log in to the admin page automatically | done (mock) |
| Read serial / MAC / IMEI / firmware and compare with the label | done (mock) |
| CSV + HTML report with PASS/FAIL and timings per check | done |
| Wi-Fi broadcast check | phase 2 |
| SIM / 5G internet check | phase 2 |
| Password changed by previous customer: operator resets by hand, tool continues | done (mock) |
| Factory reset (skipped if the operator already reset the unit) | done (mock) |
| Several units at once (one interface per unit) | phase 3 |
| Visual inspection | stays manual |

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Run against the mock (no device needed)

Terminal 1 - fake admin page on http://127.0.0.1:7357:

```bash
python -m routertest.mock_server
```

Terminal 2 - the tool. Paste or scan the QR JSON when asked
(`samples/fake_label.json` is a fake one):

```bash
python -m routertest.cli --mock
```

Add `--show-browser` to watch it work. Reports go to `reports/` (git-ignored).

To see a unit whose admin password was changed, start the mock with
`--customer-password something`. When the tool asks for the manual reset, open
http://127.0.0.1:7357/hardware-reset (it stands in for the button on the back),
then press Enter.

## Run against a real unit: the station

The station is a local page that runs the whole test with Playwright. Supported
model: Gateway 12 FastMile (label N `5G31-03W-B`).

1. Connect the PC to the unit's LAN port with a cable.
2. Start it, then open http://127.0.0.1:7360 in Chrome:

   ```bash
   python3 -m routertest.station
   ```

3. Scan (or paste) the unit's QR label into the station's scan box.

Playwright then logs in with the label, checks model, serial and MAC, presses
Factory default > Reset and answers its confirm box itself, waits for the unit to go down, logs in again as soon as the login box is back,
and reads IMEI, SIM, 5G and the three Wi-Fi bands twice each. The operator only
answers two questions on the page: is the light green, and does the unit look
right. The right half of the page is a live view of the router page Playwright
is on; a click there is passed on to the router. The Gateway 12 asks to confirm the
reset with the browser's own confirm box; the station answers OK to that one
question only, and Cancel to any other box. Every step has a stopwatch, and the
log ends with each step's time and the total.

Untick "Factory reset the unit" to test without a reset. A unit left logged in
by someone else is signed out after 20 seconds and logged in with the label.
Reports and a masked log go to `reports/` (git-ignored). `--show-browser` also
opens the router browser in its own window; `--router` changes the address.

The Chrome bookmarklet in `browser/` does the same test without installing
anything, but it needs the router page open and the scan aimed at the right tab.

## Tests

```bash
python -m pytest
```

Runs the full login + identity flow against the mock in a headless browser,
including changed-password, unreachable-unit and label-mismatch cases.

## Layout

```
routertest/
  qr.py           parse + validate the label JSON, mask secrets for logs
  unit.py         one unit under test (label, admin URL, network interface, results)
  pages.py        every selector the tool relies on, one profile per model
  admin.py        browser actions on the admin page (Playwright)
  checks.py       test steps -> PASS/FAIL + time + reason
  report.py       CSV and HTML report
  cli.py          mock runs from the terminal
  station.py      the station: local page + Playwright, full test on a real unit
  mock_server.py  fake admin page for development
browser/          page capture and FastMile demo that run inside Chrome, no install (build.py makes the bookmarklets)
samples/          fake label data only
notes/            what to collect from the real device
```

## Data rules

- No real passwords, serials, IMEIs or customer data in this repo - ever.
  Samples are fake. Reports are git-ignored.
- Logs show secrets as `***` and identifiers shortened to the last 4 characters.
