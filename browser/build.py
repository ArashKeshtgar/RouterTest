"""Turn capture.js into a bookmarklet: one line to paste as a Chrome bookmark's URL.

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
    source = (HERE / "capture.js").read_text(encoding="utf-8")
    (HERE / "capture.bookmarklet.txt").write_text(bookmarklet(source) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
