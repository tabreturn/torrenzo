from __future__ import annotations

from pathlib import Path
import logging
import re
from typing import Any, Dict, Tuple

from markdown_it import MarkdownIt
from premailer import transform
from lxml import html as lxml_html
from pybtex.database import parse_file

from .bib_to_html import render_entry_to_html
from . import highlight as _hl
from .md_to_pdf import apply_tags
from ..build_stamp import html_comment, now_iso
from ..preprocess import convert_dashes, unicode_to_entities, expand_wiki_links, resolve_includes, rewrite_md_hrefs, collect_valid_outputs, check_asset_refs, apply_image_style_directives, cache_bust_asset_refs, rewrite_video_images
from ...components import build_component_tags, render_page_spacer


CITATION_BRACKET_RE = re.compile(r'\[@([^\]]+)\]')


def load_module_css(input_path: Path) -> str:
    modules_dir = input_path.parent.parent
    css_path = modules_dir / 'style' / 'style.css'
    if css_path.exists():
        return css_path.read_text(encoding='utf-8')
    return ''


def substitute_css_variables(css_text: str) -> str:
    root_blocks = re.findall(r':root\s*{([^}]*)}', css_text, re.S)
    mapping: dict[str, str] = {}
    for block in root_blocks:
        for match in re.finditer(
          r'--([A-Za-z0-9_-]+)\s*:\s*([^;]+);', block
        ):
            name = match.group(1).strip()
            value = match.group(2).strip()
            if name:
                mapping[name] = value
    if not mapping:
        return css_text

    def replace_var(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        fallback = match.group(2).strip() if match.group(2) else None
        if name in mapping:
            return mapping[name]
        if fallback is not None:
            return fallback
        return match.group(0)

    substituted = re.sub(
      r'var\(\s*--([A-Za-z0-9_-]+)(?:\s*,\s*([^)]+))?\)',
      replace_var,
      css_text,
    )
    substituted = re.sub(r':root\s*{[^}]*}', '', substituted, flags=re.S)
    substituted = re.sub(
      r'\s*--[A-Za-z0-9_-]+\s*:\s*[^;]+;\s*', '', substituted
    )
    return substituted


def strip_html_wrapper(html_text: str) -> str:
    try:
        document = lxml_html.fromstring(html_text)
    except Exception:
        return html_text
    body = document.find('body')
    if body is None:
        return html_text
    inner = body.text or ''
    for child in body:
        inner += lxml_html.tostring(child, encoding='unicode', method='html')
        if child.tail:
            inner += child.tail
    return inner


def sanitize_html_attributes(html_text: str) -> str:
    try:
        document = lxml_html.fromstring(html_text)
    except Exception:
        return html_text
    unwanted = {'bgcolor', 'color', 'background', 'text', 'link', 'alink', 'vlink'}
    for element in document.iter():
        for attr in list(element.attrib):
            if attr.lower() in unwanted:
                del element.attrib[attr]
    return lxml_html.tostring(document, encoding='unicode', method='html')


_FONT_WEIGHT_RE = re.compile(r'font-weight\s*:\s*(bold|700|bolder)\s*;?\s*')





def replace_inline_bold(html_text: str) -> str:
    try:
        document = lxml_html.fromstring(html_text)
    except Exception:
        return html_text
    for elem in document.iter():
        style = elem.get('style', '')
        if not style:
            continue
        m = _FONT_WEIGHT_RE.search(style)
        if not m:
            continue
        new_style = _FONT_WEIGHT_RE.sub('', style).strip()
        if new_style:
            elem.set('style', new_style)
        else:
            del elem.attrib['style']
        b = lxml_html.Element('b')
        b.text = elem.text
        elem.text = None
        for child in list(elem):
            b.append(child)
        elem.append(b)
    return lxml_html.tostring(document, encoding='unicode', method='html')


def load_bibliography(
  input_path: Path,
  warnings: list[str] | None = None,
) -> dict[str, Any]:
    modules_root = input_path.parent.parent
    entries: dict[str, Any] = {}
    bib_paths = [
      modules_root / 'references.bib',
      *sorted(modules_root.glob('mod_*_resources*.bib')),
    ]
    for bib_path in bib_paths:
        if not bib_path.exists():
            continue
        try:
            bib_data = parse_file(str(bib_path))
        except Exception as exc:
            if warnings is not None:
                warnings.append(f'Failed to parse {bib_path.name}: {exc}')
            continue
        for key, entry in bib_data.entries.items():
            if key not in entries:
                entries[key] = entry
    return entries


def collect_citation_numbers(
  text: str,
  bib_entries: dict[str, Any],
) -> tuple[dict[str, int], list[str], list[str]]:
    mapping: dict[str, int] = {}
    ordered: list[str] = []
    missing: list[str] = []

    def add_key(key: str) -> None:
        if key in bib_entries:
            if key not in mapping:
                mapping[key] = len(mapping) + 1
                ordered.append(key)
        elif key not in missing:
            missing.append(key)

    for match in CITATION_BRACKET_RE.finditer(text):
        raw_keys = match.group(1)
        for token in re.split(r'[;,]', raw_keys):
            key = token.strip().lstrip('@')
            if key:
                add_key(key)
    return mapping, ordered, missing


def replace_citations(text: str, mapping: dict[str, int]) -> str:
    def replace_bracket(match: re.Match[str]) -> str:
        raw_keys = match.group(1)
        pieces: list[str] = []
        for token in re.split(r'[;,]', raw_keys):
            key = token.strip().lstrip('@')
            if not key:
                continue
            number = mapping.get(key)
            if number is None:
                pieces.append(f'[@{key}]')
            else:
                pieces.append(f'<sup><a href="#ref-{key}">[{number}]</a></sup>')
        return ' '.join(pieces) if pieces else match.group(0)

    text = CITATION_BRACKET_RE.sub(replace_bracket, text)
    return text


def render_references(
  keys_in_order: list[str],
  bib_entries: dict[str, Any],
  warnings: list[str] | None = None,
) -> str:
    if not keys_in_order:
        return ''
    items: list[str] = []
    for key in keys_in_order:
        entry = bib_entries.get(key)
        if entry is None:
            continue
        try:
            html_block = render_entry_to_html(entry)
        except Exception as exc:
            if warnings is not None:
                warnings.append(f"Could not format entry '{key}': {exc}")
            continue
        items.append(f'<li id="ref-{key}">{html_block}</li>')
    if not items:
        return ''
    return '\n'.join(['<h2>References</h2>', '<ol>', *items, '</ol>'])


def render(
  input_path: Path,
  output_path: Path,
  context: Dict[str, Any],
) -> Tuple[bool, str, list[str]]:
    tags = context.get('tags', {})
    tags = {**tags, **build_component_tags(input_path)}
    md = MarkdownIt('commonmark').enable('table').enable('strikethrough')
    _hl.install(md)
    raw = input_path.read_text(encoding='utf-8')

    raw, include_warnings = resolve_includes(
      raw, context.get('subject_root', input_path.parent.parent.parent))
    raw = raw.replace('[[cc-section|hide-in-pdf]]', '')
    raw = raw.replace('[[cc-section]]', '')
    raw = rewrite_video_images(raw)
    raw, tag_warnings = apply_tags(raw, tags)
    raw, link_warnings = expand_wiki_links(raw, collect_valid_outputs(
      input_path.parent.parent.parent))
    raw = rewrite_md_hrefs(raw)
    raw = convert_dashes(raw)

    warnings: list[str] = list(tag_warnings)
    warnings.extend(include_warnings)
    warnings.extend(link_warnings)
    warnings.extend(check_asset_refs(raw, input_path))
    bib_entries = load_bibliography(input_path, warnings)
    citation_numbers, ordered_keys, missing_keys = collect_citation_numbers(
      raw, bib_entries
    )
    if citation_numbers:
        raw = replace_citations(raw, citation_numbers)

    css_text = load_module_css(input_path)
    if not css_text:
        warnings.append(
          f'No modules/style/style.css found; {input_path.name} built unstyled'
        )
    css_text = substitute_css_variables(css_text)
    html_body = md.render(raw)
    html_body = apply_image_style_directives(html_body)
    if ordered_keys:
        references = render_references(ordered_keys, bib_entries, warnings)
        if references:
            html_body = f'{html_body}\n{references}'
    html_body = f'{html_body}\n{render_page_spacer()}'
    if css_text.strip():
        try:
            import cssutils
            cssutils.log.setLevel(logging.CRITICAL)
            html_body = transform(
              html_body,
              css_text=css_text,
              remove_classes=False,
            )
            html_body = sanitize_html_attributes(html_body)
            html_body = replace_inline_bold(html_body)
            html_body = strip_html_wrapper(html_body)
        except Exception as exc:
            return (
              False,
              f'{input_path} -> {output_path} failed to inline CSS: {exc}',
              [],
            )

    html_body = unicode_to_entities(html_body)
    cache_bust = context.get('cache_bust', '')
    if cache_bust:
        html_body = cache_bust_asset_refs(html_body, cache_bust)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
      html_comment(input_path, now_iso()) + html_body,
      encoding='utf-8',
    )

    if missing_keys:
        warnings.append(f"Missing citations: {', '.join(missing_keys)}")

    return True, f'{input_path} -> {output_path}', warnings
