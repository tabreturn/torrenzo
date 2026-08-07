"""Syntax-highlight fenced code blocks using Pygments (inline styles).

Language-tagged fenced blocks are wrapped in ``<div class="pre">`` with
Pygments inline colour.  Plain fenced blocks and indented code blocks
keep the default ``<pre><code>`` rendering.
"""

from __future__ import annotations

import html as _html
import re as _re

from markdown_it.utils import OptionsDict, EnvType
from markdown_it.token import Token

from pygments import highlight as _highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound


_FORMATTER = HtmlFormatter(noclasses=True, nowrap=True)


def _parse_info_classes(tokens: list[str]) -> list[str]:
    """Extract CSS class names from the trailing info-string tokens.

    Supports the ``markdown-it-attrs`` style ``{.class}`` group (which may
    contain several ``.cls`` entries) and bare ``.class`` tokens. Unknown
    tokens are ignored so the first token is always the language.
    """
    classes: list[str] = []
    for tok in tokens:
        if tok.startswith('{') and tok.endswith('}'):
            inner = tok[1:-1]
            classes.extend(
              p.lstrip('.') for p in inner.split() if p.startswith('.')
            )
        elif tok.startswith('.') and tok[1:]:
            classes.append(tok[1:])
    return classes


def _fence_renderer(
  self,
  tokens: list[Token],
  idx: int,
  options: OptionsDict,
  env: EnvType,
) -> str:
    """Custom ``fence`` render rule.

    * Language-tagged blocks with a recognised Pygments lexer →
      ``<div class="pre"><code class="language-…">…</code></div>``
      with inline colour spans.  Extra ``{.class}`` tokens in the info
      string are appended to the ``<div>``; a ``.wrap`` class switches
      the inline ``white-space`` to ``pre-wrap`` so long lines wrap.
    * Everything else → standard ``<pre><code>…</code></pre>``.
    """
    token = tokens[idx]
    info = token.info.strip() if token.info else ''
    info_parts = info.split()
    lang = info_parts[0] if info_parts else ''
    extra_classes = _parse_info_classes(info_parts[1:])

    if lang:
        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except ClassNotFound:
            lexer = None

        if lexer is not None:
            highlighted = _highlight(token.content, lexer, _FORMATTER)
            highlighted = highlighted.rstrip('\n')

            # canvas strips inline white-space:pre, so runs of 2+ spaces
            # are converted to &nbsp; for alignment. single spaces are left
            # as-is so copy-pasted code remains runnable
            _tag_re = _re.compile(r'<[^>]*>')
            _space_run_re = _re.compile(r'  +')

            def _nbspify_text(text: str) -> str:
                return _space_run_re.sub(
                  lambda m: '&nbsp;' * len(m.group()), text
                )

            parts: list[str] = []
            last = 0
            for m in _tag_re.finditer(highlighted):
                parts.append(_nbspify_text(highlighted[last:m.start()]))
                parts.append(m.group())
                last = m.end()
            parts.append(_nbspify_text(highlighted[last:]))
            highlighted = ''.join(parts)

            highlighted = highlighted.replace('\n', '<br>')

            wrap = 'wrap' in extra_classes
            whitespace = 'white-space:pre-wrap' if wrap else 'white-space:pre'
            div_class = 'pre'
            if extra_classes:
                div_class = f'pre {" ".join(extra_classes)}'

            return (
              f'<div class="{div_class}"><code class="language-{_html.escape(lang)}" '
              f'style="{whitespace}">'
              f'{highlighted}</code></div>\n'
            )

    escaped = _html.escape(token.content)
    return f'<pre><code>{escaped}</code></pre>\n'


def install(md) -> None:
    """Patch *md* to use Pygments highlighting with ``<div class="pre">``."""
    md.add_render_rule('fence', _fence_renderer)
