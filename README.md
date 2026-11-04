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

## Run against a real unit

1. Connect the PC directly to the unit's **yellow LAN port** with a cable.
   The PC is not connected to any other network.
2. Fill in the model's profile in `routertest/pages.py` from the real admin page
   (see `notes/README.md`). Until then `--real` refuses to run. The tool picks
   the profile from the model field of the QR label.
3. `python -m routertest.cli --real`

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
  cli.py          operator entry point
  mock_server.py  fake admin page for development
samples/          fake label data only
notes/            what to collect from the real device
```

## Data rules

- No real passwords, serials, IMEIs or customer data in this repo - ever.
  Samples are fake. Reports are git-ignored.
- Logs show secrets as `***` and identifiers shortened to the last 4 characters.
