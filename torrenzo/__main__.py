#!/usr/bin/env python3
"""torrenzo.__main__
Converts assessment briefs into PDFs and module activities into
LMS-ready HTML snippets.
"""


import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .torrenzo_engine import Pipeline, RenderJob, RendererRegistry
from .torrenzo_engine.pipeline import fmt
from .torrenzo_engine.renderers import (
  register_renderer,
  render_md_to_pdf,
  render_md_to_html,
  render_docx_to_html,
  render_copy_asset,
)
from .torrenzo_engine.build_stamp import now_iso
from .torrenzo_engine.cc_export import export_cc
from .torrenzo_engine.tags import build_tag_map, find_outline, load_outline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
                cmd = [
                  png_tool, '--force', '--strip', '--ext', '.png', str(path)
                ]
            else:
                cmd = [
                  png_tool, '--strip', 'safe', '--opt', '3', '--fix',
                  str(path),
                ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                optimized_pngs += 1
            else:
                error = result.stderr.strip() or result.stdout.strip()
                tool_name = Path(png_tool).name
                rel = path.relative_to(build_dir)
                if error:
                    msg = f'PNG optimize failed ({tool_name}): {rel}: {error}'
                else:
                    msg = f'PNG optimize failed ({tool_name}): {rel}'
                messages.append(fmt('error', msg))
        if optimized_pngs:
            messages.append(fmt(
              'info',
              f'Optimized {optimized_pngs} PNG file(s) with '
              f'{Path(png_tool).name}',
            ))
    elif not png_tool:
        messages.append(fmt(
          'warning',
          'Skipping PNG optimization (pngquant or oxipng not installed)',
        ))
    elif not png_files:
        messages.append(fmt('info', 'No PNG assets to optimize'))

    scour_tool = locate_command(['scour'])
    svg_files = sorted(build_dir.rglob('*.svg'))
    if scour_tool and svg_files:
        import tempfile, os
        optimized_svgs = 0
        for path in svg_files:
            fd, tmp = tempfile.mkstemp(suffix='.svg')
            os.close(fd)
            tmp_path = Path(tmp)
            cmd = [
              scour_tool, '--quiet',
              '-i', str(path), '-o', str(tmp_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                tmp_path.replace(path)
                optimized_svgs += 1
            else:
                tmp_path.unlink(missing_ok=True)
                error = result.stderr.strip() or result.stdout.strip()
                rel = path.relative_to(build_dir)
                if error:
                    msg = f'SVG optimize failed (scour): {rel}: {error}'
                else:
                    msg = f'SVG optimize failed (scour): {rel}'
                messages.append(fmt('error', msg))
        if optimized_svgs:
            messages.append(fmt(
              'info', f'Optimized {optimized_svgs} SVG file(s) with scour'
            ))
    elif not scour_tool:
        messages.append(fmt(
          'warning',
          'Skipping SVG optimization (scour not installed; '
          'pip install scour)',
        ))
    elif not svg_files:
        messages.append(fmt('info', 'No SVG assets to optimize'))

    return messages


def prepare_build_dir(build_dir: Path, clean: bool = False) -> None:
    if build_dir.exists():
        if clean:
            for child in build_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    else:
        build_dir.mkdir(parents=True, exist_ok=True)


def make_jobs(
  tags: dict[str, str],
  subject_root: Path,
  built: str | None = None,
  version_stamp: str = '',
) -> list[RenderJob]:
    briefs_pattern = 'assessments/*/ass_*_brief.md'
    module_md_pattern = 'modules/*/mod_*.md'
    module_docx_pattern = 'modules/*/mod_*.docx'

    built = built or now_iso()

    outline = find_outline(subject_root)
    module_css = subject_root / 'modules' / 'style' / 'style.css'
    module_bib = subject_root / 'modules' / 'references.bib'
    assess_css = subject_root / 'assessments' / 'style' / 'style.css'
    assess_js = subject_root / 'assessments' / 'style' / 'config.js'
    assess_logo = subject_root / 'assessments' / 'style' / 'logo.svg'

    html_deps = [
      p for p in [outline, module_css, module_bib] if p.exists()
    ]
    pdf_deps = [
      p for p in [outline, assess_css, assess_js, assess_logo]
      if p.exists()
    ]

    return [
      RenderJob(
        name='assessment_briefs',
        input_pattern=briefs_pattern,
        output_dir=Path('assessments_briefs'),
        renderer='md_to_pdf',
        context={
          'tags': tags,
          'pdf_css': PDF_USER_CSS,
          'version_stamp': version_stamp,
          'header_html': (
            f'<div class="header">ver.2026-03-04 &nbsp; built: {built}</div>'
          ),
          'footer_html': '<div class="footer"></div>',
        },
        output_ext='.pdf',
        output_namer=lambda p: f'{p.parent.name}.pdf',
        deps=pdf_deps,
      ),
      RenderJob(
        name='module_md',
        input_pattern=module_md_pattern,
        output_dir=Path('modules_html'),
        renderer='md_to_html',
        context={'tags': tags, 'asset_dir': Path('modules_html/assets')},
        output_ext='.html',
        output_namer=lambda p: p.with_suffix('.html').name,
        deps=html_deps,
      ),
      RenderJob(
        name='module_docx',
        input_pattern=module_docx_pattern,
        output_dir=Path('modules_html'),
        renderer='docx_to_html',
        context={'tags': tags},
        output_ext='.html',
        output_namer=lambda p: p.with_suffix('.html').name,
        deps=html_deps,
      ),
      RenderJob(
        name='module_assets',
        input_pattern='modules/*/assets/**/*',
        output_dir=Path('modules_html/assets'),
        renderer='copy_asset',
        context={},
        output_ext='',
        output_namer=lambda p: p.name,
      ),
      RenderJob(
        name='lecturer_notes',
        input_pattern='notes/**/*',
        output_dir=Path('lecturer_notes'),
        renderer='copy_asset',
        context={},
        output_ext='',
        output_namer=lambda p: p.name,
      ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
      description=(
        'Convert assessment briefs to PDF and module activities '
        'to LMS-ready HTML snippets.'
      )
    )
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
    parser.add_argument(
      '--clean',
      action='store_true',
      help='Wipe build/ before building (forces full rebuild)',
    )
    parser.add_argument(
      '--force',
      action='store_true',
      help='Rebuild all files even if outputs are up-to-date',
    )
    parser.add_argument(
      '--cc',
      action='store_true',
      help='Export a Common Cartridge (.imscc) package after building',
    )
    args = parser.parse_args()

    subject_root = args.root.resolve()
    build_dir = subject_root / 'build'

    built = now_iso()
    version_stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    force = args.force or args.clean
    prepare_build_dir(build_dir, clean=args.clean)
    tags = build_tag_map(subject_root)

    registry = RendererRegistry()
    register_renderer(registry, 'md_to_pdf', lambda _: render_md_to_pdf)
    register_renderer(registry, 'md_to_html', lambda _: render_md_to_html)
    register_renderer(
      registry, 'docx_to_html', lambda _: render_docx_to_html
    )
    register_renderer(registry, 'copy_asset', lambda _: render_copy_asset)

    pipeline = Pipeline(subject_root, build_dir, registry)
    diagnostics = pipeline.execute(
      make_jobs(tags, subject_root=subject_root, built=built,
                version_stamp=version_stamp),
      force=force,
    )
    if args.optimize_assets:
        diagnostics.extend(optimize_assets(build_dir))
    if args.cc:
        outline = load_outline(subject_root)
        _, cc_diagnostics = export_cc(subject_root, build_dir, outline,
                                      version_stamp)
        diagnostics.extend(fmt('info', m) for m in cc_diagnostics)
    for message in diagnostics:
        print(message)


if __name__ == '__main__':
    main()
