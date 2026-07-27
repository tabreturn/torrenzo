from __future__ import annotations

"""torrenzo.components -- reusable HTML components injected via tags."""

import html as html_mod
import re
from pathlib import Path
from typing import Callable


VIDEO_EXTS: tuple[str, ...] = (
  '.mp4', '.webm', '.ogg', '.ogv', '.mov', '.m4v', '.mkv',
)


def _titlecase_slug_part(word: str) -> str:
    """Title-case one slug word; preserve hyphens and existing uppercase."""
    segments: list[str] = []
    for seg in word.split('-'):
        if not seg:
            segments.append('')
            continue
        cased_chars: list[str] = []
        seen_alpha = False
        for ch in seg:
            if ch.isupper():
                cased_chars.append(ch)
            elif ch.islower():
                cased_chars.append(ch.upper() if not seen_alpha else ch)
                seen_alpha = True
                continue
            else:
                cased_chars.append(ch)
            seen_alpha = seen_alpha or ch.isalpha()
        segments.append(''.join(cased_chars))
    return '-'.join(segments)


def _titlecase_slug(slug: str) -> str:
    """Title-case a full module-name slug (underscores -> spaces)."""
    return ' '.join(_titlecase_slug_part(w) for w in slug.split('_'))


def _parse_module_filename(filepath: Path) -> tuple[int, str] | None:
    """Parse `mod_<n>_<seq>_<name>.<ext>` -> (seq_int, display_name)."""
    stem = filepath.stem
    parts = stem.split('_')
    if len(parts) < 3 or parts[0] != 'mod':
        return None
    try:
        seq = int(parts[2])
    except (ValueError, IndexError):
        return None
    name = _titlecase_slug('_'.join(parts[3:]))
    if not name:
        name = parts[2]
    return seq, name


_MODULE_DIR_RE = re.compile(r'^module_(\d+)(?:_(.*))?$')


def parse_module_path(filepath: Path) -> dict[str, str] | None:
    """Resolve the ``[[module|...]]`` value tags for a module file, or None.

    ``n``/``.n``/``n.n`` come from the parent dir + file seq; ``name`` from
    the dir slug; ``sub-name`` from the file slug. All title-cased via
    ``_titlecase_slug``.
    """
    parent = filepath.parent
    m = _MODULE_DIR_RE.match(parent.name)
    if not m:
        return None
    module_num = str(int(m.group(1)))
    name_slug = (m.group(2) or '').strip()
    if not name_slug:
        return None
    stem = filepath.stem
    parts = stem.split('_')
    if len(parts) < 4 or parts[0] != 'mod':
        return None
    try:
        sub_num = str(int(parts[2]))
    except (ValueError, IndexError):
        return None
    name = _titlecase_slug(name_slug)
    sub_name = _titlecase_slug('_'.join(parts[3:]))
    return {
      'n': module_num,
      '.n': sub_num,
      'n.n': f'{module_num}.{sub_num}',
      'name': name,
      'sub-name': sub_name,
    }


def render_module_navigation(input_path: Path) -> str:
    """Build tabbed navigation links to sibling module files."""
    module_dir = input_path.parent
    siblings: list[tuple[int, str, str]] = []  # (seq, name, filename)
    for f in sorted(module_dir.glob('mod_*')):
        if f.suffix not in ('.md', '.docx'):
            continue
        parsed = _parse_module_filename(f)
        if parsed is None:
            continue
        seq, name = parsed
        siblings.append((seq, name, f.name))
    siblings.sort(key=lambda x: x[0])

    if not siblings:
        return ''

    links: list[str] = []
    for seq, name, filename in siblings:
        cls = ' class="selected"' if filename == input_path.name else ''
        href = Path(filename).with_suffix('.html').name
        links.append(f'<a href="{href}"{cls}>{name}</a>')

    return (
      '<div data-tag="component-module-navigation">\n'
      + '\n'.join(links)
      + '\n</div>'
    )


def render_page_spacer() -> str:
    return '<p>&nbsp;</p>'


def render_page_break() -> str:
    return '<div data-tag="component-page-break" style="page-break-after: always; break-after: page;"></div>'


def render_under_construction(message: str = '') -> str:
    text = message.strip() if message.strip() else 'Under construction'
    safe = html_mod.escape(text)
    return (
      '<div data-tag="component-under-construction">'
      f'🚧 {safe}'
      '</div>'
    )


def render_video(file_path: str) -> str:
    safe = html_mod.escape(file_path.strip())
    basename = html_mod.escape(Path(file_path.strip()).name)
    return (
      '<div style="position: relative; width: 100%; '
      'padding-bottom: calc(56.3% + 48px); height: 0; overflow: hidden;">\n'
      '  <iframe\n'
      f'    title="Video player for {basename}"\n'
      '    data-media-type="video"\n'
      f'    src="{safe}"\n'
      '    loading="lazy"\n'
      '    allowfullscreen="allowfullscreen"\n'
      '    allow="fullscreen"\n'
      '    style="position: absolute; top: 0; left: 0; '
      'width: 100%; height: 100%; border: 0;"\n'
      '  ></iframe>\n'
      '</div>'
    )


PARAMETERIZED_COMPONENTS: dict[str, Callable[[str], str]] = {
  'under-construction': render_under_construction,
  'video': render_video,
}


def build_component_tags(input_path: Path) -> dict[str, str]:
    tags: dict[str, str] = {}
    nav = render_module_navigation(input_path)
    if nav:
        tags['outline.component.module-navigation'] = nav
    spacer = render_page_spacer()
    tags['outline.component.page-spacer'] = spacer
    tags['outline.component.page-break'] = render_page_break()
    tags['outline.component.under-construction'] = render_under_construction()
    module_info = parse_module_path(input_path)
    if module_info:
        for key, value in module_info.items():
            if value:
                tags[f'module|{key}'] = value
    return tags
