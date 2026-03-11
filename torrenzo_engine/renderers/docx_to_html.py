from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Dict, Tuple

from docx import Document
from docx.oxml.ns import qn
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
NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
BLIP_TAG = f"{{{NAMESPACES['a']}}}blip"
BR_TAG = qn("w:br")
TEXT_TAG = qn("w:t")


def extract_image_map(document: Document, asset_dir: Path, input_path: Path) -> dict[str, str]:
    image_map: dict[str, str] = {}
    asset_dir.mkdir(parents=True, exist_ok=True)
    prefix = "demo_" if "demo_" in input_path.parent.name else ""
    for rel_id, part in document.part.related_parts.items():
        content_type = getattr(part, "content_type", "") or ""
        if not content_type.startswith("image/"):
            continue
        filename = Path(part.partname).name
        output_name = f"{prefix}{input_path.stem}_{filename}"
        dest = asset_dir / output_name
        if not dest.exists():
            dest.write_bytes(part.blob)
        image_map[rel_id] = f"assets/{output_name}"
    return image_map


def paragraph_to_html(p, image_map: dict[str, str]) -> str:
    pieces: list[str] = []
    for run in p.runs:
        for child in run._element.iterchildren():
            tag = child.tag
            if tag == BR_TAG:
                pieces.append("<br>")
                continue
            if tag == TEXT_TAG:
                text = child.text or ""
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
        for blip in run._element.iterfind(f".//{BLIP_TAG}"):
            embed = blip.get(qn("r:embed"))
            if embed and embed in image_map:
                pieces.append(f'<img src="{escape(image_map[embed])}">')
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
    asset_dir = output_path.parent / "assets"
    image_map = extract_image_map(document, asset_dir, input_path)
    raw_fragments: list[str] = []
    warnings: list[str] = []

    for block in document.paragraphs:
        raw_fragments.append(paragraph_to_html(block, image_map))

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
