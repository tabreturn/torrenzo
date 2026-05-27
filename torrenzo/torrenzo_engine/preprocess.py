"""preprocess -- shared Markdown text transformations applied before rendering."""

import re
from pathlib import Path

_WIKI_LINK_RE = re.compile(r'\[\[([^\]]+?)(?:\|([^\]]+?))?\]\]')
_FILE_ISH_RE = re.compile(r'(mod_\d+_\d+_\w+|assessment_\d+|\.\w+$|/)')
_MOD_RE = re.compile(r'\bmod_(\d+)_(\d+)_(\w+)$')


def _display_name(target: str) -> str:
    """Derive a human-readable display name from a wiki-link target."""
    m = _MOD_RE.search(target)
    if m:
        mod_num = str(int(m.group(1)))
        seq = int(m.group(2))
        name = m.group(3).replace('_', ' ').title()
        return f'Module {mod_num}.{seq}: {name}'
    am = re.match(r'^assessment_0*(\d+)$', target)
    if am:
        return f'Assessment {int(am.group(1))}'
    return target


_MD_LINK_HREF = re.compile(r'\]\(([^)]+)\.md\)')


def rewrite_md_hrefs(text: str) -> str:
    """Rewrite .md extensions to .html in Markdown link hrefs.

    Allows authors to write Obsidian-compatible .md links in source;
    the build converts them to .html so they work in the final output.
    """
    return _MD_LINK_HREF.sub(r'](\1.html)', text)


def expand_wiki_links(
    text: str,
    valid_targets: frozenset[str] | None = None,
) -> tuple[str, list[str]]:
    """Convert [[target]] and [[label|target]] to Markdown links.

    Only expands when target looks like a file path (module page name,
    assessment name, extension, or contains /) so Dataview-style
    [[outline]] tags are left alone.  Bare targets get an auto-derived
    human-readable label; pipe syntax lets authors override it.

    If *valid_targets* is provided, warns about links whose resolved
    href basename is not in the set.
    """
    warnings: list[str] = []

    def _replacer(m: re.Match[str]) -> str:
        left = m.group(1).strip()
        right = m.group(2).strip() if m.group(2) else None
        if right is not None:
            left_is_file = bool(_FILE_ISH_RE.search(left))
            right_is_file = bool(_FILE_ISH_RE.search(right))
            if left_is_file and not right_is_file:
                target, display = left, right
            elif right_is_file and not left_is_file:
                target, display = right, left
            else:
                target, display = left, right
        else:
            display = target = left
        if not _FILE_ISH_RE.search(target):
            return m.group(0)
        if not m.group(2):
            display = _display_name(target)
        href = target if '.' in target.split('/')[-1] else f'{target}.html'
        if valid_targets is not None:
            basename = href.rsplit('/', 1)[-1]
            if basename not in valid_targets:
                warnings.append(f'Unresolved link: [[{left}]] -> {href}')
        return f'[{display}]({href})'
    return _WIKI_LINK_RE.sub(_replacer, text), warnings


def collect_valid_outputs(subject_root: Path) -> frozenset[str]:
    """Return the set of .html basenames that will exist in the build output.

    Scans modules/* for mod_*.md files and assessments/* for
    ass_*_brief.md files so wiki-link targets can be validated.
    """
    names: set[str] = set()
    modules_dir = subject_root / 'modules'
    if modules_dir.exists():
        for f in sorted(modules_dir.rglob('mod_*.md')):
            names.add(f.with_suffix('.html').name)
    assess_dir = subject_root / 'assessments'
    if assess_dir.exists():
        for f in sorted(assess_dir.rglob('ass_*_brief.md')):
            names.add(f.parent.name + '.html')
    return frozenset(names)


def convert_dashes(text: str) -> str:
    """Convert -- to en-dash and --- to em-dash in Markdown text.

    Preserves dashes inside fenced code blocks, inline code spans,
    HTML comments, and horizontal-rule lines.
    """
    lines = text.split('\n')
    result: list[str] = []
    in_fence = False
    fence_char = ''
    fence_len = 0

    for line in lines:
        if in_fence:
            stripped = line.strip()
            if (stripped
                    and all(c == fence_char for c in stripped)
                    and len(stripped) >= fence_len):
                in_fence = False
            result.append(line)
            continue

        fence_match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if fence_match:
            fence_char = fence_match.group(1)[0]
            fence_len = len(fence_match.group(1))
            in_fence = True
            result.append(line)
            continue

        if re.match(r'^\s{0,3}-{3,}\s*$', line):
            result.append(line)
            continue

        if re.match(r'^\s*\|[\s:]*-{2,}[\s:]*(\|[\s:]*-{2,}[\s:]*)+\|?\s*$', line):
            result.append(line)
            continue

        result.append(_convert_line_dashes(line))

    return '\n'.join(result)


def _convert_line_dashes(line: str) -> str:
    placeholders: list[str] = []

    def _save(m: re.Match[str]) -> str:
        placeholders.append(m.group(0))
        return f'\x00PH{len(placeholders) - 1}\x00'

    protected = re.sub(r'(`+)(.+?)\1', _save, line)
    protected = re.sub(r'<!--.*?-->', _save, protected)
    protected = re.sub(r'<!--|-->', _save, protected)

    protected = protected.replace('---', '\u2014')
    protected = protected.replace('--', '\u2013')

    for i, original in enumerate(placeholders):
        protected = protected.replace(f'\x00PH{i}\x00', original)

    return protected


_UNICODE_TO_ENTITY = {
    '\u2013': '&ndash;',
    '\u2014': '&mdash;',
    '\u00d7': '&times;',
    '\u2018': '&lsquo;',
    '\u2019': '&rsquo;',
    '\u201c': '&ldquo;',
    '\u201d': '&rdquo;',
    '\u2026': '&hellip;',
    '\u00a9': '&copy;',
    '\u00ae': '&reg;',
    '\u2122': '&trade;',
    '\u00b0': '&deg;',
    '\u00b1': '&plusmn;',
    '\u2264': '&le;',
    '\u2265': '&ge;',
    '\u00bd': '&frac12;',
    '\u2153': '&#8531;',
    '\u00bc': '&frac14;',
    '\u00be': '&frac34;',
    '\u2190': '&larr;',
    '\u2192': '&rarr;',
    '\u2191': '&uarr;',
    '\u2193': '&darr;',
    '\u00b7': '&middot;',
    '\u2022': '&bull;',
}


def unicode_to_entities(html: str) -> str:
    """Replace Unicode symbols with HTML entities for encoding safety."""
    for char, entity in _UNICODE_TO_ENTITY.items():
        html = html.replace(char, entity)
    return html
