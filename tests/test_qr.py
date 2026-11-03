import json

import pytest

from routertest import qr

GOOD = {"ID": "NOKIA-TEST", "KY": "k", "U": "admin", "P": "p", "S": "FAKE00000001",
        "23S": "0011223344aa", "N": "5G16-12W-A", "PN": "TEST", "IMEI": "000000000000001"}


def test_parses_scanner_input_with_whitespace():
    label = qr.parse("  " + json.dumps(GOOD) + "\r\n")
    assert label.serial == "FAKE00000001"
    assert label.mac == "0011223344AA"


def test_rejects_non_json():
    with pytest.raises(qr.QRError, match="not valid JSON"):
        qr.parse("FAKE00000001")


def test_rejects_missing_fields():
    data = dict(GOOD)
    del data["IMEI"]
    with pytest.raises(qr.QRError, match="IMEI"):
        qr.parse(json.dumps(data))


def test_rejects_bad_imei():
    with pytest.raises(qr.QRError, match="15 digits"):
        qr.parse(json.dumps({**GOOD, "IMEI": "123"}))


def test_masked_view_hides_secrets():
    m = qr.parse(json.dumps(GOOD)).masked()
    assert m["admin_password"] == "***"
    assert m["wifi_key"] == "***"
    assert m["imei"].endswith("0001") and m["imei"].startswith("*")
