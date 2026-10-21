"""Render README download badges from the official website's stats.json.

Usage: python scripts/update_download_badges.py /path/to/stats.json
The scheduled workflow fetches the JSON; invalid data leaves existing badges intact.
"""

import json
import sys
from datetime import date
from html import escape
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parents[1] / ".github" / "badges"


def badge(label: str, value: str, color: str) -> str:
    left = len(label) * 7 + 14
    right = len(value) * 7 + 14
    width = left + right
    title = escape(f"{label}: {value}", quote=True)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="{title}">
  <title>{title}</title>
  <clipPath id="badge"><rect width="{width}" height="20" rx="3"/></clipPath>
  <g clip-path="url(#badge)">
    <rect width="{left}" height="20" fill="#555"/>
    <rect x="{left}" width="{right}" height="20" fill="{color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{left / 2:g}" y="14">{escape(label)}</text>
    <text x="{left + right / 2:g}" y="14">{escape(value)}</text>
  </g>
</svg>
'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    stats = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    updated = date.fromisoformat(stats["generatedAt"]).isoformat()
    badges = {}
    for key, name, label, color in (
        ("echo_agent", "runtime-downloads", "Runtime downloads", "#007ec6"),
        ("client", "desktop-downloads", "Desktop downloads", "#4c1"),
    ):
        total = stats[key]["total"]
        if type(total) is not int or not 0 <= total < 10**15:
            raise ValueError(f"{key}.total must be a non-negative integer below 10^15")
        badges[name] = badge(label, f"{total:,}", color)
    badges["stats-updated"] = badge("Stats updated", updated, "#007ec6")

    # Validate every field before touching any of the currently displayed badges.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, svg in badges.items():
        (OUTPUT_DIR / f"{name}.svg").write_text(svg, encoding="utf-8")
    print(f"Updated {len(badges)} badges from official statistics dated {updated}")


if __name__ == "__main__":
    main()
