"""torrenzo.components -- reusable HTML components injected via tags."""

from pathlib import Path


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
    name = ' '.join(w.capitalize() for w in parts[3:])
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
        links.append(f'<a href="#" data-page="{filename}"{cls}>{name}</a>')

    return (
        '<div data-tag="component-module-navigation">\n'
        + '\n'.join(links)
        + '\n</div>'
    )


def build_component_tags(input_path: Path) -> dict[str, str]:
    tags: dict[str, str] = {}
    nav = render_module_navigation(input_path)
    if nav:
        tags['outline.component.module-navigation'] = nav
    return tags
