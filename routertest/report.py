"""Write per-unit results as CSV (for data entry) and HTML (for people)."""

import csv
import html
from datetime import datetime
from pathlib import Path

from .unit import Unit

COLUMNS = ["time", "slot", "serial", "model", "check", "result", "seconds", "detail"]


def write(units: list[Unit], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rows = [
        {
            "time": stamp,
            "slot": u.slot,
            "serial": u.label.serial,
            "model": u.label.model,
            "check": r.name,
            "result": r.status,
            "seconds": r.seconds,
            "detail": r.detail,
        }
        for u in units
        for r in u.results
    ]

    csv_path = out_dir / f"run-{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    html_path = out_dir / f"run-{stamp}.html"
    html_path.write_text(_html(units, rows, stamp), encoding="utf-8")
    return csv_path, html_path


def _html(units: list[Unit], rows: list[dict], stamp: str) -> str:
    passed = sum(u.passed for u in units)
    body = "".join(
        "<tr class='{cls}'>{cells}</tr>".format(
            cls=row["result"].lower(),
            cells="".join(f"<td>{html.escape(str(row[c]))}</td>" for c in COLUMNS),
        )
        for row in rows
    )
    head = "".join(f"<th>{c}</th>" for c in COLUMNS)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Test run {stamp}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
tr.pass td:nth-child(6) {{ color: #137333; font-weight: 600; }}
tr.fail td:nth-child(6) {{ color: #c5221f; font-weight: 600; }}
tr.skip td:nth-child(6) {{ color: #5f6368; font-weight: 600; }}
</style></head><body>
<h1>Test run {stamp}</h1>
<p>{passed} of {len(units)} unit(s) passed.</p>
<table><tr>{head}</tr>{body}</table>
</body></html>
"""
