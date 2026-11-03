"""Where things live on each admin page.

Every selector the tool depends on is here, so when the real firmware's page
differs from the mock, only this file changes.
"""

PROFILES = {
    "mock": {
        "login_path": "/",
        "username": "#username",
        "password": "#password",
        "submit": "#login-btn",
        "logged_in": "#device-info",
        "info_path": "/device",
        "fields": {
            "serial": "#serial",
            "mac": "#mac",
            "imei": "#imei",
            "firmware": "#firmware",
        },
    },
    # TODO: fill in from screenshots / DevTools of the real admin page.
    # Do not guess - every value here must come from the real device.
    "real": {
        "login_path": "/",
        "username": "TODO",
        "password": "TODO",
        "submit": "TODO",
        "logged_in": "TODO",
        "info_path": "TODO",
        "fields": {
            "serial": "TODO",
            "mac": "TODO",
            "imei": "TODO",
            "firmware": "TODO",
        },
    },
}


def get(name: str) -> dict:
    profile = PROFILES[name]
    if "TODO" in repr(profile):
        raise NotImplementedError(
            f"Page profile '{name}' still has TODO selectors - "
            "fill them in from the real admin page first (see notes/README.md)."
        )
    return profile
