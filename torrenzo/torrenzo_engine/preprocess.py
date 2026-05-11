"""preprocess -- shared Markdown text transformations applied before rendering."""

import re


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
