from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Dict, Tuple

from docx import Document
from premailer import transform
from lxml import html as lxml_html

from .md_to_pdf import apply_tags
from .md_to_html import (
    collect_citation_numbers,
    load_bibliography,
    load_module_css,
    render_references,
    replace_citations,
    sanitize_html_attributes,
    strip_html_wrapper,
    substitute_css_variables,
)


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

    bib_entries = load_bibliography(input_path)
    citation_numbers, ordered_keys, missing_keys = collect_citation_numbers(raw_html, bib_entries)
    if citation_numbers:
        raw_html = replace_citations(raw_html, citation_numbers)
    if ordered_keys:
        references = render_references(ordered_keys, bib_entries)
        if references:
            raw_html = f"{raw_html}\n{references}"

    css_text = load_module_css(input_path)
    css_text = substitute_css_variables(css_text)
    if css_text.strip():
        try:
            raw_html = transform(
                raw_html,
                css_text=css_text,
                remove_classes=False,
            )
        except Exception as exc:
            return False, f"{input_path} -> {output_path} failed to inline CSS: {exc}", warnings

    try:
        raw_html = sanitize_html_attributes(raw_html)
        raw_html = strip_html_wrapper(raw_html)
    except Exception:
        pass

    if missing_keys:
        warnings.append(f"Missing citations: {', '.join(missing_keys)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(raw_html, encoding="utf-8")
    return True, f"{input_path} -> {output_path}", warnings
