"""cc_export -- package build/ artifacts into an IMS Common Cartridge (.imscc).

Walks the build directory for actual artifacts, combines with the outline
structure, generates imsmanifest.xml, rewrites HTML asset paths, and zips
everything into a .imscc file.  Rebuilt from scratch every run.

References:
  https://www.imsglobal.org/cc/ccv1p1/imscc_profilev1p1-Implementation.html
"""

import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path
from typing import Any


CC_NS = 'http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1'
LOM_RES_NS = 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource'
LOM_MAN_NS = 'http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'

SCHEMA_LOCATION = (
    f'{CC_NS} '
    'http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_imscp_v1p2_v1p0.xsd '
    f'{LOM_RES_NS} '
    'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lomresource_v1p0.xsd '
    f'{LOM_MAN_NS} '
    'http://www.imsglobal.org/profile/cc/ccv1p1/LOM/ccv1p1_lommanifest_v1p0.xsd'
)

MOD_HTML_RE = re.compile(r'^mod_(\d+)_(\d+)_(.+)\.html$')
ASSESS_PDF_RE = re.compile(r'^assessment_(\d+)\.pdf$')
ASSET_REF_RE = re.compile(r'((?:src|href)=["\'])assets/([^"\']+)(["\'])')
PAGE_HREF_RE = re.compile(r'(href=["\'])(mod_\d+_\d+_[^"\']+\.html)(["\'])')


def _id(name: str) -> str:
    return 'g' + hashlib.md5(name.encode()).hexdigest()


def _title_from_slug(slug: str) -> str:
    return slug.replace('_', ' ').title()


def _el(parent: ET.Element, tag: str, text: str | None = None,
        **attrib: str) -> ET.Element:
    e = ET.SubElement(parent, tag, **attrib)
    if text is not None:
        e.text = text
    return e


def _wrap_wiki_html(body: str, title: str, identifier: str) -> str:
    return (
        '<html>\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>\n'
        f'<title>{title}</title>\n'
        f'<meta name="identifier" content="{identifier}"/>\n'
        '<meta name="editing_roles" content="teachers"/>\n'
        '<meta name="workflow_state" content="active"/>\n'
        '</head>\n<body>\n'
        f'{body}\n'
        '</body>\n</html>\n'
    )


def _rewrite_html(html_text: str, page_id_map: dict[str, str]) -> str:
    html_text = re.sub(r'<!-- built:.*?-->\n?', '', html_text)

    html_text = ASSET_REF_RE.sub(
        r'\1$IMS-CC-FILEBASE$/assets/\2\3', html_text,
    )

    def _replace_page_href(m: re.Match) -> str:
        filename = m.group(2)
        rid = page_id_map.get(filename)
        if rid:
            return f'{m.group(1)}$WIKI_REFERENCE$/pages/{rid}{m.group(3)}'
        return m.group(0)

    html_text = PAGE_HREF_RE.sub(_replace_page_href, html_text)
    return html_text


def _build_manifest(
    subject_code: str,
    subject_title: str,
    module_pages: dict[int, list[dict]],
    assessment_items: list[dict],
    assets: list[dict],
) -> str:
    ET.register_namespace('', CC_NS)
    ET.register_namespace('lom', LOM_RES_NS)
    ET.register_namespace('lomimscc', LOM_MAN_NS)
    ET.register_namespace('xsi', XSI_NS)

    ns = CC_NS
    lm = LOM_MAN_NS

    manifest = ET.Element(f'{{{ns}}}manifest')
    manifest.set('identifier', _id(f'manifest/{subject_code}'))
    manifest.set(f'{{{XSI_NS}}}schemaLocation', SCHEMA_LOCATION)

    # -- metadata --
    metadata = _el(manifest, f'{{{ns}}}metadata')
    _el(metadata, f'{{{ns}}}schema', 'IMS Common Cartridge')
    _el(metadata, f'{{{ns}}}schemaversion', '1.1.0')

    lom = _el(metadata, f'{{{lm}}}lom')
    general = _el(lom, f'{{{lm}}}general')
    title_wrap = _el(general, f'{{{lm}}}title')
    _el(title_wrap, f'{{{lm}}}string', f'{subject_code} {subject_title}')

    lifecycle = _el(lom, f'{{{lm}}}lifeCycle')
    contribute = _el(lifecycle, f'{{{lm}}}contribute')
    date_wrap = _el(contribute, f'{{{lm}}}date')
    _el(date_wrap, f'{{{lm}}}dateTime', str(date.today()))

    rights = _el(lom, f'{{{lm}}}rights')
    cr = _el(rights, f'{{{lm}}}copyrightAndOtherRestrictions')
    _el(cr, f'{{{lm}}}value', 'yes')
    desc = _el(rights, f'{{{lm}}}description')
    _el(desc, f'{{{lm}}}string',
        'Private (Copyrighted) - http://en.wikipedia.org/wiki/Copyright')

    # -- organizations --
    organizations = _el(manifest, f'{{{ns}}}organizations')
    org = _el(organizations, f'{{{ns}}}organization',
              identifier='org_1', structure='rooted-hierarchy')
    root_item = _el(org, f'{{{ns}}}item', identifier='LearningModules')

    for mod_num in sorted(module_pages):
        pages = sorted(module_pages[mod_num], key=lambda p: p['seq'])
        mod_label = 'Welcome' if mod_num == 0 else f'Module {mod_num}'

        mod_item = _el(root_item, f'{{{ns}}}item',
                       identifier=_id(f'module/{mod_num}'))
        _el(mod_item, f'{{{ns}}}title', mod_label)

        for page in pages:
            page_item = _el(
                mod_item, f'{{{ns}}}item',
                identifier=_id(f'item/{page["filename"]}'),
                identifierref=page['resource_id'],
            )
            if mod_num == 0:
                _el(page_item, f'{{{ns}}}title', page['title'])
            else:
                _el(page_item, f'{{{ns}}}title',
                    f'Module {mod_num}: {page["title"]}')

    if assessment_items:
        sec = _el(root_item, f'{{{ns}}}item',
                  identifier=_id('section/assessments'))
        _el(sec, f'{{{ns}}}title', 'Assessments')
        for ass in assessment_items:
            ai = _el(sec, f'{{{ns}}}item',
                     identifier=_id(f'item/{ass["filename"]}'),
                     identifierref=ass['resource_id'])
            _el(ai, f'{{{ns}}}title', ass['title'])

    # -- resources --
    resources = _el(manifest, f'{{{ns}}}resources')

    for mod_num in sorted(module_pages):
        for page in module_pages[mod_num]:
            cc_href = f'wiki_content/{page["filename"]}'
            res = _el(resources, f'{{{ns}}}resource',
                      identifier=page['resource_id'],
                      type='webcontent', href=cc_href)
            _el(res, f'{{{ns}}}file', href=cc_href)

    for ass in assessment_items:
        cc_href = f'web_resources/{ass["filename"]}'
        res = _el(resources, f'{{{ns}}}resource',
                  identifier=ass['resource_id'],
                  type='webcontent', href=cc_href)
        _el(res, f'{{{ns}}}file', href=cc_href)

    for asset in assets:
        cc_href = f'web_resources/assets/{asset["filename"]}'
        res = _el(resources, f'{{{ns}}}resource',
                  identifier=asset['resource_id'],
                  type='webcontent', href=cc_href)
        _el(res, f'{{{ns}}}file', href=cc_href)

    ET.indent(manifest)
    xml_str = ET.tostring(manifest, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + '\n'


def export_cc(
    subject_root: Path,
    build_dir: Path,
    outline: dict[str, Any],
) -> tuple[Path, list[str]]:
    subject = outline.get('subject', {})
    subject_code = str(subject.get('code', 'SUBJECT')).strip()
    subject_title = str(subject.get('title', subject_code)).strip()

    modules_dir = build_dir / 'modules_html'
    assessments_dir = build_dir / 'assessments_briefs'

    module_pages: dict[int, list[dict]] = {}
    page_id_map: dict[str, str] = {}

    if modules_dir.exists():
        for f in sorted(modules_dir.iterdir()):
            m = MOD_HTML_RE.match(f.name)
            if not m:
                continue
            mod_num = int(m.group(1))
            seq = int(m.group(2))
            slug = m.group(3)
            resource_id = _id(f'resource/{f.name}')
            page_id_map[f.name] = resource_id
            module_pages.setdefault(mod_num, []).append({
                'filename': f.name,
                'path': f,
                'seq': seq,
                'slug': slug,
                'title': _title_from_slug(slug),
                'resource_id': resource_id,
            })

    assessment_items: list[dict] = []
    assess_data = outline.get('assessment', {})
    if assessments_dir.exists():
        for f in sorted(assessments_dir.iterdir()):
            m = ASSESS_PDF_RE.match(f.name)
            if not m:
                continue
            ass_num = int(m.group(1))
            resource_id = _id(f'resource/{f.name}')
            ass_key = f'a{ass_num}'
            info = (assess_data.get(ass_key, {})
                    if isinstance(assess_data, dict) else {})
            name = (info.get('assessment', f'Assessment {ass_num}')
                    if isinstance(info, dict) else f'Assessment {ass_num}')
            assessment_items.append({
                'filename': f.name,
                'path': f,
                'num': ass_num,
                'title': f'Assessment {ass_num} \u2013 {name}',
                'resource_id': resource_id,
            })

    assets: list[dict] = []
    assets_dir = modules_dir / 'assets' if modules_dir.exists() else None
    if assets_dir and assets_dir.exists():
        for f in sorted(assets_dir.rglob('*')):
            if f.is_file():
                resource_id = _id(f'resource/assets/{f.name}')
                assets.append({
                    'filename': f.name,
                    'path': f,
                    'resource_id': resource_id,
                })

    manifest_xml = _build_manifest(
        subject_code, subject_title,
        module_pages, assessment_items, assets,
    )

    output_path = build_dir / f'{subject_code}.imscc'
    diagnostics: list[str] = []

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('imsmanifest.xml', manifest_xml)

        for mod_num in sorted(module_pages):
            for page in sorted(module_pages[mod_num], key=lambda p: p['seq']):
                body = page['path'].read_text(encoding='utf-8')
                body = _rewrite_html(body, page_id_map)
                if mod_num == 0:
                    title = page['title']
                else:
                    title = f'Module {mod_num}: {page["title"]}'
                wrapped = _wrap_wiki_html(body, title, page['resource_id'])
                zf.writestr(f'wiki_content/{page["filename"]}', wrapped)

        for ass in assessment_items:
            zf.write(ass['path'], f'web_resources/{ass["filename"]}')

        for asset in assets:
            zf.write(asset['path'], f'web_resources/assets/{asset["filename"]}')

    page_count = sum(len(v) for v in module_pages.values())
    diagnostics.append(
        f'Common Cartridge -> {output_path.name} '
        f'({page_count} pages, {len(assessment_items)} assessments, '
        f'{len(assets)} assets)'
    )
    return output_path, diagnostics
