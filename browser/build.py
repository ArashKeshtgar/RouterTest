"""Turn the browser scripts into bookmarklets: one line to paste as a Chrome bookmark's URL.

    python browser/build.py
"""

import re
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).parent


def bookmarklet(source: str) -> str:
    code = re.sub(r"^\s*//.*$", "", source, flags=re.M)
    code = " ".join(line.strip() for line in code.splitlines() if line.strip())
    return "javascript:" + quote(code, safe="()'*!~-_.")


def main() -> None:
    for name in ("capture", "fastmile_demo"):
        source = (HERE / f"{name}.js").read_text(encoding="utf-8")
        (HERE / f"{name}.bookmarklet.txt").write_text(bookmarklet(source) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
