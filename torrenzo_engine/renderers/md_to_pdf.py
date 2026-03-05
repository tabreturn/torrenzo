from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from markdown_it import MarkdownIt

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
    lines: list[str] = ['<table>', '<thead><tr><th>Field</th><th>Details</th></tr></thead>', '<tbody>']
    for key, value in metadata.items():
        field = key.replace('_', ' ').title()
        if isinstance(value, list):
            detail = '<br>'.join(str(item) for item in value)
        else:
            detail = str(value)
        lines.append(f'<tr><td>{field}</td><td>{detail}</td></tr>')
    lines.append('</tbody></table>')
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

    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    _ = md

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        md_temp = Path(tmpdir) / 'input.md'
        md_temp.write_text(body, encoding='utf-8')

        css_path = Path(tmpdir) / 'style.css'
        css_path.write_text(pdf_css, encoding='utf-8')

        pdf_options = json.dumps({
            "format": "A4",
            "margin": {"top": "25mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
            "displayHeaderFooter": True,
            "headerTemplate": "<div style='font-size:10px;width:100%;text-align:center;'>ver.2026-03-04</div>",
            "footerTemplate": "<div style='font-size:10px;width:100%;text-align:center;'><span class=\"pageNumber\"></span>/<span class=\"totalPages\"></span></div>",
        })

        cmd_npm = [
            'npx', 'md-to-pdf',
            str(md_temp),
            '--stylesheet', str(css_path),
            '--pdf-options', pdf_options,
            '--basedir', str(input_path.parent),
        ]
        result = subprocess.run(cmd_npm, capture_output=True, text=True)

        pdf_temp = md_temp.with_suffix('.pdf')
        if result.returncode == 0 and pdf_temp.exists():
            shutil.move(str(pdf_temp), output_path)

    success = result.returncode == 0 and output_path.exists()
    msg = f"{input_path} -> {output_path}" if success else f"{input_path} -> {output_path} failed: {result.stderr.strip()}"
    return success, msg
