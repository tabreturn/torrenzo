#!/usr/bin/env python3
"""torenzo.py
Converts assessment briefs into PDFs and module activities into LMS-ready HTML snippets.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
import yaml

from torrenzo_engine import Pipeline, RenderJob, RendererRegistry
from torrenzo_engine.pipeline import fmt
from torrenzo_engine.renderers import register_renderer, render_md_to_pdf, render_md_to_html, render_docx_to_html, render_copy_asset

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_DIR = PROJECT_ROOT / 'build'
PDF_USER_CSS = ''

def locate_command(candidates: list[str | Path]) -> str | None:
    for candidate in candidates:
        if isinstance(candidate, Path):
            if candidate.exists():
                return str(candidate)
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None

def optimize_assets(build_dir: Path) -> list[str]:
    messages: list[str] = []

    png_tool = locate_command(['pngquant', 'oxipng'])
    png_files = sorted(build_dir.rglob('*.png'))
    if png_tool and png_files:
        optimized_pngs = 0
        for path in png_files:
            if Path(png_tool).name == 'pngquant':
                cmd = [png_tool, '--force', '--strip', '--ext', '.png', str(path)]
            else:
                cmd = [png_tool, '--strip', 'safe', '--opt', '3', '--fix', str(path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                optimized_pngs += 1
            else:
                error = result.stderr.strip() or result.stdout.strip()
                messages.append(fmt('error', f"PNG optimize failed ({Path(png_tool).name}): {path.relative_to(build_dir)}: {error}" if error else f"PNG optimize failed ({Path(png_tool).name}): {path.relative_to(build_dir)}"))
        if optimized_pngs:
            messages.append(fmt('info', f"Optimized {optimized_pngs} PNG file(s) with {Path(png_tool).name}"))
    elif not png_tool:
        messages.append(fmt('warning', 'Skipping PNG optimization (pngquant or oxipng not installed)'))
    elif not png_files:
        messages.append(fmt('info', 'No PNG assets to optimize'))

    svgo_tool = locate_command([PROJECT_ROOT / 'node_modules' / '.bin' / 'svgo', 'svgo'])
    svg_files = sorted(build_dir.rglob('*.svg'))
    if svgo_tool and svg_files:
        optimized_svgs = 0
        for path in svg_files:
            cmd = [svgo_tool, '--quiet', '--multipass', '--input', str(path), '--output', str(path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                optimized_svgs += 1
            else:
                error = result.stderr.strip() or result.stdout.strip()
                messages.append(fmt('error', f"SVG optimize failed (svgo): {path.relative_to(build_dir)}: {error}" if error else f"SVG optimize failed (svgo): {path.relative_to(build_dir)}"))
        if optimized_svgs:
            messages.append(fmt('info', f"Optimized {optimized_svgs} SVG file(s) with svgo"))
    elif not svgo_tool:
        messages.append(fmt('warning', 'Skipping SVG optimization (svgo not installed; run npm install)'))
    elif not svg_files:
        messages.append(fmt('info', 'No SVG assets to optimize'))

    return messages

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
            if str(key).startswith('_'):
                continue
            normalized_key = 'slo' if key in ('learning_outcomes', 'lo', 'slo') else key
            if normalized_key == 'slo':
                outcomes: list[str] = []
                if isinstance(value, list):
                    for code in value:
                        code_str = str(code).strip()
                        if code_str in slos_by_id:
                            desc = html.escape(str(slos_by_id[code_str].get('description', '')).strip())
                            if desc:
                                outcomes.append(f'<li>{desc}</li>')
                            else:
                                outcomes.append(f'<li>{html.escape(code_str)}</li>')
                        else:
                            outcomes.append(f'<li>{html.escape(code_str)}</li>')
                detail = f"<ul>{''.join(outcomes)}</ul>" if outcomes else ''
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
            table_markup = '\n'.join(lines)
            tags[f'assessment|{assessment_id}|meta_table'] = table_markup
            tags[f"assessment|{fields.get('_key', assessment_id)}|meta_table"] = table_markup
    return tags

def load_outline() -> dict[str, Any]:
    md_path = PROJECT_ROOT / 'outline.md'
    if not md_path.exists():
        raise SystemExit('outline.md is required at the project root')
    text = md_path.read_text(encoding='utf-8')
    frontmatter_match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    yaml_text = frontmatter_match.group(1) if frontmatter_match else text
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f'Failed to parse outline.md: {exc}') from exc
    return data


def build_tag_map() -> dict[str, str]:
    data = load_outline()

    tags: dict[str, str] = {}
    slos_obj = data.get('slo') or data.get('slos') or {}
    if isinstance(slos_obj, dict):
        slos = [{'id': k, 'description': v} for k, v in slos_obj.items()]
    elif isinstance(slos_obj, list):
        slos = slos_obj
    else:
        slos = []

    if slos:
        tags['slo'] = render_learning_outcomes(slos)
        tags['^slo'] = tags['slo']
        for outcome in slos:
            code = str(outcome.get('id', '')).strip()
            if not code:
                continue
            snippet = render_single_learning_outcome(outcome)
            if snippet:
                tags[f'slo|{code}'] = snippet
                tags[f'slo-{code}'] = snippet
                tags[f'^slo-{code}'] = snippet

    assessments_obj = data.get('assessment') or data.get('assessments') or {}
    if isinstance(assessments_obj, dict):
        assessments_list = []
        for key, val in assessments_obj.items():
            if isinstance(val, dict):
                entry = dict(val)
                entry.setdefault('id', str(entry.get('id') or key))
                entry['_key'] = str(key).strip()
                assessments_list.append(entry)
        assessments = assessments_list
    else:
        assessments = assessments_obj if isinstance(assessments_obj, list) else []

    slos_lookup = {str(item.get('id', '')).strip(): item for item in slos if isinstance(item, dict)}

    tags.update(build_assessment_metadata_tags(assessments, slos))
    if isinstance(assessments, list):
        for entry in assessments:
            aid = str(entry.get('id', '')).strip()
            key = str(entry.get('_key', aid)).strip()
            if not aid:
                continue
            title = str(entry.get('title', '')).strip()
            tags[f'assess-{aid}-number'] = aid
            tags[f'ass-{aid}-number'] = aid
            tags[f'^assess-{aid}-number'] = aid
            tags[f'^ass-{aid}-number'] = aid
            tags[f'outline.assessment.{aid}.number'] = aid
            tags[f'outline.assessment.{key}.number'] = aid
            tags[f'outline.assessment.{aid}.id'] = aid
            tags[f'outline.assessment.{key}.id'] = aid
            if title:
                tags[f'assess-{aid}'] = title
                tags[f'assess-{aid}-title'] = title
                tags[f'ass-{aid}'] = title
                tags[f'ass-{aid}-title'] = title
                tags[f'^assess-{aid}'] = title
                tags[f'^assess-{aid}-title'] = title
                tags[f'^ass-{aid}'] = title
                tags[f'^ass-{aid}-title'] = title
                tags[f'outline.assessment.{aid}.title'] = title
                tags[f'outline.assessment.{key}.title'] = title
            meta_key = f'assessment|{aid}|meta_table'
            alt_meta_key = f'assessment|{key}|meta_table'
            if meta_key in tags:
                table = tags[meta_key]
            elif alt_meta_key in tags:
                table = tags[alt_meta_key]
            else:
                table = ''
            if table:
                tags[f'assess-{aid}-meta'] = table
                tags[f'ass-{aid}-meta'] = table
                tags[f'^assess-{aid}-meta'] = table
                tags[f'^ass-{aid}-meta'] = table
                tags[f'^assess-{aid}-meta-table'] = table
                tags[f'^ass-{aid}-meta-table'] = table
                tags[f'outline.assessment.{aid}.metatable'] = table
                tags[f'outline.assessment.{key}.metatable'] = table

    def to_table(value: Any, prefix: str, slos_lookup: dict[str, Any] | None) -> str | None:
        if isinstance(value, dict):
            rows = []
            for k, v in value.items():
                if str(k).startswith('_'):
                    continue
                child_prefix = f"{prefix}.{k}"
                if isinstance(v, list) and all(isinstance(item, (str, int, float)) for item in v):
                    if slos_lookup and (child_prefix.endswith('.learning_outcomes') or child_prefix.endswith('.slo') or '.learning_outcomes.' in child_prefix or '.slo.' in child_prefix):
                        snippets: list[str] = []
                        for item in v:
                            code = str(item).strip()
                            if code in slos_lookup:
                                desc = html.escape(str(slos_lookup[code].get('description', '')).strip())
                                if desc:
                                    snippets.append(f'<li>{desc}</li>')
                                else:
                                    snippets.append(f'<li>{html.escape(code)}</li>')
                            else:
                                snippets.append(f'<li>{html.escape(code)}</li>')
                        detail = f"<ul>{''.join(snippets)}</ul>" if snippets else ''
                    else:
                        detail = '<br>'.join(html.escape(str(item).strip()) for item in v)
                else:
                    nested = to_table(v, child_prefix, slos_lookup)
                    detail = nested if nested is not None else html.escape(str(v))
                rows.append((str(k).replace('_', ' ').title(), detail))
            if rows:
                lines = ['<table>', '<tbody>']
                for label, detail in rows:
                    lines.append(f'<tr><td>{label}</td><td>{detail}</td></tr>')
                lines.append('</tbody></table>')
                return '\n'.join(lines)
        if isinstance(value, list):
            if value and all(isinstance(item, (dict, list)) for item in value):
                lines = ['<table>', '<tbody>']
                for idx, item in enumerate(value):
                    lines.append(f'<tr><td>{idx}</td><td>{to_table(item, f"{prefix}.{idx}", slos_lookup) or html.escape(str(item))}</td></tr>')
                lines.append('</tbody></table>')
                return '\n'.join(lines)
            if all(isinstance(item, (str, int, float)) for item in value):
                if slos_lookup and (prefix.endswith('.learning_outcomes') or prefix.endswith('.slo') or '.learning_outcomes.' in prefix or '.slo.' in prefix):
                    snippets = []
                    for item in value:
                        code = str(item).strip()
                        if code in slos_lookup:
                            desc = html.escape(str(slos_lookup[code].get('description', '')).strip())
                            if desc:
                                snippets.append(f'<li>{desc}</li>')
                            else:
                                snippets.append(f'<li>{html.escape(code)}</li>')
                        else:
                            snippets.append(f'<li>{html.escape(code)}</li>')
                    return f"<ul>{''.join(snippets)}</ul>" if snippets else ''
                return '<br>'.join(html.escape(str(item).strip()) for item in value)
        return None

    def flatten(obj: Any, prefix: str, slos_lookup: dict[str, Any] | None) -> None:
        if isinstance(obj, dict):
            table_value = to_table(obj, prefix, slos_lookup)
            if table_value:
                tags[prefix] = table_value
            for k, v in obj.items():
                flatten(v, f"{prefix}.{k}", slos_lookup)
        elif isinstance(obj, list):
            if all(isinstance(item, (str, int, float)) for item in obj):
                if slos_lookup and (prefix.endswith('.learning_outcomes') or prefix.endswith('.slo') or '.learning_outcomes.' in prefix or '.slo.' in prefix):
                    snippets = []
                    for item in obj:
                        code = str(item).strip()
                        if code in slos_lookup:
                            desc = html.escape(str(slos_lookup[code].get('description', '')).strip())
                            if desc:
                                snippets.append(f'<li>{desc}</li>')
                            else:
                                snippets.append(f'<li>{html.escape(code)}</li>')
                        else:
                            snippets.append(f'<li>{html.escape(code)}</li>')
                    tags[prefix] = f"<ul>{''.join(snippets)}</ul>" if snippets else ''
                else:
                    tags[prefix] = ', '.join(str(item) for item in obj)
            else:
                table_value = to_table(obj, prefix, slos_lookup)
                if table_value:
                    tags[prefix] = table_value
                for idx, item in enumerate(obj):
                    flatten(item, f"{prefix}.{idx}", slos_lookup)
        else:
            tags[prefix] = str(obj)

    flatten(data, 'outline', slos_lookup)

    for key, value in list(tags.items()):
        if key.startswith('^'):
            tags[f'outline#{key}'] = value
    return tags

def make_jobs(tags: dict[str, str]) -> list[RenderJob]:
    briefs_pattern = 'assessments/*/ass_*_brief.md'
    content_pattern = 'modules/*/mod_*_content*.md'
    content_docx_pattern = 'modules/*/mod_*_content*.docx'
    activities_pattern = 'modules/*/mod_*_activit*.md'
    activities_docx_pattern = 'modules/*/mod_*_activit*.docx'
    resources_pattern = 'modules/*/mod_*_resources.bib'

    return [
        RenderJob(
            name='assessment_briefs',
            input_pattern=briefs_pattern,
            output_dir=Path('assessments_briefs'),
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
            output_dir=Path('modules_html'),
            renderer='md_to_html',
            context={'tags': tags, 'asset_dir': Path('modules_html/assets')},
            output_ext='.html',
            output_namer=lambda p: f"demo_{p.with_suffix('.html').name}" if 'demo_' in p.parent.name else p.with_suffix('.html').name,
        ),
        RenderJob(
            name='module_content_docx',
            input_pattern=content_docx_pattern,
            output_dir=Path('modules_html'),
            renderer='docx_to_html',
            context={'tags': tags},
            output_ext='.html',
            output_namer=lambda p: f"demo_{p.with_suffix('.html').name}" if 'demo_' in p.parent.name else p.with_suffix('.html').name,
        ),
        RenderJob(
            name='module_activities',
            input_pattern=activities_pattern,
            output_dir=Path('modules_html'),
            renderer='md_to_html',
            context={'tags': tags, 'asset_dir': Path('modules_html/assets')},
            output_ext='.html',
            output_namer=lambda p: f"demo_{p.with_suffix('.html').name}" if 'demo_' in p.parent.name else p.with_suffix('.html').name,
        ),
        RenderJob(
            name='module_activities_docx',
            input_pattern=activities_docx_pattern,
            output_dir=Path('modules_html'),
            renderer='docx_to_html',
            context={'tags': tags},
            output_ext='.html',
            output_namer=lambda p: f"demo_{p.with_suffix('.html').name}" if 'demo_' in p.parent.name else p.with_suffix('.html').name,
        ),
        RenderJob(
            name='module_assets',
            input_pattern='modules/*/assets/**/*',
            output_dir=Path('modules_html/assets'),
            renderer='copy_asset',
            context={},
            output_ext='',
            output_namer=lambda p: (
                f"demo_{p.name}" if 'demo_' in p.parent.parent.name else p.name
            ),
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
    parser.add_argument(
        '--optimize-assets',
        action='store_true',
        help='Optimize built assets with pngquant/oxipng and svgo',
    )
    args = parser.parse_args()

    prepare_build_dir()
    tags = build_tag_map()

    registry = RendererRegistry()
    register_renderer(registry, 'md_to_pdf', lambda _: render_md_to_pdf)
    register_renderer(registry, 'md_to_html', lambda _: render_md_to_html)
    register_renderer(registry, 'docx_to_html', lambda _: render_docx_to_html)
    register_renderer(registry, 'copy_asset', lambda _: render_copy_asset)

    pipeline = Pipeline(args.root, BUILD_DIR, registry)
    diagnostics = pipeline.execute(make_jobs(tags))
    if args.optimize_assets:
        diagnostics.extend(optimize_assets(BUILD_DIR))
    for message in diagnostics:
        print(message)

if __name__ == '__main__':
    main()
