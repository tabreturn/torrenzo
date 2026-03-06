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

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TAG_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")
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
        content = match.group(1)
        parts = [part.strip() for part in content.split('|') if part.strip()]
        if not parts:
            return match.group(0)

        lookup_keys: list[str] = []
        if len(parts) == 1:
            lookup_keys.append(parts[0])
        else:
            lookup_keys.append('|'.join(parts))
            if parts[0].lower() == 'assessment':
                lookup_keys.append('|'.join(parts[1:]))

        for key in lookup_keys:
            snippet = tags.get(key)
            if snippet is not None:
                return snippet
        return match.group(0)

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

    workdir = input_path.parent
    css_path = workdir / 'style' / 'style.css'

    original_md = input_path.read_text(encoding='utf-8')
    input_path.write_text(body, encoding='utf-8')

    local_bin = PROJECT_ROOT / 'node_modules' / '.bin' / ('md-to-pdf.cmd' if Path.home().anchor != '/' else 'md-to-pdf')
    if local_bin.exists():
        cmd = [str(local_bin.resolve()), input_path.name, '--stylesheet', 'style/style.css']
    else:
        cmd = ['npx', 'md-to-pdf', input_path.name, '--stylesheet', 'style/style.css']

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))

    input_path.write_text(original_md, encoding='utf-8')

    pdf_temp = workdir / f"{input_path.stem}.pdf"
    if result.returncode == 0 and pdf_temp.exists():
        shutil.move(str(pdf_temp), output_path)

    success = result.returncode == 0 and output_path.exists()
    msg = f"{input_path} -> {output_path}" if success else f"{input_path} -> {output_path} failed: {result.stderr.strip()}"
    return success, msg
