#!/usr/bin/env python3
"""torenzo.py
Converts assessment briefs into PDFs and module activities into LMS-ready HTML snippets.
"""

from __future__ import annotations

import argparse
import html
import shutil
from pathlib import Path
from typing import Any
import yaml

from torrenzo_engine import Pipeline, RenderJob, RendererRegistry
from torrenzo_engine.renderers import register_renderer, render_md_to_pdf, render_md_to_html, render_bib_to_html

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_DIR = PROJECT_ROOT / 'build'
PDF_USER_CSS = (PROJECT_ROOT / 'assessments' / 'style.css').read_text(encoding='utf-8')


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


def render_single_learning_outcome(outcome: dict[str, str]) -> str:
    code = html.escape(str(outcome.get('code', '')).strip())
    description = html.escape(str(outcome.get('description', '')).strip())
    if not code and not description:
        return ''
    if not code:
        return f'<p>{description}</p>' if description else ''
    if not description:
        return f'<p><strong>{code}</strong></p>'
    return f'<p><strong>{code}</strong> {description}</p>'


def build_tag_map() -> dict[str, str]:
    outline_path = PROJECT_ROOT / 'outline.yaml'
    if not outline_path.exists():
        raise SystemExit('outline.yaml is required at the project root')
    try:
        data = yaml.safe_load(outline_path.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f'Failed to parse outline.yaml: {exc}') from exc

    tags: dict[str, str] = {}
    slo = data.get('slo')
    if isinstance(slo, list):
        tags['slo'] = render_learning_outcomes(slo)
        for outcome in slo:
            code = str(outcome.get('code', '')).strip()
            if not code:
                continue
            snippet = render_single_learning_outcome(outcome)
            if snippet:
                tags[f'slo|{code}'] = snippet
    return tags


def make_jobs(tags: dict[str, str]) -> list[RenderJob]:
    briefs_pattern = 'assessments/assessment_*/ass_*_brief.md'
    activities_pattern = 'modules/module_*/mod_*_activities.md'
    resources_pattern = 'modules/module_*/mod_*_resources.bib'

    return [
        RenderJob(
            name='assessment_briefs',
            input_pattern=briefs_pattern,
            output_dir=Path('.'),
            renderer='md_to_pdf',
            context={'tags': tags, 'pdf_css': PDF_USER_CSS},
            output_ext='.pdf',
            output_namer=lambda p: f"{p.parent.name}.pdf",
        ),
        RenderJob(
            name='module_activities',
            input_pattern=activities_pattern,
            output_dir=Path('.'),
            renderer='md_to_html',
            context={'tags': tags},
            output_ext='.html',
        ),
        RenderJob(
            name='module_resources',
            input_pattern=resources_pattern,
            output_dir=Path('.'),
            renderer='bib_to_html',
            context={},
            output_ext='.html',
        ),
    ]


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
