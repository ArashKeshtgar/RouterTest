"""Build a printable sheet of slot QR codes for the FastMile demo.

Each code holds the plain text "$SLT0n". The operator scans it before the unit's
QR; the demo reads the slot number, then runs the next label under that slot.

    python browser/make_slot_barcodes.py            # 4 slots -> browser/slot-barcodes.html
    python browser/make_slot_barcodes.py 8          # 8 slots

Needs segno (pure Python):  pip install segno
"""

import io
import sys
from pathlib import Path

import segno

HERE = Path(__file__).parent


def qr_svg(text: str) -> str:
    buf = io.BytesIO()
    # High error correction so a smudged or partly covered print still scans
    segno.make(text, error="h").save(buf, kind="svg", scale=7, border=2, xmldecl=False, svgns=True)
    return buf.getvalue().decode("utf-8")


def main() -> None:
    slots = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    cards = []
    for n in range(1, slots + 1):
        code = "$SLT%02d" % n
        cards.append(
            '<figure class="card">'
            + qr_svg(code)
            + '<figcaption><div class="slot">SLOT %d</div><div class="code">%s</div></figcaption>'
            % (n, code)
            + "</figure>"
        )

    html = """<!doctype html>
<meta charset="utf-8">
<title>Slot barcodes</title>
<style>
  :root { color-scheme: light; }
  body { margin: 24px; font: 14px Arial, sans-serif; color: #111; background: #fff; }
  h1 { font-size: 18px; margin: 0 0 4px; }
  p.note { color: #444; margin: 0 0 20px; max-width: 640px; }
  .sheet { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; max-width: 720px; }
  .card { margin: 0; border: 1px dashed #999; border-radius: 10px; padding: 14px;
          display: flex; flex-direction: column; align-items: center; text-align: center;
          break-inside: avoid; page-break-inside: avoid; }
  .card svg { width: 190px; height: 190px; }
  figcaption { margin-top: 8px; }
  .slot { font-size: 20px; font-weight: bold; }
  .code { font: 15px Consolas, monospace; color: #333; margin-top: 2px; }
  @media print { body { margin: 10mm; } p.note { display: none; } .card { border-color: #bbb; } }
</style>
<h1>FastMile bench slot barcodes</h1>
<p class="note">Print this page, cut along the dashed lines and tape one barcode to each bench slot.
To test a unit: scan its slot barcode first (the station shows "SLOT n" and asks for the QR),
then scan the unit's QR. Scan them while the Router test station tab is in front.</p>
<div class="sheet">
%s
</div>
""" % "\n".join(cards)

    out = HERE / "slot-barcodes.html"
    out.write_text(html, encoding="utf-8")
    print("wrote %s with %d slot codes" % (out, slots))


if __name__ == "__main__":
    main()
