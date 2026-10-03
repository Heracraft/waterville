"""Build the unlisted /map page from docs/code-map.html.

docs/code-map.html is the source (it is also published as an Artifact, which
supplies its own document skeleton). This writes a full HTML document plus
the page script as a separate file, because the site's Content Security Policy
allows scripts only from the site itself.

    uv run python docs/build_map.py web/static      # preview (SvelteKit static dir)
    uv run python docs/build_map.py app/web         # production (FastAPI static dir)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(__file__).with_name("code-map.html")
# The site's ledger favicon (the same data URI as the main page).
ICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' fill='%23032c3c'/%3E%3Cpath d='M0 7.5H32M7.5 0V32' "
    "stroke='%23e1dcd8' stroke-width='1'/%3E%3Ctext x='19.5' y='26' font-size='19' "
    "font-family='Georgia,serif' fill='%23e6c5b8' text-anchor='middle'%3E%C2%A7%3C/text%3E%3C/svg%3E"
)


def build(out_dir: Path) -> None:
    src = SRC.read_text()
    m = re.search(r"<script>\n?(.*?)</script>\s*$", src, re.S)
    if not m:
        raise SystemExit("no trailing <script> block in code-map.html")
    script, page = m.group(1), src[: m.start()].rstrip()
    head_end = page.index("</style>") + len("</style>")
    head, body = page[:head_end], page[head_end:].strip()
    html = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        "<meta name=\"robots\" content=\"noindex\">\n"
        f"<link rel=\"icon\" href=\"{ICON}\">\n"
        f"{head}\n</head>\n<body>\n{body}\n<script src=\"/map.js\"></script>\n</body>\n</html>\n"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "map.html").write_text(html)
    (out_dir / "map.js").write_text(script)
    print(f"wrote {out_dir / 'map.html'} and {out_dir / 'map.js'}")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "web/static"))
