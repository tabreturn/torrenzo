#!/usr/bin/env python3
"""CI helper — builds demo HTML (skips PDF, no Chrome needed)."""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from torrenzo.__main__ import build_tag_map, make_jobs, prepare_build_dir
from torrenzo.torrenzo_engine import Pipeline, RendererRegistry
from torrenzo.torrenzo_engine.renderers import (
    register_renderer, render_md_to_html,
    render_docx_to_html, render_copy_asset,
)
from torrenzo.torrenzo_engine.build_stamp import now_iso

root = Path('demo').resolve()
build_dir = root / 'build'
prepare_build_dir(build_dir, clean=False)
tags = build_tag_map(root)

registry = RendererRegistry()
register_renderer(registry, 'md_to_html', lambda _: render_md_to_html)
register_renderer(registry, 'docx_to_html', lambda _: render_docx_to_html)
register_renderer(registry, 'copy_asset', lambda _: render_copy_asset)

jobs = [j for j in make_jobs(tags, subject_root=root, built=now_iso())
        if j.renderer != 'md_to_pdf']

pipeline = Pipeline(root, build_dir, registry)
for msg in pipeline.execute(jobs, force=True):
    print(msg)
