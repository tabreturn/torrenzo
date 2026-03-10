from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Dict, Tuple

from docx import Document
from lxml import html as lxml_html

from .md_to_pdf import apply_tags
from .md_to_html import sanitize_html_attributes, strip_html_wrapper


HEADING_PREFIX = "heading "


def paragraph_to_html(p) -> str:
    pieces: list[str] = []
    for run in p.runs:
        text = run.text or ""
        if not text:
            continue
        escaped = escape(text)
        if run.bold:
            escaped = f"<strong>{escaped}</strong>"
        if run.italic:
            escaped = f"<em>{escaped}</em>"
        if run.underline:
            escaped = f"<u>{escaped}</u>"
        pieces.append(escaped)
    html_text = "".join(pieces)
    style = p.style.name.lower() if p.style and p.style.name else ""
    if style.startswith(HEADING_PREFIX):
        level = style.removeprefix(HEADING_PREFIX).strip()
        if level.isdigit():
            return f"<h{level}>{html_text}</h{level}>"
    if "title" in style:
        return f"<h1>{html_text}</h1>"
    return f"<p>{html_text}</p>"


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str, list[str]]:
    tags = context.get("tags", {})
    document = Document(str(input_path))
    raw_fragments: list[str] = []
    warnings: list[str] = []

    for block in document.paragraphs:
        raw_fragments.append(paragraph_to_html(block))

    raw_html = "\n".join(raw_fragments)
    raw_html, tag_warnings = apply_tags(raw_html, tags)
    warnings.extend(tag_warnings)

    try:
        raw_html = sanitize_html_attributes(raw_html)
        raw_html = strip_html_wrapper(raw_html)
    except Exception:
        pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(raw_html, encoding="utf-8")
    return True, f"{input_path} -> {output_path}", warnings
