from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from markdown_it import MarkdownIt


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    tags = context.get("tags", {})
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    raw = input_path.read_text(encoding="utf-8")

    # simple tag replacement pre-pass
    for key, value in tags.items():
        raw = raw.replace(f"{{{{{key}}}}}", value)

    html_body = md.render(raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_body, encoding="utf-8")
    return True, f"{input_path} -> {output_path}"
