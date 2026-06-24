from __future__ import annotations

"""torrenzo.components -- reusable HTML components injected via tags."""

import html as html_mod
from pathlib import Path
from typing import Callable


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
    name = ' '.join('-'.join(p.capitalize() for p in w.split('-')) for w in parts[3:])
    if not name:
        name = parts[2]
    return seq, name


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
    'video': render_video,
}


def build_component_tags(input_path: Path) -> dict[str, str]:
    tags: dict[str, str] = {}
    nav = render_module_navigation(input_path)
    if nav:
        tags['outline.component.module-navigation'] = nav
    spacer = render_page_spacer()
    tags['outline.component.page-spacer'] = spacer
    return tags
