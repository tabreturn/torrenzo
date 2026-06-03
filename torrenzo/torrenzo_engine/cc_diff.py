from __future__ import annotations

"""cc_diff -- compare two IMS Common Cartridge (.imscc) files.

Extracts and diffs WikiPages, assessments, assets, and module structure.
Designed to compare a local Torrenzo build against a live Canvas export.
"""

import difflib
import hashlib
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

CC_NS = 'http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1'
CANVAS_NS = 'http://canvas.instructure.com/xsd/cccv1p0'


# ---------------------------------------------------------------------------
# Filename normalisation
# ---------------------------------------------------------------------------

def _normalize_filename(fn: str) -> str:
    """Normalize dashes, underscores, and Canvas module-N renames."""
    CANVAS_RENAME = {
        'module-1-introduction-2.html': 'mod_01_01_introduction.html',
        'module-1-activities-2.html': 'mod_01_04_activities.html',
    }
    fn = CANVAS_RENAME.get(fn, fn)
    return re.sub(r'[-_]', '_', fn)


MOD_HTML_FILENAME_RE = re.compile(
    r'^mod[-_]\d+[-_]\d+[-_].+\.html$'
    r'|^module[-_]\d+[-_].+[-_]\d+\.html$')


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _extract_zip(path: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix='cc_diff_'))
    with zipfile.ZipFile(path) as zf:
        zf.extractall(tmp)
    return tmp


def _parse_manifest(tmp: Path) -> dict[str, Any]:
    manifest_path = tmp / 'imsmanifest.xml'
    if not manifest_path.exists():
        return {}
    tree = ET.parse(str(manifest_path))
    root = tree.getroot()
    ns = {
        'cc': CC_NS,
        'lomimscc': 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest',
    }

    title_el = root.find(
        './/cc:metadata/lomimscc:lom/lomimscc:general/'
        'lomimscc:title/lomimscc:string', ns)
    title = title_el.text.strip() if title_el is not None else ''

    modules: list[dict] = []
    org = root.find('.//cc:organizations/cc:organization', ns)
    if org is not None:
        for item in org.iterfind('cc:item', ns):
            mod_title = (item.findtext('cc:title', default='', namespaces=ns)
                         .strip())
            pages: list[dict] = []
            for sub in item.iterfind('cc:item', ns):
                ptitle = (sub.findtext('cc:title', default='', namespaces=ns)
                          .strip())
                ref = sub.get('identifierref', '')
                pages.append({'title': ptitle, 'identifierref': ref})
            modules.append({'title': mod_title, 'pages': pages})

    resources: dict[str, dict] = {}
    for res in root.iterfind('.//cc:resources/cc:resource', ns):
        rid = res.get('identifier', '')
        rtype = res.get('type', '')
        href = res.get('href', '')
        resources[rid] = {'type': rtype, 'href': href}

    return {'title': title, 'modules': modules, 'resources': resources}


def _read_wiki_pages(tmp: Path) -> dict[str, str]:
    wiki_dir = tmp / 'wiki_content'
    if not wiki_dir.exists():
        return {}
    pages: dict[str, str] = {}
    for f in sorted(wiki_dir.iterdir()):
        if MOD_HTML_FILENAME_RE.match(f.name):
            text = f.read_text(encoding='utf-8', errors='replace')
            key = _normalize_filename(f.name)
            pages[key] = _normalize_html_body(text)
    return pages


def _read_assessments(tmp: Path) -> list[dict]:
    result: list[dict] = []
    for d in sorted(tmp.iterdir()):
        if not d.is_dir() or not re.match(r'^g[0-9a-f]+$', d.name):
            continue
        settings = d / 'assignment_settings.xml'
        html_files = sorted(d.glob('*.html'))
        if not settings.exists():
            continue

        tree = ET.parse(str(settings))
        root = tree.getroot()
        ns = {'c': CANVAS_NS}
        title = root.findtext('c:title', default='', namespaces=ns).strip()
        points = float(root.findtext('c:points_possible', default='0',
                                     namespaces=ns))
        rubric_ref = root.findtext('c:rubric_identifierref', default='',
                                   namespaces=ns)
        body = ''
        if html_files:
            body = _normalize_html_body(html_files[0].read_text(
                encoding='utf-8', errors='replace'))
        result.append({
            'title': title,
            'points': points,
            'rubric_ref': rubric_ref,
            'body': body,
        })
    return result


def _sha_short(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


_PDF_TIMESTAMP_RE = re.compile(r'ver\.\s*\d{8}-\d{6}')


def _pdf_content_hash(path: Path) -> str:
    """Hash of PDF text content with build timestamp stripped."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        text = _PDF_TIMESTAMP_RE.sub('', text)
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
    except Exception:
        return _sha_short(path)


ASSESS_PDF_TS_RE = re.compile(
    r'^(assessment_\d{2})-\d{8}-\d{6}(?:-\d+)?(\.pdf)$')
ASSESS_PDF_TS_BODY_RE = re.compile(
    r'(assessment_\d{2})-\d{8}-\d{6}(?:-\d+)?(\.pdf)')

ASSESS_PDF_RE = re.compile(r'^assessment_\d{2}')


def _normalize_asset_key(rel: str) -> str:
    return ASSESS_PDF_TS_RE.sub(r'\1-TIMESTAMP\2', rel)


def _is_assessment_pdf(rel: str) -> bool:
    return bool(ASSESS_PDF_RE.match(rel))


def _read_assets(tmp: Path) -> dict[str, tuple[str, str, int]]:
    """Return {normalized_key: (original_name, sha12, size_bytes)}."""
    assets_dir = tmp / 'web_resources'
    if not assets_dir.exists():
        return {}
    result: dict[str, tuple[str, str, int]] = {}
    for f in sorted(assets_dir.rglob('*')):
        if f.is_file() and 'lecturer_notes' not in str(f):
            rel = str(f.relative_to(assets_dir))
            key = _normalize_asset_key(rel)
            sha = _pdf_content_hash(f) if _is_assessment_pdf(rel) else _sha_short(f)
            result[key] = (rel, sha, f.stat().st_size)
    return result


def _read_course_settings(tmp: Path) -> dict[str, str]:
    cs_dir = tmp / 'course_settings'
    if not cs_dir.exists():
        return {}
    result: dict[str, str] = {}
    for f in cs_dir.iterdir():
        if f.is_file():
            result[f.name] = f.read_text(encoding='utf-8', errors='replace')
    return result


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

GUID_RE = re.compile(r'g[0-9a-f]{32}')
API_URL_RE = re.compile(
    r'\s*data-api-endpoint=["\'][^"\']*["\']\s*')
API_RETURN_RE = re.compile(
    r'\s*data-api-returntype=["\'][^"\']*["\']\s*')
LOADING_ATTR_RE = re.compile(r'\s*loading=["\'][^"\']*["\']\s*')


STYLE_ATTR_RE = re.compile(r'style="([^"]+)"')


def _normalize_html_body(html: str) -> str:
    body = html
    m = re.search(r'<body[^>]*>(.*)</body>', html, re.S)
    if m:
        body = m.group(1)

    body = body.replace('%24IMS-CC-FILEBASE%24', '$IMS-CC-FILEBASE$')
    body = ASSESS_PDF_TS_BODY_RE.sub(r'\1-TIMESTAMP\2', body)
    body = GUID_RE.sub('GUID', body)
    body = API_URL_RE.sub(' ', body)
    body = API_RETURN_RE.sub(' ', body)
    body = LOADING_ATTR_RE.sub(' ', body)
    body = re.sub(r'\s+align=["\'][^"\']*["\']', '', body)
    # HTML entities → unicode
    body = body.replace('&ndash;', '\u2013')
    body = body.replace('&mdash;', '\u2014')
    body = body.replace('&times;', '\u00d7')
    body = body.replace('&rarr;', '\u2192')
    body = body.replace('&hellip;', '\u2026')
    body = body.replace('&deg;', '\u00b0')
    body = body.replace('&nbsp;', ' ')
    # Canvas strips HTML comments on import; normalize both sides
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    # Canvas adds trailing empty paragraphs
    body = body.replace('<p></p>', '')
    # Normalize component-navigation divs to a placeholder
    NAV_RE = re.compile(
        r'<div[^>]*data-tag="component-module-navigation"[^>]*>.*?</div>',
        re.S)
    body = NAV_RE.sub(
        '<div data-tag="component-module-navigation" '
        'style="display:flex;flex-wrap:wrap;gap:0;justify-content:center">'
        'Navigation</div>', body)

    def _norm_style(m: re.Match) -> str:
        val = m.group(1)
        val = re.sub(r'\s*:\s*', ':', val)
        val = re.sub(r'\s*;\s*', ';', val)
        val = val.rstrip(';')
        val = val.lower()
        return f'style="{val}"'
    body = STYLE_ATTR_RE.sub(_norm_style, body)

    body = re.sub(r'"\s*>', '">', body)
    body = re.sub(r'\s+', ' ', body)
    body = re.sub(r'>\s+<', '><', body)
    return body.strip()


# ---------------------------------------------------------------------------
# Diff engine
# ---------------------------------------------------------------------------

def _diff_text(a_label: str, b_label: str, a_text: str, b_text: str) -> str:
    if a_text == b_text:
        return ''
    lines: list[str] = []
    diff = difflib.unified_diff(
        a_text.splitlines(keepends=True),
        b_text.splitlines(keepends=True),
        fromfile=f'[{a_label}]', tofile=f'[{b_label}]',
    )
    for line in diff:
        lines.append(line.rstrip('\n'))
    return '\n'.join(lines)


def diff_cc(local_path: Path, live_path: Path, *, verbose: bool = False) -> str:
    local_tmp = _extract_zip(local_path)
    live_tmp = _extract_zip(live_path)

    local_manifest = _parse_manifest(local_tmp)
    live_manifest = _parse_manifest(live_tmp)

    local_pages = _read_wiki_pages(local_tmp)
    live_pages = _read_wiki_pages(live_tmp)

    local_assess = {a['title']: a for a in _read_assessments(local_tmp)}
    live_assess = {a['title']: a for a in _read_assessments(live_tmp)}

    local_assets = _read_assets(local_tmp)
    live_assets = _read_assets(live_tmp)

    lines: list[str] = []
    sepline = '─' * 79

    # Header
    local_title = local_manifest.get('title', local_path.name)
    live_title = live_manifest.get('title', live_path.name)
    lines.append(f'{sepline}')
    lines.append(f'LOCAL:  {local_title}')
    lines.append(f'LIVE:   {live_title}')
    lines.append(f'{sepline}')
    lines.append('')

    # =================================================================
    # Gather
    # =================================================================

    # -- WikiPages --
    wiki_added = sorted(set(local_pages) - set(live_pages))
    wiki_removed = sorted(set(live_pages) - set(local_pages))
    wiki_modified: list[str] = []
    for fn in sorted(set(local_pages) & set(live_pages)):
        if _diff_text(fn, fn, local_pages[fn], live_pages[fn]):
            wiki_modified.append(fn)

    # -- Assessments --
    assess_only_local: list[str] = []
    assess_only_live: list[str] = []
    assess_changed: list[tuple[str, str]] = []
    for title in sorted(set(local_assess) | set(live_assess)):
        la = local_assess.get(title)
        li = live_assess.get(title)
        if la and not li:
            assess_only_local.append(title)
        elif li and not la:
            assess_only_live.append(title)
        elif la['points'] != li['points']:
            assess_changed.append(
                (title, f'points {li["points"]} → {la["points"]}'))

    # -- Assets --
    lkeys = set(local_assets)
    rkeys = set(live_assets)
    asset_only_local: list[tuple[str, int]] = []
    for k in sorted(lkeys - rkeys):
        n, _, s = local_assets[k]
        asset_only_local.append((n, s))
    asset_only_live: list[tuple[str, int]] = []
    for k in sorted(rkeys - lkeys):
        n, _, s = live_assets[k]
        asset_only_live.append((n, s))

    checksum_changed: list[str] = []
    rebuilt_same: list[str] = []
    for k in sorted(lkeys & rkeys):
        ln, ls, lz = local_assets[k]
        rn, rs, rz = live_assets[k]
        if ls != rs:
            checksum_changed.append(
                f'* {ln}  ({_fmt_size(rz)} → {_fmt_size(lz)})')
        elif _is_assessment_pdf(ln) and ln != rn:
            rebuilt_same.append(f'{rn} → {ln}  (rebuilt, same content)')

    # -- Live-only Canvas artifacts --
    extra_dirs: list[str] = []
    for name in ['lti_resource_links', 'non_cc_assessments']:
        if (live_tmp / name).exists():
            cnt = len(list((live_tmp / name).iterdir()))
            extra_dirs.append(f'{name} ({cnt} items)')
    ci = live_tmp / 'web_resources' / 'course_image'
    if ci.exists() and not (local_tmp / 'web_resources' / 'course_image').exists():
        extra_dirs.append('course_image')

    # =================================================================
    # CHANGES
    # =================================================================
    cl: list[str] = []
    for fn in wiki_modified:
        cl.append(f'* {fn}  (content differs)')
    for title, detail in assess_changed:
        cl.append(f'* {title}  ({detail})')
    cl.extend(checksum_changed)

    # =================================================================
    # LIVE-ONLY
    # =================================================================
    ll: list[str] = []
    for fn in wiki_removed:
        ll.append(f'− (wikipage) {fn}')
    for title in assess_only_live:
        ll.append(f'− (assessment) {title}')
    for name, size in asset_only_live:
        ll.append(f'− (asset) {name}  ({_fmt_size(size)})')
    for d in extra_dirs:
        ll.append(f'• {d}')

    # =================================================================
    # REBUILT, SAME CONTENT
    # =================================================================
    rl = list(rebuilt_same)

    # =================================================================
    # Output
    # =================================================================
    def _section(heading: str, items: list[str]) -> None:
        if not items:
            return
        lines.append(heading)
        lines.append('')
        for item in items:
            lines.append(item)
        lines.append('')

    _section('CHANGES', cl)
    _section('LIVE-ONLY', ll)
    _section('REBUILT, SAME CONTENT', rl)

    if not cl and not ll and not rl:
        lines.append('NO DIFFERENCES')
        lines.append('')

    # --- Cleanup ---
    import shutil
    shutil.rmtree(local_tmp, ignore_errors=True)
    shutil.rmtree(live_tmp, ignore_errors=True)

    return '\n'.join(lines)


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f'{size} B'
    elif size < 1024 * 1024:
        return f'{size / 1024:.1f} KB'
    return f'{size / (1024 * 1024):.1f} MB'
