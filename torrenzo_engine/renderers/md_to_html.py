from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Dict, Tuple

TAG_RE = re.compile(r"{{\s*([\w_]+)(?:\|([\w\-]+))?\s*}}")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
STRONG_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
CODE_RE = re.compile(r"`([^`]+)`")


def inline_format(text: str, tags: Dict[str, str]) -> str:
    placeholders: Dict[str, str] = {}

    def capture_token() -> str:
        token = f"__TOKEN_{len(placeholders)}__"
        return token

    def handle_tag(match: re.Match[str]) -> str:
        key = capture_token()
        name = match.group(1)
        detail = match.group(2)
        lookup_key = name if detail is None else f"{name}|{detail}"
        snippet = tags.get(lookup_key)
        if snippet is None:
            if detail is None:
                return match.group(0)
            snippet = tags.get(name)
            if snippet is None:
                return match.group(0)
        placeholders[key] = snippet
        return key

    def handle_image(match: re.Match[str]) -> str:
        key = capture_token()
        alt = html.escape(match.group(1), quote=True)
        src = html.escape(match.group(2), quote=True)
        placeholders[key] = f'<img src="{src}" alt="{alt}">'
        return key

    text = TAG_RE.sub(handle_tag, text)
    text = IMAGE_RE.sub(handle_image, text)
    escaped = html.escape(text)
    escaped = CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = STRONG_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = ITALIC_RE.sub(r"<em>\1</em>", escaped)

    for token, snippet in placeholders.items():
        escaped = escaped.replace(token, snippet)

    return escaped


def convert_markdown_to_lms_html(content: str, tags: Dict[str, str]) -> str:
    lines = content.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_type: str | None = None
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        text = " ".join(line.strip() for line in paragraph).strip()
        paragraph = []
        if text:
            output.append(f"<p>{inline_format(text, tags)}</p>")

    def flush_list() -> None:
        nonlocal list_items, list_type
        if not list_items or list_type is None:
            list_items = []
            list_type = None
            return
        tag = "ul" if list_type == "bullet" else "ol"
        output.append(f"<{tag}>")
        for item in list_items:
            output.append(f"  <li>{inline_format(item, tags)}</li>")
        output.append(f"</{tag}>")
        list_items = []
        list_type = None

    def flush_code() -> None:
        nonlocal code_lines
        if not code_lines:
            return
        block = "\n".join(html.escape(line) for line in code_lines)
        code_lines = []
        output.append(f"<pre><code>{block}</code></pre>")

    for line in lines:
        stripped = line.rstrip("\n")

        if stripped.strip().startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                in_code = False
                flush_code()
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(stripped)
            continue

        if not stripped.strip():
            flush_paragraph()
            flush_list()
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            output.append(f"<h{level}>{inline_format(heading, tags)}</h{level}>")
            continue

        bullet_match = re.match(r"^\s*[-*]\s+(.*)$", stripped)
        if bullet_match:
            flush_paragraph()
            if list_type not in (None, "bullet"):
                flush_list()
            list_type = "bullet"
            list_items.append(bullet_match.group(1).strip())
            continue

        ordered_match = re.match(r"^\s*\d+\.\s+(.*)$", stripped)
        if ordered_match:
            flush_paragraph()
            if list_type not in (None, "ordered"):
                flush_list()
            list_type = "ordered"
            list_items.append(ordered_match.group(1).strip())
            continue

        if list_items:
            flush_list()

        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    flush_code()

    return "\n".join(output)


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    tags = context.get("tags", {})
    html_body = convert_markdown_to_lms_html(input_path.read_text(encoding="utf-8"), tags)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_body, encoding="utf-8")
    return True, f"{input_path} -> {output_path}"
