#!/usr/bin/env python3
"""torenza.py
Converts assessment briefs into PDFs and module activities into LMS-ready HTML snippets.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path
from markdown_pdf import MarkdownPdf, Section
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
BRIEF_PATTERN = 'ass_*_brief.md'
ACTIVITY_PATTERN = 'mod_*_activities.md'
BUILD_DIR = PROJECT_ROOT / 'build'

IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
TAG_RE = re.compile(r'{{\s*([\w_]+)\s*}}')
STRONG_RE = re.compile(r'\*\*(.+?)\*\*')
ITALIC_RE = re.compile(r'(?<!\*)\*([^*]+)\*(?!\*)')
CODE_RE = re.compile(r'`([^`]+)`')
PDF_USER_CSS = (PROJECT_ROOT / 'assessments' / 'style.css').read_text(encoding='utf-8')
FRONT_MATTER_RE = re.compile(r'\A---\n(.*?)\n---\n', re.S)
METADATA_TOKEN = '<<metadata_table>>'


def prepare_build_dir() -> None:
    if BUILD_DIR.exists():
        for child in BUILD_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        BUILD_DIR.mkdir(parents=True, exist_ok=True)


def render_learning_outcomes(outcomes: list[dict[str, str]]) -> str:
    if not outcomes:
        return ''
    entries: list[str] = [
        '<section class="subject-learning-outcomes">',
        '<h3>Subject learning outcomes</h3>',
        '<dl>',
    ]
    for outcome in outcomes:
        code = html.escape(str(outcome.get('code', '')).strip())
        description = html.escape(str(outcome.get('description', '')).strip())
        entries.append(f'<dt>{code}</dt>')
        entries.append(f'<dd>{description}</dd>')
    entries.extend(['</dl>', '</section>'])
    return '\n'.join(entries)


def build_tag_map() -> dict[str, str]:
    outline_path = PROJECT_ROOT / 'outline.yaml'
    if not outline_path.exists():
        raise SystemExit('outline.yaml is required at the project root')
    try:
        data = yaml.safe_load(outline_path.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f'Failed to parse outline.yaml: {exc}') from exc

    tags: dict[str, str] = {}
    slo = data.get('subject_learning_outcomes')
    if isinstance(slo, list):
        tags['subject_learning_outcomes'] = render_learning_outcomes(slo)
    return tags


def extract_metadata_from_front_matter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
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


def convert_md_to_pdf(md_path: Path) -> None:
    pdf = MarkdownPdf()
    raw_content = md_path.read_text(encoding='utf-8')
    metadata, body = extract_metadata_from_front_matter(raw_content)
    if METADATA_TOKEN in body and metadata:
        body = body.replace(METADATA_TOKEN, build_metadata_table(metadata))
    styled_content = f"<style>{PDF_USER_CSS}</style>\n{body}"
    section = Section(styled_content, root=str(md_path.parent), paper_size='A4')
    pdf.add_section(section)

    dest_name = f'{md_path.parent.name}.pdf'
    dest = BUILD_DIR / dest_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(str(dest))


def inline_format(text: str, tags: dict[str, str]) -> str:
    placeholders: dict[str, str] = {}

    def capture_token() -> str:
        token = f'__TOKEN_{len(placeholders)}__'
        return token

    def handle_tag(match: re.Match[str]) -> str:
        key = capture_token()
        name = match.group(1)
        snippet = tags.get(name)
        if snippet is None:
            return match.group(0)
        placeholders[key] = snippet
        return key

    def handle_image(match: re.Match[str]) -> str:
        key = capture_token()
        alt = html.escape(match.group(1), quote=True)
        src = html.escape(match.group(2), quote=True)
        placeholders[key] = f'<img src="{src}" alt="{alt}">' 
        return key

    text = TAG_RE.sub(handle_tag, text)
    text = IMAGE_RE.sub(handle_image, text)
    escaped = html.escape(text)
    escaped = CODE_RE.sub(r'<code>\1</code>', escaped)
    escaped = STRONG_RE.sub(r'<strong>\1</strong>', escaped)
    escaped = ITALIC_RE.sub(r'<em>\1</em>', escaped)

    for token, snippet in placeholders.items():
        escaped = escaped.replace(token, snippet)

    return escaped


def convert_markdown_to_lms_html(content: str, tags: dict[str, str]) -> str:
    lines = content.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_type: str | None = None
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        text = ' '.join(line.strip() for line in paragraph).strip()
        paragraph = []
        if text:
            output.append(f'<p>{inline_format(text, tags)}</p>')

    def flush_list() -> None:
        nonlocal list_items, list_type
        if not list_items or list_type is None:
            list_items = []
            list_type = None
            return
        tag = 'ul' if list_type == 'bullet' else 'ol'
        output.append(f'<{tag}>')
        for item in list_items:
            output.append(f'  <li>{inline_format(item, tags)}</li>')
        output.append(f'</{tag}>')
        list_items = []
        list_type = None

    def flush_code() -> None:
        nonlocal code_lines
        if not code_lines:
            return
        block = '\n'.join(html.escape(line) for line in code_lines)
        code_lines = []
        output.append(f'<pre><code>{block}</code></pre>')

    for line in lines:
        stripped = line.rstrip('\n')

        if stripped.strip().startswith('```'):
            flush_paragraph()
            flush_list()
            if in_code:
                in_code = False
                flush_code()
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(stripped)
            continue

        if not stripped.strip():
            flush_paragraph()
            flush_list()
            continue

        heading_match = re.match(r'^(#{1,4})\s+(.*)$', stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            output.append(f'<h{level}>{inline_format(heading, tags)}</h{level}>')
            continue

        bullet_match = re.match(r'^\s*[-*]\s+(.*)$', stripped)
        if bullet_match:
            flush_paragraph()
            if list_type not in (None, 'bullet'):
                flush_list()
            list_type = 'bullet'
            list_items.append(bullet_match.group(1).strip())
            continue

        ordered_match = re.match(r'^\s*\d+\.\s+(.*)$', stripped)
        if ordered_match:
            flush_paragraph()
            if list_type not in (None, 'ordered'):
                flush_list()
            list_type = 'ordered'
            list_items.append(ordered_match.group(1).strip())
            continue

        if list_items:
            flush_list()

        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    flush_code()

    return '\n'.join(output)


def convert_activity_to_html(md_path: Path, tags: dict[str, str]) -> None:
    html_body = convert_markdown_to_lms_html(md_path.read_text(encoding='utf-8'), tags)
    dest = BUILD_DIR / md_path.with_suffix('.html').name
    dest.write_text(html_body, encoding='utf-8')


def find_briefs(root: Path) -> list[Path]:
    return sorted(root.rglob(BRIEF_PATTERN))


def find_activities(root: Path) -> list[Path]:
    return sorted(root.rglob(ACTIVITY_PATTERN))


def main() -> None:
    parser = argparse.ArgumentParser(description='Convert assessment briefs to PDF and module activities to LMS HTML snippets.')
    parser.add_argument(
        'root',
        nargs='?',
        type=Path,
        default=Path('.'),
        help='Directory to search for briefs and activities',
    )
    args = parser.parse_args()

    prepare_build_dir()
    tags = build_tag_map()

    briefs = find_briefs(args.root)
    activities = find_activities(args.root)

    if not briefs and not activities:
        raise SystemExit(f'No files matching {BRIEF_PATTERN} or {ACTIVITY_PATTERN} were found under {args.root}')

    if briefs:
        for brief in briefs:
            convert_md_to_pdf(brief)

    for activity in activities:
        convert_activity_to_html(activity, tags)


if __name__ == '__main__':
    main()
