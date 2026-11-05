"""A fake admin page so the tool can be developed without a real unit.

It only imitates the flow (login -> overview -> click the device -> details
and factory reset). Its HTML is
NOT the real firmware's page; the real selectors go in pages.py once they are
known.

Run:  python -m routertest.mock_server --label samples/fake_label.json

To imitate a unit whose previous customer changed the admin password, add
--customer-password something. Opening /hardware-reset then stands in for the
button on the back of the unit.
"""

import argparse
import json
from pathlib import Path

from flask import Flask, redirect, request, session

LOGIN_HTML = """<!doctype html><title>Gateway login</title>
<h1>Gateway</h1>
<form method="post" action="/">
  <input id="username" name="username" placeholder="Username">
  <input id="password" name="password" type="password" placeholder="Password">
  <button id="login-btn" type="submit">Log in</button>
  <p id="error">{error}</p>
</form>"""

OVERVIEW_HTML = """<!doctype html><title>Overview</title>
<div id="overview">
  <h1>Overview</h1>
  <a id="device-card" href="/device">{model}</a>
</div>"""

CELLULAR_HTML = """<!doctype html><title>Cellular status</title>
<p>IMEI: <span id="imei">{imei}</span></p>"""

DEVICE_HTML = """<!doctype html><title>Device info</title>
<div id="device-info">
  <h1>Device information</h1>
  <p>Model: <span id="model">{model}</span></p>
  <p>Serial number: <span id="serial">{serial}</span></p>
  <p>MAC: <span id="mac">{mac}</span></p>
  <p>Firmware: <span id="firmware">{firmware}</span></p>
  <form method="post" action="/factory-reset">
    <button id="factory-reset" type="submit">Reset</button>
  </form>
</div>"""


def create_app(
    label: dict,
    firmware: str = "MOCK-1.0.0",
    identity_override: dict | None = None,
    customer_password: str | None = None,
) -> Flask:
    """identity_override lets tests simulate a unit whose label doesn't match.
    customer_password is the admin password a previous customer left on the unit.
    """
    app = Flask(__name__)
    app.secret_key = "mock-only"
    state = {
        "password": customer_password or label["P"],
        "software_resets": 0,
        "hardware_resets": 0,
    }
    app.config["STATE"] = state
    device = {
        "model": label["N"],
        "serial": label["S"],
        # Real pages usually show MAC with colons; the tool must normalize it
        "mac": ":".join(label["23S"][i:i + 2] for i in range(0, 12, 2)),
        "imei": label["IMEI"],
        "firmware": firmware,
        **(identity_override or {}),
    }

    @app.route("/", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if (request.form.get("username") == label["U"]
                    and request.form.get("password") == state["password"]):
                session["auth"] = True
                return redirect("/overview")
            return LOGIN_HTML.format(error="Wrong username or password"), 401
        return LOGIN_HTML.format(error="")

    @app.route("/overview")
    def overview():
        if not session.get("auth"):
            return redirect("/")
        return OVERVIEW_HTML.format(**device)

    @app.route("/cellular")
    def cellular():
        if not session.get("auth"):
            return redirect("/")
        return CELLULAR_HTML.format(**device)

    @app.route("/device")
    def device_info():
        if not session.get("auth"):
            return redirect("/")
        return DEVICE_HTML.format(**device)

    @app.route("/factory-reset", methods=["POST"])
    def factory_reset():
        if not session.get("auth"):
            return redirect("/")
        state["software_resets"] += 1
        state["password"] = label["P"]
        session.clear()
        return redirect("/")

    @app.route("/hardware-reset")
    def hardware_reset():
        state["hardware_resets"] += 1
        state["password"] = label["P"]
        session.clear()
        return "Unit reset. Back to the tool and press Enter."

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fake gateway admin page")
    parser.add_argument("--label", default="samples/fake_label.json")
    # 7357 is outside the port ranges Windows/Hyper-V commonly reserves
    parser.add_argument("--port", type=int, default=7357)
    parser.add_argument("--customer-password", help="imitate a changed admin password")
    args = parser.parse_args()
    label = json.loads(Path(args.label).read_text(encoding="utf-8"))
    try:
        app = create_app(label, customer_password=args.customer_password)
        app.run(host="127.0.0.1", port=args.port)
    except OSError as e:
        raise SystemExit(
            f"Cannot use port {args.port} ({e}). Pick another with --port "
            "and pass the same URL to the CLI with --url."
        )


if __name__ == "__main__":
    main()
