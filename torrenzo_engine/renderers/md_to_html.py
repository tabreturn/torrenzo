from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
from typing import Any, Dict, Tuple

from markdown_it import MarkdownIt
from premailer import transform
from lxml import html as lxml_html
from pybtex.database import parse_file

from .bib_to_html import render_entry_to_html
from .md_to_pdf import apply_tags


CITATION_BRACKET_RE = re.compile(r"\[@([^\]]+)\]")
CITATION_BARE_RE = re.compile(r"(?<!\w)@([A-Za-z0-9:_-]+)")


def load_module_css(input_path: Path) -> str:
    modules_dir = input_path.parent.parent
    css_path = modules_dir / "style" / "style.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def substitute_css_variables(css_text: str) -> str:
    root_blocks = re.findall(r":root\s*{([^}]*)}", css_text, re.S)
    mapping: dict[str, str] = {}
    for block in root_blocks:
        for match in re.finditer(r"--([A-Za-z0-9_-]+)\s*:\s*([^;]+);", block):
            name = match.group(1).strip()
            value = match.group(2).strip()
            if name:
                mapping[name] = value
    if not mapping:
        return css_text

    def replace_var(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        fallback = match.group(2).strip() if match.group(2) else None
        if name in mapping:
            return mapping[name]
        if fallback is not None:
            return fallback
        return match.group(0)

    substituted = re.sub(r"var\(\s*--([A-Za-z0-9_-]+)(?:\s*,\s*([^)]+))?\)", replace_var, css_text)
    substituted = re.sub(r":root\s*{[^}]*}", "", substituted, flags=re.S)
    substituted = re.sub(r"\s*--[A-Za-z0-9_-]+\s*:\s*[^;]+;\s*", "", substituted)
    return substituted


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


def load_bibliography(input_path: Path) -> dict[str, Any]:
    modules_root = input_path.parent.parent
    entries: dict[str, Any] = {}
    bib_paths = [modules_root / "references.bib", *sorted(modules_root.glob("mod_*_resources*.bib"))]
    for bib_path in bib_paths:
        if not bib_path.exists():
            continue
        try:
            bib_data = parse_file(str(bib_path))
        except Exception:
            continue
        for key, entry in bib_data.entries.items():
            if key not in entries:
                entries[key] = entry
    return entries


def collect_citation_numbers(text: str, bib_entries: dict[str, Any]) -> tuple[dict[str, int], list[str], list[str]]:
    mapping: dict[str, int] = {}
    ordered: list[str] = []
    missing: list[str] = []

    def add_key(key: str) -> None:
        if key in bib_entries:
            if key not in mapping:
                mapping[key] = len(mapping) + 1
                ordered.append(key)
        elif key not in missing:
            missing.append(key)

    for match in CITATION_BRACKET_RE.finditer(text):
        raw_keys = match.group(1)
        for token in re.split(r"[;,]", raw_keys):
            key = token.strip().lstrip("@")
            if key:
                add_key(key)
    for match in CITATION_BARE_RE.finditer(text):
        key = match.group(1).strip()
        if key:
            add_key(key)
    return mapping, ordered, missing


def replace_citations(text: str, mapping: dict[str, int]) -> str:
    def replace_bracket(match: re.Match[str]) -> str:
        raw_keys = match.group(1)
        pieces: list[str] = []
        for token in re.split(r"[;,]", raw_keys):
            key = token.strip().lstrip("@")
            if not key:
                continue
            number = mapping.get(key)
            if number is None:
                pieces.append(f"[@{key}]")
            else:
                pieces.append(f'<sup><a href="#ref-{key}">[{number}]</a></sup>')
        return " ".join(pieces) if pieces else match.group(0)

    def replace_bare(match: re.Match[str]) -> str:
        key = match.group(1)
        number = mapping.get(key)
        if number is None:
            return match.group(0)
        return f'<sup><a href="#ref-{key}">[{number}]</a></sup>'

    text = CITATION_BRACKET_RE.sub(replace_bracket, text)
    text = CITATION_BARE_RE.sub(replace_bare, text)
    return text


def render_references(keys_in_order: list[str], bib_entries: dict[str, Any]) -> str:
    if not keys_in_order:
        return ""
    items: list[str] = []
    for key in keys_in_order:
        entry = bib_entries.get(key)
        if entry is None:
            continue
        try:
            html_block = render_entry_to_html(entry)
        except Exception:
            continue
        items.append(f'<li id="ref-{key}">{html_block}</li>')
    if not items:
        return ""
    return "\n".join(["<h2>References</h2>", "<ul>", *items, "</ul>"])


def prefix_demo_asset_paths(html_body: str, input_path: Path) -> str:
    if "demo_" not in input_path.parent.name:
        return html_body
    try:
        document = lxml_html.fromstring(html_body)
    except Exception:
        return html_body
    for element in document.iter("img"):
        src = element.get("src")
        if not src:
            continue
        normalized = PurePosixPath(src)
        if not normalized.name.startswith("demo_"):
            element.set("src", str(normalized.with_name(f"demo_{normalized.name}")))
    return lxml_html.tostring(document, encoding="unicode", method="html")

def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str, list[str]]:
    tags = context.get("tags", {})
    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    raw = input_path.read_text(encoding="utf-8")

    raw, tag_warnings = apply_tags(raw, tags)

    bib_entries = load_bibliography(input_path)
    citation_numbers, ordered_keys, missing_keys = collect_citation_numbers(raw, bib_entries)
    if citation_numbers:
        raw = replace_citations(raw, citation_numbers)

    css_text = load_module_css(input_path)
    css_text = substitute_css_variables(css_text)
    html_body = md.render(raw)
    if ordered_keys:
        references = render_references(ordered_keys, bib_entries)
        if references:
            html_body = f"{html_body}\n{references}"
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
            return False, f"{input_path} -> {output_path} failed to inline CSS: {exc}", []

    html_body = prefix_demo_asset_paths(html_body, input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_body, encoding="utf-8")

    warnings: list[str] = list(tag_warnings)
    if missing_keys:
        warnings.append(f"Missing citations: {', '.join(missing_keys)}")

    return True, f"{input_path} -> {output_path}", warnings
