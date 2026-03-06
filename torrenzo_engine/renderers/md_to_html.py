from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from markdown_it import MarkdownIt
from premailer import transform
from lxml import html as lxml_html

from .md_to_pdf import apply_tags


def load_module_css(input_path: Path) -> str:
    modules_dir = input_path.parent.parent
    css_path = modules_dir / "style" / "style.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def strip_html_wrapper(html_text: str) -> str:
    try:
        document = lxml_html.fromstring(html_text)
    except Exception:
        return html_text
    body = document.find("body")
    if body is None:
        return html_text
    inner = body.text or ""
    for child in body:
        inner += lxml_html.tostring(child, encoding="unicode", method="html")
        if child.tail:
            inner += child.tail
    return inner


def sanitize_html_attributes(html_text: str) -> str:
    try:
        document = lxml_html.fromstring(html_text)
    except Exception:
        return html_text
    unwanted = {"bgcolor", "color", "background", "text", "link", "alink", "vlink"}
    for element in document.iter():
        for attr in list(element.attrib):
            if attr.lower() in unwanted:
                del element.attrib[attr]
    return lxml_html.tostring(document, encoding="unicode", method="html")


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    tags = context.get("tags", {})
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    raw = input_path.read_text(encoding="utf-8")

    raw = apply_tags(raw, tags)

    css_text = load_module_css(input_path)
    html_body = md.render(raw)
    if css_text.strip():
        try:
            html_body = transform(
                html_body,
                css_text=css_text,
                remove_classes=False,
            )
            html_body = sanitize_html_attributes(html_body)
            html_body = strip_html_wrapper(html_body)
        except Exception as exc:
            return False, f"{input_path} -> {output_path} failed to inline CSS: {exc}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_body, encoding="utf-8")
    return True, f"{input_path} -> {output_path}"
