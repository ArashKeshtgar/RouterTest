"""Parse the JSON label that the barcode scanner types in from the unit's QR code."""

import json
import re
from dataclasses import dataclass

REQUIRED_KEYS = ("ID", "KY", "U", "P", "S", "23S", "N", "PN", "IMEI")


class QRError(ValueError):
    pass


@dataclass(frozen=True)
class Label:
    ssid: str
    wifi_key: str
    admin_user: str
    admin_password: str
    serial: str
    mac: str
    model: str
    part_number: str
    imei: str

    def masked(self) -> dict:
        """Safe-to-log view: secrets hidden, identifiers shortened."""
        return {
            "ssid": self.ssid,
            "serial": mask(self.serial),
            "mac": mask(self.mac),
            "imei": mask(self.imei),
            "model": self.model,
            "part_number": self.part_number,
            "admin_password": "***",
            "wifi_key": "***",
        }


def mask(value: str, keep: int = 4) -> str:
    return "*" * max(len(value) - keep, 0) + value[-keep:]


def parse(raw: str) -> Label:
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise QRError(f"QR is not valid JSON: {e}") from None

    missing = [k for k in REQUIRED_KEYS if not data.get(k)]
    if missing:
        raise QRError(f"QR is missing fields: {', '.join(missing)}")

    imei = str(data["IMEI"])
    if not re.fullmatch(r"\d{15}", imei):
        raise QRError("IMEI must be 15 digits")

    mac = str(data["23S"]).upper().replace(":", "").replace("-", "")
    if not re.fullmatch(r"[0-9A-F]{12}", mac):
        raise QRError("MAC (23S) must be 12 hex characters")

    return Label(
        ssid=data["ID"],
        wifi_key=data["KY"],
        admin_user=data["U"],
        admin_password=data["P"],
        serial=data["S"],
        mac=mac,
        model=data["N"],
        part_number=data["PN"],
        imei=imei,
    )
