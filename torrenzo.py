#!/usr/bin/env python3
"""torenzo.py
Converts assessment briefs into PDFs and module activities into LMS-ready HTML snippets.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path
from typing import Any
import yaml

from torrenzo_engine import Pipeline, RenderJob, RendererRegistry
from torrenzo_engine.renderers import register_renderer, render_md_to_pdf, render_md_to_html, render_bib_to_html

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_DIR = PROJECT_ROOT / 'build'
PDF_USER_CSS = ''

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
        code = html.escape(str(outcome.get('id', '')).strip())
        description = html.escape(str(outcome.get('description', '')).strip())
        entries.append(f'<dt>{code}</dt>')
        entries.append(f'<dd>{description}</dd>')
    entries.extend(['</dl>', '</section>'])
    return '\n'.join(entries)

def render_single_learning_outcome(outcome: dict[str, str]) -> str:
    code = html.escape(str(outcome.get('id', '')).strip())
    description = html.escape(str(outcome.get('description', '')).strip())
    if not code and not description:
        return ''
    if not code:
        return f'<p>{description}</p>' if description else ''
    if not description:
        return f'<p><strong>{code}</strong></p>'
    return f'<p><strong>{code}</strong> {description}</p>'

def format_metadata_value(value: Any) -> str:
    if isinstance(value, list):
        return '<br>'.join(html.escape(str(item).strip()) for item in value)
    return html.escape(str(value).strip())

def build_assessment_metadata_tags(assessments: list[dict[str, Any]] | dict[str, Any], slos: list[dict[str, str]] | None = None) -> dict[str, str]:
    slos_by_id = {str(item.get('id', '')).strip(): item for item in slos or []}
    tags: dict[str, str] = {}

    if isinstance(assessments, list):
        items = [(str(item.get('id', '')).strip(), item) for item in assessments if isinstance(item, dict)]
    elif isinstance(assessments, dict):
        items = assessments.items()
    else:
        return tags

    for assessment_id, fields in items:
        if not assessment_id or not isinstance(fields, dict):
            continue
        table_rows: list[tuple[str, str]] = []
        for key, value in fields.items():
            normalized_key = 'slo' if key in ('learning_outcomes', 'lo', 'slo') else key
            if normalized_key == 'slo':
                outcomes: list[str] = []
                if isinstance(value, list):
                    for code in value:
                        code_str = str(code).strip()
                        if code_str in slos_by_id:
                            snippet = render_single_learning_outcome(slos_by_id[code_str])
                            if snippet:
                                outcomes.append(snippet)
                        else:
                            outcomes.append(html.escape(code_str))
                detail = '<br>'.join(outcomes)
                normalized_key = 'slo'
            else:
                detail = format_metadata_value(value)
            tags[f'assessment|{assessment_id}|{normalized_key}'] = detail
            table_rows.append((normalized_key.replace('_', ' ').title(), detail))
        if table_rows:
            lines: list[str] = ['<table>', '<thead><tr><th>Field</th><th>Details</th></tr></thead>', '<tbody>']
            for label, detail in table_rows:
                lines.append(f'<tr><td>{label}</td><td>{detail}</td></tr>')
            lines.append('</tbody></table>')
            tags[f'assessment|{assessment_id}|meta_table'] = '\n'.join(lines)
    return tags

def load_outline() -> dict[str, Any]:
    yaml_path = PROJECT_ROOT / 'outline.yaml'
    md_path = PROJECT_ROOT / 'outline.md'

    if yaml_path.exists():
        try:
            return yaml.safe_load(yaml_path.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError as exc:
            raise SystemExit(f'Failed to parse outline.yaml: {exc}') from exc

    if not md_path.exists():
        raise SystemExit('outline.yaml or outline.md is required at the project root')

    text = md_path.read_text(encoding='utf-8')
    frontmatter_match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    if not frontmatter_match:
        raise SystemExit('outline.md must start with YAML frontmatter enclosed by --- markers')

    try:
        return yaml.safe_load(frontmatter_match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f'Failed to parse outline.md frontmatter: {exc}') from exc


def build_tag_map() -> dict[str, str]:
    data = load_outline()

    tags: dict[str, str] = {}
    slos = data.get('slo') or data.get('slos')
    if isinstance(slos, list):
        tags['slo'] = render_learning_outcomes(slos)
        for outcome in slos:
            code = str(outcome.get('id', '')).strip()
            if not code:
                continue
            snippet = render_single_learning_outcome(outcome)
            if snippet:
                tags[f'slo|{code}'] = snippet

    assessments = data.get('assessment') or data.get('assessments')
    tags.update(build_assessment_metadata_tags(assessments, slos))
    return tags

def make_jobs(tags: dict[str, str]) -> list[RenderJob]:
    briefs_pattern = 'assessments/*/ass_*_brief.md'
    content_pattern = 'modules/*/mod_*_content.md'
    activities_pattern = 'modules/*/mod_*_activities.md'
    resources_pattern = 'modules/*/mod_*_resources.bib'

    return [
        RenderJob(
            name='assessment_briefs',
            input_pattern=briefs_pattern,
            output_dir=Path('.'),
            renderer='md_to_pdf',
            context={
                'tags': tags,
                'pdf_css': PDF_USER_CSS,
                'header_html': '<div class="header">ver.2026-03-04</div>',
                'footer_html': '<div class="footer"></div>',
            },
            output_ext='.pdf',
            output_namer=lambda p: f"{p.parent.name}.pdf",
        ),
        RenderJob(
            name='module_content',
            input_pattern=content_pattern,
            output_dir=Path('.'),
            renderer='md_to_html',
            context={'tags': tags},
            output_ext='.html',
            output_namer=lambda p: f"demo_{p.with_suffix('.html').name}" if 'demo_' in p.parent.name else p.with_suffix('.html').name,
        ),
        RenderJob(
            name='module_activities',
            input_pattern=activities_pattern,
            output_dir=Path('.'),
            renderer='md_to_html',
            context={'tags': tags},
            output_ext='.html',
            output_namer=lambda p: f"demo_{p.with_suffix('.html').name}" if 'demo_' in p.parent.name else p.with_suffix('.html').name,
        ),
        RenderJob(
            name='module_resources',
            input_pattern=resources_pattern,
            output_dir=Path('.'),
            renderer='bib_to_html',
            context={},
            output_ext='.html',
            output_namer=lambda p: f"demo_{p.with_suffix('.html').name}" if 'demo_' in p.parent.name else p.with_suffix('.html').name,
        ),
    ]

def main() -> None:
    parser = argparse.ArgumentParser(description='Convert assessment briefs to PDF and module activities to LMS-ready HTML snippets.')
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

    registry = RendererRegistry()
    register_renderer(registry, 'md_to_pdf', lambda _: render_md_to_pdf)
    register_renderer(registry, 'md_to_html', lambda _: render_md_to_html)
    register_renderer(registry, 'bib_to_html', lambda _: render_bib_to_html)

    pipeline = Pipeline(args.root, BUILD_DIR, registry)
    diagnostics = pipeline.execute(make_jobs(tags))
    for message in diagnostics:
        print(message)

if __name__ == '__main__':
    main()
