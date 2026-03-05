from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Dict, Tuple

from markdown_pdf import MarkdownPdf, Section

TAG_RE = re.compile(r"{{\s*([\w_]+)(?:\|([\w\-]+))?\s*}}")
FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
METADATA_TOKEN = "<<metadata_table>>"


def extract_metadata_from_front_matter(text: str) -> tuple[Dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except Exception:
        metadata = {}
    body = text[match.end():]
    return metadata, body


def build_metadata_table(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ''
    lines: list[str] = ['| Field | Details |', '| --- | --- |']
    for key, value in metadata.items():
        field = key.replace('_', ' ').title()
        if isinstance(value, list):
            detail = '<br>'.join(html.escape(str(item)) for item in value)
        else:
            detail = html.escape(str(value))
        lines.append(f'| {field} | {detail} |')
    return '\n'.join(lines)


def apply_tags(text: str, tags: dict[str, str]) -> str:
    def replace_tag(match: re.Match[str]) -> str:
        name = match.group(1)
        detail = match.group(2)
        lookup_key = name if detail is None else f'{name}|{detail}'
        snippet = tags.get(lookup_key)
        if snippet is None:
            if detail is None:
                return match.group(0)
            snippet = tags.get(name)
            if snippet is None:
                return match.group(0)
        return snippet

    return TAG_RE.sub(replace_tag, text)


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    pdf_css = context.get('pdf_css', '')
    tags = context.get('tags', {})

    raw_content = input_path.read_text(encoding='utf-8')
    metadata, body = extract_metadata_from_front_matter(raw_content)
    if METADATA_TOKEN in body and metadata:
        body = body.replace(METADATA_TOKEN, build_metadata_table(metadata))
    body = apply_tags(body, tags)

    styled_content = f"<style>{pdf_css}</style>\n{body}"
    pdf = MarkdownPdf()
    section = Section(styled_content, root=str(input_path.parent), paper_size='A4')
    pdf.add_section(section)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(str(output_path))

    return True, f"{input_path} -> {output_path}"
