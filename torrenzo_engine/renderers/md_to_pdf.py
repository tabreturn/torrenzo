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

    css_path = (PROJECT_ROOT / 'assessments' / 'style.css').resolve()
    style_dir = PROJECT_ROOT / 'assessments'

    temp_root = Path(tempfile.mkdtemp(prefix='torrenzo_pdf_'))
    workdir = temp_root / input_path.parent.name
    shutil.copytree(input_path.parent, workdir)

    processed_md = workdir / input_path.name
    processed_md.write_text(body, encoding='utf-8')

    pdf_options = json.dumps({
        "format": "A4",
        "margin": {"top": "25mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
        "displayHeaderFooter": True,
        "headerTemplate": "<div style='font-size:10px;width:100%;text-align:center;'>ver.2026-03-04</div>",
        "footerTemplate": "<div style='font-size:10px;width:100%;text-align:center;'><span class=\"pageNumber\"></span>/<span class=\"totalPages\"></span></div>",
    })

    local_bin = PROJECT_ROOT / 'node_modules' / '.bin' / 'md-to-pdf'
    if local_bin.exists():
        cmd_npm = [str(local_bin.resolve()), processed_md.name]
    else:
        cmd_npm = ['npx', 'md-to-pdf', processed_md.name]

    cmd_npm.extend([
        '--stylesheet', str(css_path),
        '--pdf-options', pdf_options,
        '--basedir', str(workdir),
    ])

    result = subprocess.run(cmd_npm, capture_output=True, text=True, cwd=str(workdir))

    pdf_temp = workdir / f"{processed_md.stem}.pdf"
    if result.returncode == 0 and pdf_temp.exists():
        shutil.move(str(pdf_temp), output_path)

    success = result.returncode == 0 and output_path.exists()
    msg = f"{input_path} -> {output_path}" if success else f"{input_path} -> {output_path} failed: {result.stderr.strip()}"
    return success, msg
