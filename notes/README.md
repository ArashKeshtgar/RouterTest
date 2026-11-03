# What to collect from a real unit

Goal: fill the `real` profile in `routertest/pages.py` and make the mock look
like the real admin page. Collect on the test bench, one unit, ~15 minutes.

**Before sharing anything: cover or blur passwords, Wi-Fi keys, serials, IMEIs
and MACs.** Keep raw material in `notes/private/` (git-ignored).

## 1. Screenshots
- [ ] Login page
- [ ] Page that shows serial / MAC / IMEI / firmware
- [ ] Page that shows SIM / cellular status and signal
- [ ] Wi-Fi settings page (SSID shown)
- [ ] Where the factory-reset button is (do not need to click it)

## 2. Selectors (Chrome DevTools)
Right-click each item -> Inspect -> note its `id` or a unique attribute:
- [ ] Username field, password field, login button
- [ ] Something that only exists after a successful login
- [ ] The text elements for serial, MAC, IMEI, firmware

## 3. Network (DevTools -> Network tab, during login)
- [ ] URL of the login request (e.g. `/login.cgi`) - **not** its contents
- [ ] Is the login page a normal form, or does JavaScript build the request?

## 4. Timings (stopwatch, normal manual test)
| Step | Seconds |
|---|---|
| Power on -> green LED | |
| QR scan -> logged in | |
| SIM inserted -> internet works | |
| Factory reset | |
| Visual inspection | |
| Whole unit, start to finish | |

## 5. Other
- [ ] Firmware version shown on the page
- [ ] How internet is checked today (phone? website? LED?)
