"""Where things live on each model's admin page.

Every selector the tool depends on is here, so a new model is one more profile
and the test flow does not change. The tool picks the profile from the model
field (N) of the QR label.

The FastMile models run the same web app (/web_whw/), so they share a base and
each one overrides only what differs. Vantiva units run a different one.
"""

PROFILES = {
    "mock": {
        "login_path": "/",
        "username": "#username",
        "password": "#password",
        "submit": "#login-btn",
        "logged_in": "#overview",
        "login_error": "#error:not(:empty)",
        "overview_path": "/overview",
        "open_details": "#device-card",
        "details": "#device-info",
        "fields": {
            "serial": "#serial",
            "mac": "#mac",
            "firmware": "#firmware",
        },
        "cellular_path": "/cellular",
        "cellular_fields": {"imei": "#imei"},
        "reset_button": "#factory-reset",
    },
}

def _detail(label: str) -> str:
    """Details values have no ids; each one follows its label."""
    return f'div.text > pv-text:has(div:text-is("{label}")) + pv-text > div'


# From page captures of real units. Do not guess - every value here must come
# from the real device. TODO values are the ones not captured yet.
_NOKIA = {
    "login_path": "/web_whw/#/login",
    "username": "TODO",
    "password": "TODO",
    "submit": "TODO",
    # Must be real content: the overview shows empty grey placeholders for
    # about 2 seconds, and its labels arrive later from en.json.
    "logged_in": "TODO",
    "login_error": "TODO",
    "overview_path": "/web_whw/#/overview",
    # Device details has no URL of its own (still #/overview): click the device
    # on the Network map. Its Factory default > Reset button is on the same view.
    "open_details": "TODO",
    "details": "pv-text:has(div:text-is(\"Serial number\"))",
    "fields": {
        "serial": _detail("Serial number"),
        "mac": _detail("MAC address"),
        "firmware": _detail("Software version"),
    },
    "cellular_path": "/web_whw/#/wan/cellular-status",
    "cellular_fields": {"imei": "#imei-card div.right > pv-text > div"},
    # Stays TODO until its confirm dialog is captured. The real run refuses until
    # it is set. The Chrome demo in browser/ does the reset on Gateway 12 already.
    "reset_button": "TODO",
}

# On a logged-out unit the sidenav and the map show for a moment before the app
# goes to its login page, so one sighting of them does not prove a login.
# The buttons have no ids, so Sign in and the error dialog are found by their
# English text. The dialog counts failed logins, and the unit seems to lock after
# about 3, so the tool only ever tries once per reset.
PROFILES["gateway_12_fastmile"] = {
    **_NOKIA,
    # Two builds of the web app (bench 2026-11-12): one with ids on the login
    # fields, one ("(c) 2021 Nokia" at the bottom) with only name="value" on them
    "username": ':is(#username-login-value, input[name="value"][type="text"])',
    "password": ':is(#passwordLoginAria, input[name="value"][type="password"])',
    "submit": 'button[type="button"]:has-text("Sign in")',
    # A logged-out unit opens on /prelogin (also when asked for #/login): the
    # overview without a login box, and div.sidenav-logout holds "English" and a
    # "Sign in" button (seen on the bench 2026-11-11). So that div alone does not
    # mean logged in: only its button that is not Sign in does. The logged-in
    # button's own text is not captured yet.
    # The 2021 build has no role on that button: its sign-out text is looked for
    # instead (not captured yet, so both spellings)
    "logged_in": ':is(div.sidenav-logout [role="button"]:not(:has-text("Sign in")), '
                 'div.sidenav-logout pv-text:text-matches("^\\s*(sign|log) ?out\\s*$", "i"))',
    # Maintenance on the side menu leads a logged-out unit to #/login with the
    # login box (bench 2026-11-11, the way the operators do it)
    # The 2021 build has it as a menu group (div.side-icon, no role), which also
    # leads to #/login
    "sign_in_link": ':is(div[role="link"]:has(> a:text-is("Maintenance")), '
                    'li div.side-icon:has(> a:text-is("Maintenance")))',
    # On a narrow window the side menu is behind this button
    "menu": '[name="burger_menu"]',
    # After a factory reset the app can ask for a new password on the login page
    # itself (firstLoginChangePassword in its code), in a pv-dialog with a skip
    "first_login_dialog": "pv-dialog:visible",
    "login_error": 'div:has-text("Invalid login credentials")',
    "open_details": 'div[role="button"].mapClickArea',
    # Seen on the bench by the Chrome demo before asking the operator to press it.
    # Its confirm dialog is still not captured: the station records it on its
    # first real reset and asks the operator if it cannot tell the confirm button.
    "reset_button": "#factorydefaultbtn button",
    # Used by the station (routertest/station.py), read by visible label text
    "model_name": "FastMile 5G Gateway 12",
    "labels": {
        "model": "Device name",
        "serial": "Serial number",
        "mac": "MAC address",
        "software": "Software version",
        "imei": "IMEI",
        "sim": "Status",
        # Rows that only a SIM in the slot fills. A SIM pulled while the unit is on
        # still shows Status "Valid" until a restart (bench 2026-11-12)
        "sim_operator": "SIM",
        "imsi": "IMSI",
        "iccid": "ICCID",
    },
    # Overview rows: the value is the next text after the row's name
    "overview_rows": {
        "5g": r"^5G\+? Signal$",
        "wifi_2.4": r"^WiFi 2\.4 GHz$",
        "wifi_5": r"^WiFi 5 GHz$",
        "wifi_6": r"^WiFi 6 GHz$",
    },
}
# Same app in an older build: its elements have no role attributes or button
# ids, so the Gateway 12's login and map selectors do not carry over. Its login
# page and Network map are not captured yet.
PROFILES["gateway_3_2_5g"] = {**_NOKIA, "logged_in": "div.sidenav-logout"}

# A different make and web app (footer says Vantiva). There are two models,
# Vantiva and the newer Condo. Their dashboard cards and pop-ups match. Card
# ids can hold a space, so they cannot be written as #System Info.
_VANTIVA = {
    "logged_in": "#System_Info_tab",
    "overview_path": "/",
    # Serial and MAC are likely on the Global Information tab: not captured yet.
    "open_details": '[id="System Info"]',
    "details": "#system-info-modal",
    "fields": {"serial": "TODO", "mac": "TODO", "firmware": "TODO"},
    "cellular_path": "TODO",
    "cellular_fields": {"imei": "TODO"},
    "reset_button": "TODO",
}
PROFILES["vantiva"] = {
    **_VANTIVA,
    "login_path": "/login.lp",
    "username": "#srp_username",
    "password": "#srp_password",
    "submit": "#sign-me-in",
    "login_error": "#erroruserpass",
}
# Its login page is not captured yet.
PROFILES["condo"] = {
    **_VANTIVA,
    "login_path": "TODO",
    "username": "TODO",
    "password": "TODO",
    "submit": "TODO",
    "login_error": "TODO",
}

# Model field (N) of the QR label -> profile. These two come from public listings
# (FCC, Wi-Fi Alliance, manuals), not from the labels on the bench.
# TODO: confirm both on real labels, and add the label values of both Vantiva models.
MODELS = {
    "5G31-03W-B": "gateway_12_fastmile",
    "5G16-12W-A": "gateway_3_2_5g",
}


class UnknownModel(ValueError):
    pass


def get(name: str) -> dict:
    profile = PROFILES[name]
    if "TODO" in repr(profile):
        raise NotImplementedError(
            f"Page profile '{name}' still has TODO selectors - "
            "fill them in from the real admin page first (see notes/README.md)."
        )
    return profile


def for_model(model: str) -> dict:
    if model not in MODELS:
        raise UnknownModel(f"model {model} has no profile yet")
    return get(MODELS[model])
