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

# The buttons have no ids, so Sign in and the error dialog are found by their
# English text. The dialog counts failed logins, and the unit seems to lock after
# about 3, so the tool only ever tries once per reset.
PROFILES["gateway_12_fastmile"] = {
    **_NOKIA,
    "username": "#username-login-value",
    "password": "#passwordLoginAria",
    "submit": 'button[type="button"]:has-text("Sign in")',
    "logged_in": 'div[role="button"].mapClickArea',
    "login_error": 'div:has-text("Invalid login credentials")',
    "open_details": 'div[role="button"].mapClickArea',
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

# Model field (N) of the QR label -> profile.
# TODO: confirm 5G16-12W-A is the Gateway 12, and add the label values of the
# Gateway 3.2 and both Vantiva models.
MODELS = {
    "5G16-12W-A": "gateway_12_fastmile",
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
