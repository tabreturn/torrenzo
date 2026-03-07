from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from markdown_it import MarkdownIt

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATAVIEW_RE = re.compile(r"`?=?\s*\[\[outline\]\]\.([^\s`]+)`?")
DATAVIEW_BLOCK_RE = re.compile(r"```dataview\s+LIST without id slo\[x\]\s+FROM \"outline\"\s+FLATTEN ([^\s]+) AS x\s+```", re.I | re.S)
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
    def replace_content(content: str, original: str) -> str:
        parts = [part.strip() for part in content.split('|') if part.strip()]
        if not parts:
            return original

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
        return original

    def replace_dataview_block(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        candidates: list[str] = [f'outline.{path}']
        parts = path.split('.')
        if len(parts) >= 2 and parts[0].lower() == 'assessment':
            aid_token = parts[1]
            aid_num = aid_token.removeprefix('ass') if aid_token.lower().startswith('ass') else aid_token
            candidates = [
                f'assessment|{aid_token}|slo',
                f'assessment|{aid_num}|slo',
                f'outline.{path}',
            ]
        for key in candidates:
            snippet = tags.get(key)
            if snippet is not None:
                return snippet
        return match.group(0)

    text = DATAVIEW_RE.sub(lambda m: replace_content(f"outline.{m.group(1)}", m.group(0)), text)
    text = DATAVIEW_BLOCK_RE.sub(lambda m: replace_dataview_block(m), text)
    return text


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    pdf_css = context.get('pdf_css', '')
    tags = context.get('tags', {})

    raw_content = input_path.read_text(encoding='utf-8')
    metadata, body = extract_metadata_from_front_matter(raw_content)
    if METADATA_TOKEN in body and metadata:
        body = body.replace(METADATA_TOKEN, build_metadata_table(metadata))
    body = apply_tags(body, tags)

    md = MarkdownIt("commonmark").enable("table").enable("strikethrough")
    _ = md  # parser kept for future extensions

    output_path.parent.mkdir(parents=True, exist_ok=True)

    workdir = input_path.parent
    style_src = PROJECT_ROOT / 'assessments' / 'style'
    style_dst = workdir / 'style'
    config_src = style_src / 'config.js'
    if not config_src.exists():
        return False, f"Missing config.js for {input_path}"

    logo_path = style_src / 'logo.svg'
    created_style = False
    temp_md_path: Path | None = None
    result: subprocess.CompletedProcess[str] | None = None
    success = False
    msg = ''

    try:
        if style_src.exists():
            if style_dst.exists():
                shutil.rmtree(style_dst, ignore_errors=True)
            shutil.copytree(style_src, style_dst)
            created_style = True

        config_content = config_src.read_text(encoding='utf-8')
        if logo_path.exists():
            svg_markup = logo_path.read_text(encoding='utf-8').strip()
            config_content = config_content.replace('<!--INLINE_LOGO_MARKUP-->', svg_markup)
        else:
            config_content = config_content.replace('<!--INLINE_LOGO_MARKUP-->', '')

        config_dst = style_dst / 'config.js'
        config_dst.write_text(config_content, encoding='utf-8')

        with tempfile.NamedTemporaryFile('w', delete=False, dir=workdir, suffix='.md', encoding='utf-8') as temp_md:
            temp_md.write(body)
            temp_md_path = Path(temp_md.name)

        local_bin = PROJECT_ROOT / 'node_modules' / '.bin' / ('md-to-pdf.cmd' if Path.home().anchor != '/' else 'md-to-pdf')
        if local_bin.exists():
            cmd = [str(local_bin.resolve()), temp_md_path.name]
        else:
            cmd = ['npx', 'md-to-pdf', temp_md_path.name]
        cmd.extend(['--stylesheet', 'style/style.css', '--config-file', 'style/config.js'])

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))

        pdf_temp = workdir / f"{temp_md_path.stem}.pdf"
        if result.returncode == 0 and pdf_temp.exists():
            shutil.move(str(pdf_temp), output_path)

        success = result.returncode == 0 and output_path.exists()
        if success:
            msg = f"{input_path} -> {output_path}"
        else:
            msg = f"{input_path} -> {output_path} failed: {result.stderr.strip()}"
    except FileNotFoundError as exc:
        msg = f"{input_path} -> {output_path} failed: {exc}"
    finally:
        if temp_md_path and temp_md_path.exists():
            temp_md_path.unlink(missing_ok=True)
        if created_style and style_dst.exists():
            shutil.rmtree(style_dst, ignore_errors=True)

    return success, msg
