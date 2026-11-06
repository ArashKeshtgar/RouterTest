# What to collect from a real unit

Goal: fill the model profiles in `routertest/pages.py` and make the mock look
like the real admin page. Collect on the test bench, one unit, ~15 minutes.

**Before sharing anything: cover or blur passwords, Wi-Fi keys, serials, IMEIs
and MACs.** Keep raw material in `notes/private/` (git-ignored).

## What the first screenshots showed (FastMile 12 and 3.2)

- Same web app on both (`/web_whw/#/overview`, same requests), so one shared
  profile with small overrides should work.
- Login is built by JavaScript (`login_web_app.cgi?nonce`, `?salt`, then the
  login request), so a browser is the right tool. A successful login answers
  HTTP 299 on both models: odd, but not an error.
- The overview shows grey placeholders for about 2 seconds, and its labels come
  from `assets/i18n/en.json` afterwards. Never read before they are filled in.
- `container_management_status` (403) and a cancelled `wan_config_glb_status`
  appear on both models on a working page. Do not treat them as a fault.
- Device details has no URL of its own; click the device on the Network map.
  It shows serial, MAC, firmware, hardware version and the reset button. The
  IMEI and SIM status are on WAN > Cellular Status.
- Four models come through. Gateway 12 FastMile (high volume) and Gateway 3.2 5G
  are Nokia; the pages call both "FastMile 5G Gateway". Vantiva and the newer
  Condo are Vantiva, with a different web app (`/login.lp`). Vantiva pages
  do not show the model name, so note it when capturing.
- Telling the captures apart: Gateway 12 has `role` attributes and
  `#factorydefaultbtn`; Gateway 3.2 has neither. Condo has `#Wi-Fi_tab` and
  `#wwan_ip`; Vantiva has `#Wireless_tab` and `#mobileWwanIp`.
- WAN > Cellular Status has its own Reset, for the data counter. It is not the
  factory reset.
- The FastMile demo saves `olp-result-*.json` with one record per OLP station, in
  the fields of OLP's history table (TransactionType, FieldKey, FieldValue,
  Status, TransactionDate). OLP lists units by IMEI, and a station's result is
  PASS or FAIL-FAIL. Nothing is sent to OLP; a real link needs IT's approval.
- Vantiva settings open as pop-ups from the dashboard cards, with no URL of
  their own. Factory reset is System Info > Configuration on both models.
- Overview also shows the SSID, Wi-Fi bands up/down and 5G/4G status, so those
  checks can be read from the page. The 12 has 2.4/5/6 GHz, the 3.2 has 2.4/5.
- The status words differ: "Not connected" on the 12, "Offline" and
  "5G link down" on the 3.2.

## 1. Screenshots
- [ ] Login page, both models
- [ ] Login page after a wrong password, both models
- [ ] Page that shows the IMEI
- [ ] Device details and Radio access with a SIM inserted and 5G working
- [ ] Confirm dialog after Factory default > Reset (do not confirm it)

## 2. Selectors (Chrome DevTools)
Right-click each item -> Inspect -> note its `id` or a unique attribute:
- [ ] Username field, password field, login button
- [ ] Something that only exists after a successful login **and** the data loaded
- [ ] The device on the Network map (click target)
- [ ] What the page shows after a wrong password (unit with a changed password)
- [ ] Factory-reset button, and any confirm dialog after it
- [ ] The text elements for serial, MAC, IMEI, firmware
- [ ] Do both models have the same selectors?

## 3. Timings (stopwatch, normal manual test)
| Step | Seconds |
|---|---|
| Power on -> green LED | |
| QR scan -> logged in | |
| SIM inserted -> internet works | |
| Factory reset | |
| Visual inspection | |
| Whole unit, start to finish | |

## 4. Other
- [ ] Label model field (N) of the Gateway 3.2; is 5G16-12W-A the Gateway 12?
- [ ] Which model is the label N 5G31-03W-B? On the bench its login page was
  `/login`, not the Gateway 12's `/web_whw/#/login`, and it has no
  `#username-login-value`. That login page is not captured yet.
- [ ] Does the 3.2's label have the same JSON QR?
- [ ] Does the unit lock the login after failed attempts? After how many?
- [ ] Does a freshly reset unit accept the label password, or force a new one?
- [ ] How long to hold the reset button; seconds until the LED is green again
- [ ] How internet is checked today (phone? website? LED?)
