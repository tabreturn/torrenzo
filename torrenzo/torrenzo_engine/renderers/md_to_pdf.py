from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from markdown_it import MarkdownIt

from . import highlight as _hl
from ..build_stamp import now_iso
from ..preprocess import convert_dashes, expand_wiki_links, resolve_includes, rewrite_md_hrefs, collect_valid_outputs, check_asset_refs, apply_image_style_directives, rewrite_video_images, _FILE_ISH_RE
from ...components import PARAMETERIZED_COMPONENTS, build_component_tags

# Chrome/Puppeteer PDFs under-report trailer /Size; pypdf logs a harmless
# warning each time we reopen one for metadata stamping. Silence it.
logging.getLogger('pypdf').setLevel(logging.ERROR)


DATAVIEW_RE = re.compile(r'`?=\s*\[\[([^\]]+)\]\](?:\.([^\s`\[\]]+))?`?')
BARE_TAG_RE = re.compile(r'(?<!=)\[\[([^\]]+)\]\](?:\.([^\s`\[\]]+))?')
DATAVIEW_BLOCK_RE = re.compile(
  r'```dataview\s+LIST without id slo\[x\]\s+FROM "outline"\s+'
  r'FLATTEN ([^\s]+) AS x\s+```',
  re.I | re.S,
)
FRONT_MATTER_RE = re.compile(r'\A---\n(.*?)\n---\n', re.S)
METADATA_TOKEN = '<<metadata_table>>'


def _stamp_pdf_metadata(pdf_path: Path, source: Path, title: str, body: str, ts: str) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(pdf_path))
        writer = PdfWriter(clone_from=reader)
        writer.add_metadata({
          '/Producer': 'torrenzo',
          '/Title': title,
          '/Subject': source.name,
          '/Keywords': f'built: {ts}',
        })
        # open with outline pane visible, fit-to-width on first page
        writer.page_mode = '/UseOutlines'
        writer.page_layout = '/SinglePage'
        writer.open_destination = writer.pages[0] if writer.pages else None
        # add PDF outlines from markdown headings (body has tags resolved)
        _add_pdf_outlines(writer, reader, body)
        fd, tmp = tempfile.mkstemp(suffix='.pdf', dir=pdf_path.parent)
        os.close(fd)
        with open(tmp, 'wb') as f:
            writer.write(f)
        os.replace(tmp, pdf_path)
    except Exception:
        pass


def _add_pdf_outlines(
  writer: Any,
  reader: Any,
  body: str,
) -> None:
    """Add PDF outline/bookmarks from markdown headings."""
    from pypdf.generic import Fit

    md = MarkdownIt('commonmark').enable('table').enable('strikethrough')
    tokens = md.parse(body)
    headings: list[tuple[int, str]] = []
    html_strip = re.compile(r'<[^>]+>')
    for i, token in enumerate(tokens):
        if token.type != 'heading_open':
            continue
        level = int(token.tag[1])
        if i + 1 < len(tokens) and tokens[i + 1].type == 'inline':
            html = md.renderInline(tokens[i + 1].content)
            text = html_strip.sub('', html).strip()
            headings.append((level, text))

    if not headings:
        return

    last_parent: dict[int, Any] = {}
    for level, text in headings:
        found_page = None
        for i, page in enumerate(reader.pages):
            page_text = (page.extract_text() or '').replace('\n', ' ')
            if text in page_text:
                found_page = i
                break
        if found_page is None:
            continue
        parent = None
        for l in range(level - 1, 0, -1):
            if l in last_parent and last_parent[l] is not None:
                parent = last_parent[l]
                break
        item = writer.add_outline_item(
          text, found_page, parent=parent,
        )
        last_parent[level] = item


def _find_chrome() -> str | None:
    env_path = os.environ.get('PUPPETEER_EXECUTABLE_PATH')
    if env_path and Path(env_path).exists():
        return env_path

    candidates: list[str] = []
    if sys.platform == 'linux':
        candidates = [
          'google-chrome', 'google-chrome-stable',
          'chromium', 'chromium-browser',
        ]
    elif sys.platform == 'darwin':
        candidates = [
          '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
          '/Applications/Chromium.app/Contents/MacOS/Chromium',
        ]
    elif sys.platform == 'win32':
        candidates = [
          'chrome', 'chromium',
          'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
          'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        ]

    for candidate in candidates:
        if '/' in candidate or '\\' in candidate:
            if Path(candidate).exists():
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None


def _parse_config_js(config_path: Path, version_override: str = '') -> Dict[str, Any]:
    text = config_path.read_text(encoding='utf-8')
    # keep only from module.exports = onward
    match = re.search(r'module\.exports\s*=\s*', text)
    if not match:
        return {}
    text = text[match.end():].strip().rstrip(';')
    # remove leading block comment if any
    text = re.sub(r'^/\*.*?\*/\s*', '', text, flags=re.DOTALL)
    # replace process.env.X || undefined → null
    text = re.sub(r'process\.env\.\w+(?:\s*\|\|\s*undefined)?', 'null', text)
    # capture template literals
    templates: list[str] = []
    def _capture(m: re.Match[str]) -> str:
        templates.append(m.group(1))
        return f'"__TPL_{len(templates) - 1}__"'
    text = re.sub(r'`([^`]*)`', _capture, text)
    # remove JS comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'//[^\n]*', '', text)
    # quote unquoted keys (word before colon that's not already quoted)
    text = re.sub(
      r'([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:',
      r'\1"\2":',
      text,
    )
    # remove trailing commas
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    # convert single-quoted values to double-quoted (JSON)
    text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}

    def _restore(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _restore(v) for k, v in obj.items()}
        if isinstance(obj, str) and obj.startswith('__TPL_'):
            idx = int(obj[len('__TPL_'):-len('__')])
            return templates[idx]
        return obj

    # extract versionDate = new Date().toISOString().slice(0, 10);
    raw = config_path.read_text(encoding='utf-8')
    ver_match = re.search(
      r"const\s+versionDate\s*=\s*new\s+Date\(\)"
      r"\.toISOString\(\)\.slice\(\s*0\s*,\s*10\s*\)",
      raw,
    )
    version_date = ''
    if ver_match:
        from datetime import date
        version_date = version_override or date.today().isoformat()

    result = _restore(parsed)
    # interpolate ${versionDate} in templates
    if version_date:
        for key in ('headerTemplate', 'footerTemplate'):
            po = result.get('pdf_options', {})
            if key in po and '${versionDate}' in po[key]:
                po[key] = po[key].replace('${versionDate}', version_date)
    return result


async def _render_pdf_async(
  html_path: Path,
  output_path: Path,
  config: Dict[str, Any],
  chrome_path: str | None,
) -> None:
    # pyppeteer import deferred so pip install order does not matter
    from pyppeteer import launch
    browser = await launch(
      headless=True,
      executablePath=chrome_path,
      args=['--no-sandbox', '--disable-setuid-sandbox',
            '--disable-dev-shm-usage'],
    )
    try:
        page = await browser.newPage()
        await page.goto(
          html_path.as_uri(),
          waitUntil='networkidle0',
        )
        pdf_opts = config.get('pdf_options', {})
        await page.pdf({
          'path': str(output_path),
          'format': pdf_opts.get('format', 'A4'),
          'margin': pdf_opts.get('margin', {}),
          'displayHeaderFooter': pdf_opts.get(
            'displayHeaderFooter', False,
          ),
          'headerTemplate': pdf_opts.get('headerTemplate', ''),
          'footerTemplate': pdf_opts.get('footerTemplate', ''),
          'printBackground': True,
        })
    finally:
        await browser.close()


def extract_metadata_from_front_matter(
  text: str,
) -> tuple[Dict[str, Any], str, list[str]]:
    warnings: list[str] = []
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text, warnings
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except Exception as exc:
        metadata = {}
        warnings.append(f'Invalid front matter: {exc}')
    body = text[match.end():]
    return metadata, body, warnings


def build_metadata_table(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ''
    lines: list[str] = [
      '<table>',
      '<thead><tr><th>Field</th><th>Details</th></tr></thead>',
      '<tbody>',
    ]
    for key, value in metadata.items():
        field = key.replace('_', ' ').title()
        if isinstance(value, list):
            detail = '<br>'.join(str(item) for item in value)
        else:
            detail = str(value)
        lines.append(f'<tr><td>{field}</td><td>{detail}</td></tr>')
    lines.append('</tbody></table>')
    return '\n'.join(lines)


def apply_tags(
  text: str,
  tags: dict[str, str],
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    missing_placeholders: set[str] = set()

    def add_warning(label: str) -> None:
        if label and label not in missing_placeholders:
            missing_placeholders.add(label)
            warnings.append(f"Missing placeholder value for '{label}'")

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
        if lookup_keys:
            add_warning(lookup_keys[0])
        return original

    def replace_dataview_block(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        candidates: list[str] = [f'outline.{path}']
        parts = path.split('.')
        if len(parts) >= 2 and parts[0].lower() == 'assessment':
            aid_token = parts[1]
            aid_num = (
              aid_token.removeprefix('ass')
              if aid_token.lower().startswith('ass')
              else aid_token
            )
            candidates = [
              f'assessment|{aid_token}|slo',
              f'assessment|{aid_num}|slo',
              f'outline.{path}',
            ]
        for key in candidates:
            snippet = tags.get(key)
            if snippet is not None:
                return snippet
        if candidates:
            add_warning(candidates[0])
        return match.group(0)

    def replace_dv_inline(match: re.Match[str]) -> str:
        prefix = match.group(1)
        suffix = match.group(2)
        if suffix:
            return replace_content(f'outline.{suffix}', match.group(0))
        return replace_content(f'outline.{prefix}', match.group(0))

    def replace_bare_tag(match: re.Match[str]) -> str:
        inner = match.group(1)
        suffix = match.group(2)
        if suffix:
            return replace_content(f'outline.{suffix}', match.group(0))
        if '|' in inner:
            name, _, arg = inner.partition('|')
            if name.startswith('component.'):
                comp_key = name[len('component.'):]
                renderer = PARAMETERIZED_COMPONENTS.get(comp_key)
                if renderer is not None:
                    return renderer(arg)
            snippet = tags.get(inner)
            if snippet is not None:
                return snippet
            if _FILE_ISH_RE.search(inner):
                return match.group(0)
            return replace_content(inner, match.group(0))
        if '.' not in inner or '/' in inner:
            return match.group(0)
        return replace_content(f'outline.{inner}', match.group(0))

    replaced = DATAVIEW_RE.sub(replace_dv_inline, text)
    replaced = BARE_TAG_RE.sub(replace_bare_tag, replaced)
    replaced = DATAVIEW_BLOCK_RE.sub(
      lambda m: replace_dataview_block(m),
      replaced,
    )
    return replaced, warnings


def render(
  input_path: Path,
  output_path: Path,
  context: Dict[str, Any],
) -> Tuple[bool, str, list[str]]:
    tags = context.get('tags', {})
    tags = {**tags, **build_component_tags(input_path)}

    raw_content = input_path.read_text(encoding='utf-8')
    metadata, body, meta_warnings = extract_metadata_from_front_matter(
      raw_content
    )
    warnings: list[str] = list(meta_warnings)
    if METADATA_TOKEN in body and metadata:
        body = body.replace(METADATA_TOKEN, build_metadata_table(metadata))
    body, include_warnings = resolve_includes(
        body, context.get('subject_root', input_path.parent.parent.parent))
    from ..preprocess import strip_tagged_sections
    body = strip_tagged_sections(body, '[[cc-section|hide-in-pdf]]')
    body = body.replace('[[cc-section]]', '')
    body = rewrite_video_images(body)
    body, tag_warnings = apply_tags(body, tags)
    body, link_warnings = expand_wiki_links(body, collect_valid_outputs(
        input_path.parent.parent.parent))
    body = rewrite_md_hrefs(body)
    body = convert_dashes(body)
    warnings.extend(tag_warnings)
    warnings.extend(include_warnings)
    warnings.extend(link_warnings)
    warnings.extend(check_asset_refs(body, input_path))

    md = MarkdownIt('commonmark').enable('table').enable('strikethrough')
    _hl.install(md)

    workdir = input_path.parent
    style_src = input_path.parent.parent / 'style'
    style_dst = workdir / 'style'
    config_src = style_src / 'config.js'
    style_css_src = style_src / 'style.css'
    logo_path = style_src / 'logo.svg'
    has_style = style_src.exists()
    has_config = config_src.exists()

    if not has_config:
        warnings.append(
          f'Missing config.js for {input_path.name}; '
          f'building with defaults'
        )

    created_style = False
    temp_html_path: Path | None = None
    success = False
    msg = ''

    try:
        if has_style:
            if style_dst.exists():
                shutil.rmtree(style_dst, ignore_errors=True)
            shutil.copytree(style_src, style_dst)
            created_style = True

        # parse config for pdf_options and chrome path
        config = _parse_config_js(
            config_src, version_override=context.get('version_stamp', '')
        ) if has_config else {}
        chrome_path = config.get(
          'launch_options', {},
        ).get('executablePath') or _find_chrome()

        if not chrome_path:
            return (
              False,
              f'{input_path} -> {output_path} failed: '
              f'no Chrome/Chromium found. Install Chrome or set '
              f'PUPPETEER_EXECUTABLE_PATH',
              warnings,
            )

        # render markdown → HTML body
        html_body = md.render(body)
        html_body = apply_image_style_directives(html_body)

        # inline logo SVG into header template
        logo_markup = ''
        if logo_path.exists():
            logo_markup = logo_path.read_text(encoding='utf-8').strip()

        # build full HTML document with inlined CSS
        # (inlining ensures font url() paths resolve relative
        #  to the HTML file, matching md-to-pdf behavior)
        css_content = ''
        if has_style and style_css_src.exists():
            css_content = style_css_src.read_text(encoding='utf-8')

        # inject header/footer with logo
        header_html = config.get(
          'pdf_options', {},
        ).get('headerTemplate', '')
        footer_html = config.get(
          'pdf_options', {},
        ).get('footerTemplate', '')
        if logo_markup and 'INLINE_LOGO_MARKUP' in header_html:
            header_html = header_html.replace(
              '<!--INLINE_LOGO_MARKUP-->', logo_markup,
            )
        # override templates in config for pyppeteer
        pdf_opts = config.get('pdf_options', {}).copy()
        pdf_opts['headerTemplate'] = header_html
        pdf_opts['footerTemplate'] = footer_html
        render_config: Dict[str, Any] = {
          'pdf_options': pdf_opts,
        }

        # derive title from first h1 in processed body, fallback to filename
        h1_match = re.search(r'^#\s+(.+)$', body, re.M)
        doc_title = h1_match.group(1).strip() if h1_match else input_path.stem

        full_html = (
          '<!DOCTYPE html>\n'
          '<html><head>\n'
          '<meta charset="utf-8">\n'
          f'<title>{doc_title}</title>\n'
          f'<style>{css_content}</style>\n'
          '</head><body>\n'
          f'{html_body}\n'
          '</body></html>'
        )

        # write temp HTML in workdir (so relative CSS/font paths resolve)
        fd, tmp_path = tempfile.mkstemp(
          suffix='.html', dir=str(workdir),
        )
        os.close(fd)
        temp_html_path = Path(tmp_path)
        temp_html_path.write_text(full_html, encoding='utf-8')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(
          _render_pdf_async(
            temp_html_path, output_path, render_config, chrome_path,
          )
        )

        success = output_path.exists()
        if success:
            _stamp_pdf_metadata(output_path, input_path, doc_title, body, now_iso())
            msg = f'{input_path} -> {output_path}'
        else:
            msg = f'{input_path} -> {output_path} failed: no output'
    except Exception as exc:
        msg = f'{input_path} -> {output_path} failed: {exc}'
    finally:
        if temp_html_path and temp_html_path.exists():
            temp_html_path.unlink(missing_ok=True)
        if created_style and style_dst.exists():
            shutil.rmtree(style_dst, ignore_errors=True)

    return success, msg, warnings
