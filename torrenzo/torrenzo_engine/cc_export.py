"""cc_export -- package build/ artifacts into an IMS Common Cartridge (.imscc).

Walks the build directory for actual artifacts, combines with the outline
structure, generates imsmanifest.xml, rewrites HTML asset paths, and zips
everything into a .imscc file.  Rebuilt from scratch every run.

Canvas-specific extensions (assignment_settings.xml, rubrics.xml,
assignment_groups.xml) are included so that Canvas imports recreate
assignments with correct marks, weighting, and rubrics.

References:
  https://www.imsglobal.org/cc/ccv1p1/imscc_profilev1p1-Implementation.html
  https://github.com/instructure/canvas-lms  (CC import/export)
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
CANVAS_NS = 'http://canvas.instructure.com/xsd/cccv1p0'
CANVAS_XSD = 'https://canvas.instructure.com/xsd/cccv1p0.xsd'

LOR_TYPE = 'associatedcontent/imscc_xmlv1p1/learning-application-resource'

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
ITALIC_WEIGHT_RE = re.compile(r'^(.+?)\s*\*(\d+)\s*%\*\s*$')
ITALIC_RANGE_RE = re.compile(r'^(.+?)\s*\*(\d+)\s*[-–]+\s*(\d+)\s*%\*\s*$')


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


# ---------------------------------------------------------------------------
# Rubric parsing from brief markdown
# ---------------------------------------------------------------------------

def _parse_rubric(brief_path: Path, total_marks: float) -> dict | None:
    """Extract rubric from the last markdown table in a brief .md file."""
    text = brief_path.read_text(encoding='utf-8')
    lines = text.splitlines()

    tables: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            current.append(stripped)
        else:
            if current:
                tables.append(current)
                current = []
    if current:
        tables.append(current)

    if not tables:
        return None

    rubric_lines = tables[-1]
    if len(rubric_lines) < 3:
        return None

    def _split_row(row: str) -> list[str]:
        parts = row.split('|')
        return [p.strip() for p in parts if p.strip() != '']

    header_cells = _split_row(rubric_lines[0])
    if len(header_cells) < 2:
        return None
    rating_headers = header_cells[1:]

    ratings_scale: list[dict] = []
    for i, header in enumerate(rating_headers):
        m = ITALIC_RANGE_RE.match(header)
        if m:
            name = m.group(1).strip()
            high = int(m.group(3))
        else:
            name = re.sub(r'\*([^*]+)\*', r'\1', header).strip()
            high = int(100 * (i + 1) / len(rating_headers))
        ratings_scale.append({'name': name, 'high_pct': high})

    criteria: list[dict] = []
    for row_line in rubric_lines[2:]:
        cells = _split_row(row_line)
        if len(cells) < 2:
            continue

        first = cells[0]
        cw = ITALIC_WEIGHT_RE.match(first)
        if cw:
            crit_name = cw.group(1).strip()
            weight_pct = int(cw.group(2))
        else:
            crit_name = re.sub(r'\*([^*]+)\*', r'\1', first).strip()
            weight_pct = round(100 / max(len(rubric_lines) - 2, 1))

        crit_points = round(total_marks * weight_pct / 100, 2)

        crit_ratings: list[dict] = []
        descs = cells[1:len(rating_headers) + 1]
        for j, (scale, desc) in enumerate(zip(ratings_scale, descs)):
            pts = round(crit_points * scale['high_pct'] / 100, 2)
            crit_ratings.append({
                'description': scale['name'],
                'long_description': desc,
                'points': pts,
            })

        criteria.append({
            'description': crit_name,
            'points': crit_points,
            'ratings': crit_ratings,
        })

    if not criteria:
        return None
    return {'criteria': criteria, 'points_possible': total_marks}


def _find_brief_md(subject_root: Path, ass_num: int) -> Path | None:
    """Locate the brief .md source for an assessment number."""
    pattern = f'assessments/assessment_{ass_num:02d}/ass_{ass_num:02d}_brief.md'
    p = subject_root / pattern
    if p.exists():
        return p
    for candidate in subject_root.glob(
        f'assessments/assessment_{ass_num}*/ass_*_brief.md'
    ):
        return candidate
    return None


# ---------------------------------------------------------------------------
# Canvas-specific XML generators
# ---------------------------------------------------------------------------

def _assignment_settings_xml(
    identifier: str,
    title: str,
    points: float,
    group_id: str,
    rubric_id: str | None,
    submission: str,
) -> str:
    root = ET.Element('assignment')
    root.set('identifier', identifier)
    root.set('xmlns', CANVAS_NS)
    root.set('xmlns:xsi', XSI_NS)
    root.set('xsi:schemaLocation', f'{CANVAS_NS} {CANVAS_XSD}')
    _el(root, 'title', title)
    _el(root, 'points_possible', str(points))
    _el(root, 'grading_type', 'points')
    _el(root, 'submission_types', 'online_upload')
    _el(root, 'workflow_state', 'published')
    _el(root, 'assignment_group_identifierref', group_id)
    if rubric_id:
        _el(root, 'rubric_identifierref', rubric_id)
    if submission:
        _el(root, 'description', submission)
    ET.indent(root)
    xml = ET.tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + '\n'


def _rubrics_xml(assessments: list[dict]) -> str:
    root = ET.Element('rubrics')
    root.set('xmlns', CANVAS_NS)
    for ass in assessments:
        rubric_data = ass.get('rubric')
        if not rubric_data:
            continue
        rubric = _el(root, 'rubric', identifier=ass['rubric_id'])
        _el(rubric, 'title', f'{ass["title"]} Rubric')
        _el(rubric, 'points_possible',
            str(rubric_data['points_possible']))
        _el(rubric, 'read_only', 'false')
        _el(rubric, 'reusable', 'false')
        _el(rubric, 'free_form_criterion_comments', 'false')

        for ci, crit_data in enumerate(rubric_data['criteria']):
            crit = _el(rubric, 'criterion')
            crit_id = f'{ass["rubric_id"]}_c{ci}'
            _el(crit, 'criterion_id', crit_id)
            _el(crit, 'description', crit_data['description'])
            _el(crit, 'points', str(crit_data['points']))

            for ri, rat_data in enumerate(crit_data['ratings']):
                rat = _el(crit, 'rating')
                _el(rat, 'description', rat_data['description'])
                _el(rat, 'long_description', rat_data['long_description'])
                _el(rat, 'points', str(rat_data['points']))
                _el(rat, 'id', f'{crit_id}_r{ri}')
                _el(rat, 'criterion_id', crit_id)

    ET.indent(root)
    xml = ET.tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + '\n'


def _module_meta_xml(
    module_pages: dict[int, list[dict]],
    assessment_items: list[dict],
    lecturer_notes: list[dict] | None = None,
) -> str:
    root = ET.Element('modules')
    root.set('xmlns', CANVAS_NS)
    root.set('xmlns:xsi', XSI_NS)
    root.set('xsi:schemaLocation', f'{CANVAS_NS} {CANVAS_XSD}')

    position = 0
    for mod_num in sorted(module_pages):
        pages = sorted(module_pages[mod_num], key=lambda p: p['seq'])
        mod_label = 'Welcome' if mod_num == 0 else f'Module {mod_num}'
        position += 1
        mod = _el(root, 'module', identifier=_id(f'module/{mod_num}'))
        _el(mod, 'title', mod_label)
        _el(mod, 'workflow_state', 'active')
        _el(mod, 'position', str(position))
        _el(mod, 'require_sequential_progress', 'false')
        _el(mod, 'locked', 'false')
        items = _el(mod, 'items')

        for pi, page in enumerate(pages):
            item = _el(items, 'item',
                       identifier=_id(f'item/{page["filename"]}'))
            _el(item, 'content_type', 'WikiPage')
            _el(item, 'workflow_state', 'active')
            if mod_num == 0:
                _el(item, 'title', page['title'])
            else:
                _el(item, 'title', f'Module {mod_num}: {page["title"]}')
            _el(item, 'identifierref', page['resource_id'])
            _el(item, 'position', str(pi + 1))
            _el(item, 'new_tab', 'false')
            _el(item, 'indent', '0')

    if assessment_items:
        position += 1
        mod = _el(root, 'module', identifier=_id('section/assessments'))
        _el(mod, 'title', 'Assessments')
        _el(mod, 'workflow_state', 'active')
        _el(mod, 'position', str(position))
        _el(mod, 'require_sequential_progress', 'false')
        _el(mod, 'locked', 'false')
        items = _el(mod, 'items')

        for pi, ass in enumerate(assessment_items):
            item = _el(items, 'item',
                       identifier=_id(f'item/sub/{ass["pdf_filename"]}'))
            _el(item, 'content_type', 'Assignment')
            _el(item, 'workflow_state', 'active')
            _el(item, 'title', ass['title'])
            _el(item, 'identifierref', ass['assignment_id'])
            _el(item, 'position', str(pi + 1))
            _el(item, 'new_tab', 'false')
            _el(item, 'indent', '0')

    if lecturer_notes:
        position += 1
        mod = _el(root, 'module', identifier=_id('section/lecturer_notes'))
        _el(mod, 'title', 'Lecturer Notes')
        _el(mod, 'workflow_state', 'unpublished')
        _el(mod, 'position', str(position))
        _el(mod, 'require_sequential_progress', 'false')
        _el(mod, 'locked', 'false')
        items = _el(mod, 'items')

        for pi, note in enumerate(lecturer_notes):
            item = _el(items, 'item',
                       identifier=_id(f'item/lecturer/{note["filename"]}'))
            _el(item, 'content_type', 'Attachment')
            _el(item, 'workflow_state', 'unpublished')
            _el(item, 'title', note['filename'])
            _el(item, 'identifierref', note['resource_id'])
            _el(item, 'position', str(pi + 1))
            _el(item, 'new_tab', 'false')
            _el(item, 'indent', '0')

    ET.indent(root)
    xml = ET.tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + '\n'


def _assignment_groups_xml(assessments: list[dict]) -> str:
    root = ET.Element('assignmentGroups')
    root.set('xmlns', CANVAS_NS)
    for i, ass in enumerate(assessments):
        grp = _el(root, 'assignmentGroup', identifier=ass['group_id'])
        _el(grp, 'title', ass['title'])
        _el(grp, 'position', str(i + 1))
        weight = ass.get('weight', 0)
        _el(grp, 'group_weight', str(weight))
    ET.indent(root)
    xml = ET.tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + '\n'


def _course_settings_xml(subject_code: str, subject_title: str) -> str:
    root = ET.Element('course', identifier=_id('course'))
    root.set('xmlns', CANVAS_NS)
    root.set('xmlns:xsi', XSI_NS)
    root.set('xsi:schemaLocation', f'{CANVAS_NS} {CANVAS_XSD}')
    _el(root, 'title', subject_title)
    _el(root, 'course_code', subject_code)
    _el(root, 'default_view', 'wiki')
    _el(root, 'default_wiki_editing_roles', 'teachers')
    _el(root, 'allow_student_wiki_edits', 'false')
    _el(root, 'license', 'private')
    ET.indent(root)
    xml = ET.tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + '\n'


def _parse_brief_sections(brief_path: Path) -> dict[str, str]:
    """Extract Submission Instructions and Academic Integrity Declaration
    sections from the brief markdown."""
    text = brief_path.read_text(encoding='utf-8')
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []
    targets = {'## Submission Instructions', '## Academic Integrity Declaration'}
    stop_markers = {'## ', '---', '<div class="page-break">'}

    for line in text.splitlines():
        stripped = line.strip()
        if stripped in targets:
            if current_section:
                sections[current_section] = '\n'.join(current_lines).strip()
            current_section = stripped.removeprefix('## ')
            current_lines = []
        elif current_section:
            if any(stripped.startswith(m) for m in stop_markers):
                sections[current_section] = '\n'.join(current_lines).strip()
                current_section = None
            else:
                current_lines.append(line)
    if current_section:
        sections[current_section] = '\n'.join(current_lines).strip()
    return sections


def _assignment_description_html(ass: dict, brief_md: Path | None) -> str:
    """Build an HTML description page for a Canvas assignment."""
    body = (
        f'<p>\n'
        f'<a class="instructure_file_link instructure_scribd_file auto_open" '
        f'href="$IMS-CC-FILEBASE$/{ass["pdf_filename"]}" '
        f'data-canvas-previewable="true">'
        f'Assessment Brief (PDF)'
        f'</a>\n'
        f'</p>\n'
    )

    if brief_md and brief_md.exists():
        sections = _parse_brief_sections(brief_md)
        submission = sections.get('Submission Instructions', '')
        integrity = sections.get('Academic Integrity Declaration', '')
        if submission:
            body += (
                f'<h4>Submission Instructions</h4>\n'
                f'<p>{submission}</p>\n'
            )
        if integrity:
            body += (
                f'<h4>Academic Integrity Declaration</h4>\n'
                f'<p>{integrity}</p>\n'
            )

    return _wrap_wiki_html(body, ass['title'], ass['assignment_id'])


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------

def _build_manifest(
    subject_code: str,
    subject_title: str,
    module_pages: dict[int, list[dict]],
    assessment_items: list[dict],
    assets: list[dict],
    lecturer_notes: list[dict] | None = None,
    has_course_settings: bool = False,
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
                     identifier=_id(f'item/sub/{ass["pdf_filename"]}'),
                     identifierref=ass['assignment_id'])
            _el(ai, f'{{{ns}}}title', ass['title'])

    if lecturer_notes:
        sec = _el(root_item, f'{{{ns}}}item',
                  identifier=_id('section/lecturer_notes'))
        _el(sec, f'{{{ns}}}title', 'Lecturer Notes')
        for note in lecturer_notes:
            ni = _el(sec, f'{{{ns}}}item',
                     identifier=_id(f'item/lecturer/{note["filename"]}'),
                     identifierref=note['resource_id'])
            _el(ni, f'{{{ns}}}title', note['filename'])

    # -- resources --
    resources = _el(manifest, f'{{{ns}}}resources')

    if has_course_settings:
        cs_res = _el(resources, f'{{{ns}}}resource',
                     identifier=_id('course_settings'),
                     type=LOR_TYPE,
                     href='course_settings/canvas_export.txt')
        _el(cs_res, f'{{{ns}}}file',
            href='course_settings/canvas_export.txt')
        _el(cs_res, f'{{{ns}}}file',
            href='course_settings/assignment_groups.xml')
        _el(cs_res, f'{{{ns}}}file',
            href='course_settings/rubrics.xml')
        _el(cs_res, f'{{{ns}}}file',
            href='course_settings/module_meta.xml')
        _el(cs_res, f'{{{ns}}}file',
            href='course_settings/course_settings.xml')

    for mod_num in sorted(module_pages):
        for page in module_pages[mod_num]:
            cc_href = f'wiki_content/{page["filename"]}'
            res = _el(resources, f'{{{ns}}}resource',
                      identifier=page['resource_id'],
                      type='webcontent', href=cc_href)
            _el(res, f'{{{ns}}}file', href=cc_href)

    for ass in assessment_items:
        cc_href = f'web_resources/{ass["pdf_filename"]}'
        res = _el(resources, f'{{{ns}}}resource',
                  identifier=ass['pdf_resource_id'],
                  type='webcontent', href=cc_href)
        _el(res, f'{{{ns}}}file', href=cc_href)

        ass_dir = ass['assignment_id']
        html_href = f'{ass_dir}/{ass_dir}.html'
        settings_href = f'{ass_dir}/assignment_settings.xml'
        res2 = _el(resources, f'{{{ns}}}resource',
                   identifier=ass['assignment_id'],
                   type=LOR_TYPE, href=html_href)
        _el(res2, f'{{{ns}}}file', href=html_href)
        _el(res2, f'{{{ns}}}file', href=settings_href)

    for asset in assets:
        cc_href = f'web_resources/assets/{asset["filename"]}'
        res = _el(resources, f'{{{ns}}}resource',
                  identifier=asset['resource_id'],
                  type='webcontent', href=cc_href)
        _el(res, f'{{{ns}}}file', href=cc_href)

    if lecturer_notes:
        for note in lecturer_notes:
            cc_href = f'web_resources/lecturer_notes/{note["filename"]}'
            res = _el(resources, f'{{{ns}}}resource',
                      identifier=note['resource_id'],
                      type='webcontent', href=cc_href)
            _el(res, f'{{{ns}}}file', href=cc_href)

    ET.indent(manifest)
    xml_str = ET.tostring(manifest, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + '\n'


# ---------------------------------------------------------------------------
# Main export entry point
# ---------------------------------------------------------------------------

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
    diagnostics: list[str] = []

    if assessments_dir.exists():
        for f in sorted(assessments_dir.iterdir()):
            m = ASSESS_PDF_RE.match(f.name)
            if not m:
                continue
            ass_num = int(m.group(1))
            ass_key = f'a{ass_num}'
            info = (assess_data.get(ass_key, {})
                    if isinstance(assess_data, dict) else {})
            if not isinstance(info, dict):
                info = {}
            name = info.get('assessment', f'Assessment {ass_num}')
            total_marks = float(info.get('total_marks', 0) or 0)
            weight_raw = str(info.get('weighting', '0'))
            weight = float(re.sub(r'[^0-9.]', '', weight_raw) or 0)
            submission = str(info.get('submission', ''))

            assignment_id = _id(f'assignment/{ass_key}')
            pdf_resource_id = _id(f'resource/{f.name}')
            rubric_id = _id(f'rubric/{ass_key}')
            group_id = _id(f'group/{ass_key}')

            brief_md = _find_brief_md(subject_root, ass_num)
            rubric = None
            if brief_md and total_marks > 0:
                rubric = _parse_rubric(brief_md, total_marks)
                if rubric:
                    diagnostics.append(
                        f'Rubric parsed from {brief_md.name}: '
                        f'{len(rubric["criteria"])} criteria'
                    )

            assessment_items.append({
                'pdf_filename': f.name,
                'pdf_path': f,
                'num': ass_num,
                'title': f'Assessment {ass_num} \u2013 {name}',
                'pdf_resource_id': pdf_resource_id,
                'assignment_id': assignment_id,
                'rubric_id': rubric_id if rubric else None,
                'group_id': group_id,
                'weight': weight,
                'total_marks': total_marks,
                'submission': submission,
                'rubric': rubric,
                'brief_md': brief_md,
                'outline_info': info,
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

    lecturer_notes: list[dict] = []
    lecturer_notes_dir = build_dir / 'lecturer_notes'
    if lecturer_notes_dir.exists():
        for f in sorted(lecturer_notes_dir.rglob('*')):
            if f.is_file():
                resource_id = _id(f'resource/lecturer_notes/{f.name}')
                lecturer_notes.append({
                    'filename': f.name,
                    'path': f,
                    'resource_id': resource_id,
                })

    has_course_settings = bool(assessment_items) or bool(module_pages)

    manifest_xml = _build_manifest(
        subject_code, subject_title,
        module_pages, assessment_items, assets,
        lecturer_notes=lecturer_notes,
        has_course_settings=has_course_settings,
    )

    output_path = build_dir / f'{subject_code}.imscc'

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
            zf.write(ass['pdf_path'],
                     f'web_resources/{ass["pdf_filename"]}')

            aid = ass['assignment_id']
            desc_html = _assignment_description_html(ass, ass.get('brief_md'))
            zf.writestr(f'{aid}/{aid}.html', desc_html)

            settings = _assignment_settings_xml(
                identifier=aid,
                title=ass['title'],
                points=ass['total_marks'],
                group_id=ass['group_id'],
                rubric_id=ass.get('rubric_id'),
                submission=ass['submission'],
            )
            zf.writestr(f'{aid}/assignment_settings.xml', settings)

        if has_course_settings:
            zf.writestr('course_settings/canvas_export.txt',
                        'Common Cartridge generated by torrenzo\n')
            zf.writestr('course_settings/assignment_groups.xml',
                        _assignment_groups_xml(assessment_items))
            zf.writestr('course_settings/rubrics.xml',
                        _rubrics_xml(assessment_items))
            zf.writestr('course_settings/module_meta.xml',
                        _module_meta_xml(module_pages, assessment_items,
                                         lecturer_notes=lecturer_notes))
            zf.writestr('course_settings/course_settings.xml',
                        _course_settings_xml(subject_code, subject_title))

        for asset in assets:
            zf.write(asset['path'],
                     f'web_resources/assets/{asset["filename"]}')

        for note in lecturer_notes:
            zf.write(note['path'],
                     f'web_resources/lecturer_notes/{note["filename"]}')

    page_count = sum(len(v) for v in module_pages.values())
    diagnostics.insert(0,
        f'Common Cartridge -> {output_path.name} '
        f'({page_count} pages, {len(assessment_items)} assessments, '
        f'{len(assets)} assets)'
    )
    return output_path, diagnostics
