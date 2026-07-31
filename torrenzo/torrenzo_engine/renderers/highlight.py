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
      with inline colour spans.
    * Everything else → standard ``<pre><code>…</code></pre>``.
    """
    token = tokens[idx]
    info = token.info.strip() if token.info else ''
    lang = info.split(maxsplit=1)[0] if info else ''

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

            return (
              f'<div class="pre"><code class="language-{_html.escape(lang)}" '
              f'style="white-space:pre">'
              f'{highlighted}</code></div>\n'
            )

    escaped = _html.escape(token.content)
    return f'<pre><code>{escaped}</code></pre>\n'


def install(md) -> None:
    """Patch *md* to use Pygments highlighting with ``<div class="pre">``."""
    md.add_render_rule('fence', _fence_renderer)
