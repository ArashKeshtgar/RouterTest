"""Where things live on each model's admin page.

Every selector the tool depends on is here, so a new model is one more profile
and the test flow does not change. The tool picks the profile from the model
field (N) of the QR label.

The FastMile models run the same web app (/web_whw/), so they share a base and
each one overrides only what differs.
"""

PROFILES = {
    "mock": {
        "login_path": "/",
        "username": "#username",
        "password": "#password",
        "submit": "#login-btn",
        "logged_in": "#overview",
        "login_error": "#error:not(:empty)",
        "open_details": "#device-card",
        "details": "#device-info",
        "fields": {
            "serial": "#serial",
            "mac": "#mac",
            "imei": "#imei",
            "firmware": "#firmware",
        },
        "reset_button": "#factory-reset",
    },
}

# TODO: fill in from DevTools (Elements tab) on a real unit.
# Do not guess - every value here must come from the real device.
_FASTMILE = {
    "login_path": "/",
    "username": "TODO",
    "password": "TODO",
    "submit": "TODO",
    # Must be real content: the overview shows empty grey placeholders for
    # about 2 seconds, and its labels arrive later from en.json.
    "logged_in": "TODO",
    "login_error": "TODO",
    # Device details has no URL of its own (still #/overview): click the device
    # on the Network map. Its Factory default > Reset button is on the same view.
    "open_details": "TODO",
    "details": "TODO",
    "fields": {
        "serial": "TODO",
        "mac": "TODO",
        "imei": "TODO",  # not on device details - find which page shows it
        "firmware": "TODO",
    },
    "reset_button": "TODO",
}

PROFILES["fastmile_12"] = {**_FASTMILE}
PROFILES["fastmile_3_2"] = {**_FASTMILE}

# Model field (N) of the QR label -> profile.
# TODO: confirm 5G16-12W-A is the Gateway 12, and add the Gateway 3.2's label value.
MODELS = {
    "5G16-12W-A": "fastmile_12",
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
