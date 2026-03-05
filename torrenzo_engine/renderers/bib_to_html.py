from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from pybtex.database import parse_file
from pybtex.plugin import find_plugin

APA_STYLE = "apa7"
FALLBACK_STYLE = "unsrt"


def render_entry_to_html(entry) -> str:
    style_plugin = None
    try:
        style_plugin = find_plugin("pybtex.style.formatting", APA_STYLE)
    except Exception:
        style_plugin = None
    if style_plugin is None:
        style_plugin = find_plugin("pybtex.style.formatting", FALLBACK_STYLE)
    style = style_plugin()
    backend = find_plugin("pybtex.backends", "html")()
    formatted = style.format_entries([entry])
    parts = []
    for item in formatted:
        parts.append(item.text.render(backend))
    return "\n".join(parts)


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    bib_data = parse_file(str(input_path))
    items: list[str] = []
    for key in sorted(bib_data.entries.keys()):
        entry = bib_data.entries[key]
        try:
            html_block = render_entry_to_html(entry)
        except Exception as exc:
            return False, f"{input_path} -> {output_path} (failed on {key}: {exc})"
        items.append(f"<li>{html_block}</li>")
    output = "\n".join(["<ul>", *items, "</ul>"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    return True, f"{input_path} -> {output_path}"
