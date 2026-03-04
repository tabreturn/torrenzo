from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from markdown_pdf import MarkdownPdf, Section

from torrenzo_engine.renderers.common import RenderResult
from torrenzo_engine.renderers.inline import run_inline_formatters

PDF_USER_CSS = (Path(__file__).resolve().parent.parent.parent / 'assessments' / 'style.css').read_text(encoding='utf-8')


def extract_metadata_from_front_matter(text: str) -> tuple[Dict[str, Any], str]:
    ...
