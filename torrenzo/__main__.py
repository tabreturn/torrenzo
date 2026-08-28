#!/usr/bin/env python3

from __future__ import annotations

"""torrenzo.__main__
Converts assessment briefs into PDFs and module activities into
LMS-ready HTML snippets.
"""


import argparse
import shutil
import subprocess
import sys
import time
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
  render_assessment_html,
)
from .torrenzo_engine.build_stamp import now_iso
from .torrenzo_engine.cc_diff import diff_cc
from .torrenzo_engine.cc_export import export_cc
from .torrenzo_engine.live_server import LiveServer
from .torrenzo_engine.preprocess import cache_bust_filename
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
  cache_bust: str = '',
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
    includes_dir = subject_root / 'includes'

    html_deps = [
      p for p in [outline, module_css, module_bib, includes_dir] if p.exists()
    ]
    pdf_deps = [
      p for p in [outline, assess_css, assess_js, assess_logo, includes_dir]
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
          'subject_root': subject_root,
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
        context={'tags': tags, 'subject_root': subject_root, 'asset_dir': Path('modules_html/assets'), 'cache_bust': cache_bust},
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
        output_namer=(lambda p: cache_bust_filename(p.name, cache_bust))
        if cache_bust else (lambda p: p.name),
      ),
      RenderJob(
        name='lecturer_notes_md',
        input_pattern='notes/**/*.md',
        output_dir=Path('lecturer_notes'),
        renderer='md_to_html',
        context={
          'tags': tags,
          'subject_root': subject_root,
          'no_css': True,
          'plain_code': True,
          'bib_root': subject_root / 'modules',
          'cache_bust': cache_bust,
        },
        output_ext='.html',
        output_namer=lambda p: p.with_suffix('.html').name,
        deps=html_deps,
      ),
      RenderJob(
        name='lecturer_notes',
        input_pattern='notes/**/*',
        output_dir=Path('lecturer_notes'),
        renderer='copy_asset',
        context={},
        output_ext='',
        output_namer=(lambda p: cache_bust_filename(p.name, cache_bust))
        if cache_bust else (lambda p: p.name),
        input_filter=lambda p: p.suffix.lower() != '.md',
      ),
      RenderJob(
        name='assessment_briefs_html',
        input_pattern=briefs_pattern,
        output_dir=Path('assessments_html'),
        renderer='assessment_html',
        context={
          'tags': tags,
          'subject_root': subject_root,
          'cache_bust': cache_bust,
        },
        output_ext='.html',
        output_namer=lambda p: f'{p.parent.name}.html',
        deps=pdf_deps,
      ),
    ]


def run_build(
  subject_root: Path,
  build_dir: Path,
  *,
  force: bool = False,
  optimize: bool = False,
  cc: bool = False,
  diff_paths: list[Path] | None = None,
  diff_verbose: bool = False,
  cache_bust: str = '',
) -> None:
    """Execute a single (possibly incremental) build cycle."""
    built = now_iso()
    version_stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    tags = build_tag_map(subject_root)

    registry = RendererRegistry()
    register_renderer(registry, 'md_to_pdf', lambda _: render_md_to_pdf)
    register_renderer(registry, 'md_to_html', lambda _: render_md_to_html)
    register_renderer(
      registry, 'docx_to_html', lambda _: render_docx_to_html
    )
    register_renderer(registry, 'copy_asset', lambda _: render_copy_asset)
    register_renderer(
      registry, 'assessment_html', lambda _: render_assessment_html
    )

    pipeline = Pipeline(subject_root, build_dir, registry)
    diagnostics = pipeline.execute(
      make_jobs(tags, subject_root=subject_root, built=built,
        version_stamp=version_stamp, cache_bust=cache_bust),
      force=force,
    )
    if optimize:
        diagnostics.extend(optimize_assets(build_dir))
    if cc:
        outline = load_outline(subject_root)
        cc_path, cc_diagnostics = export_cc(subject_root, build_dir, outline,
          version_stamp,
          cache_bust=cache_bust)
        diagnostics.extend(fmt('info', m) for m in cc_diagnostics)
        if diff_paths:
            if len(diff_paths) != 2:
                diagnostics.append(fmt('error',
                  '--diff requires two paths: LOCAL.imscc LIVE.imscc'))
            else:
                lc, rv = diff_paths[0].resolve(), diff_paths[1].resolve()
                if not lc.exists():
                    diagnostics.append(
                      fmt('error', f'{diff_paths[0]}: file not found'))
                elif not rv.exists():
                    diagnostics.append(
                      fmt('error', f'{diff_paths[1]}: file not found'))
                else:
                    print()
                    print(diff_cc(lc, rv, verbose=diff_verbose))
    for message in diagnostics:
        print(message)


def _snapshot_mtimes(subject_root: Path) -> dict[Path, float]:
    """Return {path: mtime} for every source file, skipping build/."""
    build_dir = subject_root / 'build'
    snap: dict[Path, float] = {}
    for p in subject_root.rglob('*'):
        if p.is_dir():
            continue
        try:
            if p.is_relative_to(build_dir):
                continue
        except AttributeError:
            # python < 3.9 fallback
            try:
                p.relative_to(build_dir)
                continue
            except ValueError:
                pass
        try:
            snap[p] = p.stat().st_mtime
        except OSError:
            pass
    return snap


def watch_and_rebuild(
  subject_root: Path,
  build_dir: Path,
  *,
  optimize: bool = False,
  cc: bool = False,
  diff_paths: list[Path] | None = None,
  diff_verbose: bool = False,
  poll_interval: float = 1.0,
  live: bool = False,
  cache_bust: str = '',
) -> None:
    """Poll for source changes and rebuild incrementally."""
    server: LiveServer | None = None
    if live:
        server = LiveServer(build_dir)
        server.start()
        print(fmt('info', f'Live server at {server.url}'), flush=True)

    print(fmt('info', f'Watching {subject_root} for changes (Ctrl+C to stop)'),
      flush=True)
    prev = _snapshot_mtimes(subject_root)
    try:
        while True:
            time.sleep(poll_interval)
            curr = _snapshot_mtimes(subject_root)
            changed = {
              p for p in curr
              if p not in prev or curr[p] != prev[p]
            }
            deleted = set(prev) - set(curr)
            if changed or deleted:
                names = [p.relative_to(subject_root) for p in changed]
                if deleted:
                    names += [
                      p.relative_to(subject_root) for p in deleted
                    ]
                summary = ', '.join(str(n) for n in sorted(names)[:5])
                if len(names) > 5:
                    summary += f' (+{len(names) - 5} more)'
                print(flush=True)
                print(fmt('info',
                  f'Change detected: {summary}'), flush=True)
                run_build(subject_root, build_dir, force=False,
                  optimize=optimize, cc=cc,
                  diff_paths=diff_paths,
                  diff_verbose=diff_verbose,
                  cache_bust=cache_bust)
                sys.stdout.flush()
                if server:
                    server.notify_reload()
                prev = _snapshot_mtimes(subject_root)
            else:
                prev = curr
    except KeyboardInterrupt:
        print(flush=True)
        print(fmt('info', 'Watch stopped'), flush=True)
    finally:
        if server:
            server.stop()


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
    parser.add_argument(
      '--diff',
      nargs='+',
      type=Path,
      default=None,
      metavar=('LOCAL', 'LIVE'),
      help='Diff two .imscc files, or auto-discover local if only one given',
    )
    parser.add_argument(
      '--diff-verbose',
      action='store_true',
      help='Show full content diffs in --diff output',
    )
    parser.add_argument(
      '--watch',
      action='store_true',
      help='Watch source files and rebuild incrementally on change',
    )
    parser.add_argument(
      '--live',
      action='store_true',
      help='Start a live-reload HTTP server (implies --watch)',
    )
    parser.add_argument(
      '--cache-bust',
      nargs='?',
      const='__auto__',
      default='',
      metavar='TAG',
      help=(
        'Append a cache-busting suffix to asset filenames and HTML '
        'references. Provide a custom tag (e.g. "v2") or omit for '
        'an auto-generated date stamp (vYYYYMMDD).'
      ),
    )
    args = parser.parse_args()
    if args.live:
        args.watch = True
    cache_bust = args.cache_bust or ''
    if cache_bust == '__auto__':
        cache_bust = datetime.now().strftime('v%Y%m%d_%H%M%S')

    # diff-only mode: no build needed
    if args.diff and not args.cc and not args.force and not args.clean:
        if len(args.diff) != 2:
            print(fmt('error', '--diff requires two paths: LOCAL.imscc LIVE.imscc'))
            return
        lc, rv = args.diff[0].resolve(), args.diff[1].resolve()
        if not lc.exists():
            print(fmt('error', f'{args.diff[0]}: file not found'))
        elif not rv.exists():
            print(fmt('error', f'{args.diff[1]}: file not found'))
        else:
            print(diff_cc(lc, rv, verbose=args.diff_verbose))
        return

    subject_root = args.root.resolve()
    build_dir = subject_root / 'build'

    force = args.force or args.clean
    prepare_build_dir(build_dir, clean=args.clean)

    if cache_bust:
        print(fmt('info', f'Cache-bust suffix: _{cache_bust}'))

    run_build(subject_root, build_dir, force=force,
      optimize=args.optimize_assets, cc=args.cc,
      diff_paths=args.diff, diff_verbose=args.diff_verbose,
      cache_bust=cache_bust)

    if args.watch:
        watch_and_rebuild(subject_root, build_dir,
          optimize=args.optimize_assets, cc=args.cc,
          diff_paths=args.diff,
          diff_verbose=args.diff_verbose,
          live=args.live,
          cache_bust=cache_bust)


if __name__ == '__main__':
    main()
