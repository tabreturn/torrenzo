from __future__ import annotations

"""tags -- build the tag map from an outline file.

Parses `outline.md` (or `.yaml`/`.yml`) YAML front-matter and produces
a flat `dict[str, str]` mapping every supported tag key to its HTML
expansion.  This is consumed by renderers via `apply_tags`.
"""

import html
import re
from pathlib import Path
from typing import Any

import yaml


def render_learning_outcomes(outcomes: list[dict[str, str]]) -> str:
    if not outcomes:
        return ''
    entries: list[str] = [
      '<section class="subject-learning-outcomes">',
      '<h3>Subject learning outcomes</h3>',
      '<dl>',
    ]
    for outcome in outcomes:
        code = html.escape(str(outcome.get('id', '')).strip())
        description = html.escape(str(outcome.get('description', '')).strip())
        entries.append(f'<dt>{code}</dt>')
        entries.append(f'<dd>{description}</dd>')
    entries.extend(['</dl>', '</section>'])
    return '\n'.join(entries)


def render_single_learning_outcome(outcome: dict[str, str]) -> str:
    code = html.escape(str(outcome.get('id', '')).strip())
    description = html.escape(str(outcome.get('description', '')).strip())
    if not code and not description:
        return ''
    if not code:
        return f'<p>{description}</p>' if description else ''
    if not description:
        return f'<p><strong>{code}</strong></p>'
    return f'<p><strong>{code}</strong> {description}</p>'


def format_metadata_value(value: Any) -> str:
    if isinstance(value, list):
        return '<br>'.join(
          html.escape(str(item).strip()) for item in value
        )
    return html.escape(str(value).strip())


def build_assessment_metadata_tags(
  assessments: list[dict[str, Any]] | dict[str, Any],
  slos: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    slos_by_id = {
      str(item.get('id', '')).strip(): item for item in slos or []
    }
    tags: dict[str, str] = {}

    if isinstance(assessments, list):
        items = [
          (str(item.get('id', '')).strip(), item)
          for item in assessments
          if isinstance(item, dict)
        ]
    elif isinstance(assessments, dict):
        items = assessments.items()
    else:
        return tags

    for assessment_id, fields in items:
        if not assessment_id or not isinstance(fields, dict):
            continue
        table_rows: list[tuple[str, str]] = []
        for key, value in fields.items():
            if str(key).startswith('_'):
                continue
            normalized_key = (
              'slo' if key in ('learning_outcomes', 'lo', 'slo') else key
            )
            if normalized_key == 'slo':
                outcomes: list[str] = []
                if isinstance(value, list):
                    for code in value:
                        code_str = str(code).strip()
                        if code_str in slos_by_id:
                            desc = html.escape(
                              str(slos_by_id[code_str]
                              .get('description', '')).strip()
                            )
                            if desc:
                                outcomes.append(f'<li>{desc}</li>')
                            else:
                                outcomes.append(
                                  f'<li>{html.escape(code_str)}</li>'
                                )
                        else:
                            outcomes.append(
                              f'<li>{html.escape(code_str)}</li>'
                            )
                detail = f"<ul>{''.join(outcomes)}</ul>" if outcomes else ''
                normalized_key = 'slo'
            else:
                detail = format_metadata_value(value)
            tags[f'assessment|{assessment_id}|{normalized_key}'] = detail
            table_rows.append((
              normalized_key.replace('_', ' ').title(), detail
            ))
        if table_rows:
            lines: list[str] = [
              '<table>',
              '<thead><tr><th>Field</th><th>Details</th></tr></thead>',
              '<tbody>',
            ]
            for label, detail in table_rows:
                lines.append(f'<tr><td>{label}</td><td>{detail}</td></tr>')
            lines.append('</tbody></table>')
            table_markup = '\n'.join(lines)
            tags[f'assessment|{assessment_id}|meta_table'] = table_markup
            tags[
              f"assessment|{fields.get('_key', assessment_id)}|meta_table"
            ] = table_markup
    return tags


def find_outline(root: Path) -> Path:
    for name in ('outline.md', 'outline.yaml', 'outline.yml'):
        p = root / name
        if p.exists():
            return p
    raise SystemExit(
      'outline.md or outline.yaml is required at the subject root'
    )


def load_outline(root: Path) -> dict[str, Any]:
    path = find_outline(root)
    text = path.read_text(encoding='utf-8')
    if path.suffix == '.md':
        frontmatter_match = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
        yaml_text = frontmatter_match.group(1) if frontmatter_match else text
    else:
        yaml_text = text
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f'Failed to parse {path.name}: {exc}') from exc
    return data


def build_tag_map(root: Path) -> dict[str, str]:
    data = load_outline(root)

    tags: dict[str, str] = {}

    subject_obj = data.get('subject') or {}
    if isinstance(subject_obj, dict):
        for key, val in subject_obj.items():
            if isinstance(val, str):
                tags[f'outline.subject.{key}'] = val
                tags[f'outline.{key}'] = val

    slos_obj = data.get('slo') or data.get('slos') or {}
    if isinstance(slos_obj, dict):
        slos = [{'id': k, 'description': v} for k, v in slos_obj.items()]
    elif isinstance(slos_obj, list):
        slos = slos_obj
    else:
        slos = []

    if slos:
        tags['slo'] = render_learning_outcomes(slos)
        tags['^slo'] = tags['slo']
        for outcome in slos:
            code = str(outcome.get('id', '')).strip()
            if not code:
                continue
            snippet = render_single_learning_outcome(outcome)
            if snippet:
                tags[f'slo|{code}'] = snippet
                tags[f'slo-{code}'] = snippet
                tags[f'^slo-{code}'] = snippet

    assessments_obj = (
      data.get('assessment') or data.get('assessments') or {}
    )
    if isinstance(assessments_obj, dict):
        assessments_list = []
        for key, val in assessments_obj.items():
            if isinstance(val, dict):
                entry = dict(val)
                entry.setdefault('id', str(entry.get('id') or key))
                entry['_key'] = str(key).strip()
                assessments_list.append(entry)
        assessments = assessments_list
    else:
        assessments = (
          assessments_obj if isinstance(assessments_obj, list) else []
        )

    slos_lookup = {
      str(item.get('id', '')).strip(): item
      for item in slos
      if isinstance(item, dict)
    }

    tags.update(build_assessment_metadata_tags(assessments, slos))
    if isinstance(assessments, list):
        for entry in assessments:
            aid = str(entry.get('id', '')).strip()
            key = str(entry.get('_key', aid)).strip()
            if not aid:
                continue
            title = str(entry.get('title', '')).strip()
            tags[f'assess-{aid}-number'] = aid
            tags[f'ass-{aid}-number'] = aid
            tags[f'^assess-{aid}-number'] = aid
            tags[f'^ass-{aid}-number'] = aid
            tags[f'outline.assessment.{aid}.number'] = aid
            tags[f'outline.assessment.{key}.number'] = aid
            tags[f'outline.assessment.{aid}.id'] = aid
            tags[f'outline.assessment.{key}.id'] = aid
            if title:
                tags[f'assess-{aid}'] = title
                tags[f'assess-{aid}-title'] = title
                tags[f'ass-{aid}'] = title
                tags[f'ass-{aid}-title'] = title
                tags[f'^assess-{aid}'] = title
                tags[f'^assess-{aid}-title'] = title
                tags[f'^ass-{aid}'] = title
                tags[f'^ass-{aid}-title'] = title
                tags[f'outline.assessment.{aid}.title'] = title
                tags[f'outline.assessment.{key}.title'] = title
            meta_key = f'assessment|{aid}|meta_table'
            alt_meta_key = f'assessment|{key}|meta_table'
            if meta_key in tags:
                table = tags[meta_key]
            elif alt_meta_key in tags:
                table = tags[alt_meta_key]
            else:
                table = ''
            if table:
                tags[f'assess-{aid}-meta'] = table
                tags[f'ass-{aid}-meta'] = table
                tags[f'^assess-{aid}-meta'] = table
                tags[f'^ass-{aid}-meta'] = table
                tags[f'^assess-{aid}-meta-table'] = table
                tags[f'^ass-{aid}-meta-table'] = table
                tags[f'outline.assessment.{aid}.metatable'] = table
                tags[f'outline.assessment.{key}.metatable'] = table

    def _is_slo_path(path: str) -> bool:
        return (
          path.endswith('.learning_outcomes')
          or path.endswith('.slo')
          or '.learning_outcomes.' in path
          or '.slo.' in path
        )

    def _slo_snippets(
      values: list[Any],
      lookup: dict[str, Any],
    ) -> list[str]:
        snippets: list[str] = []
        for item in values:
            code = str(item).strip()
            if code in lookup:
                desc = html.escape(
                  str(lookup[code].get('description', '')).strip()
                )
                snippets.append(f'<li>{desc}</li>' if desc
                                else f'<li>{html.escape(code)}</li>')
            else:
                snippets.append(f'<li>{html.escape(code)}</li>')
        return snippets

    def to_table(
      value: Any,
      prefix: str,
      lookup: dict[str, Any] | None,
    ) -> str | None:
        if isinstance(value, dict):
            rows = []
            for k, v in value.items():
                if str(k).startswith('_'):
                    continue
                child_prefix = f'{prefix}.{k}'
                is_scalar_list = (
                  isinstance(v, list)
                  and all(isinstance(i, (str, int, float)) for i in v)
                )
                if is_scalar_list:
                    if lookup and _is_slo_path(child_prefix):
                        snips = _slo_snippets(v, lookup)
                        detail = f"<ul>{''.join(snips)}</ul>" if snips else ''
                    else:
                        detail = '<br>'.join(
                          html.escape(str(i).strip()) for i in v
                        )
                else:
                    nested = to_table(v, child_prefix, lookup)
                    detail = nested if nested is not None else html.escape(
                      str(v)
                    )
                rows.append((str(k).replace('_', ' ').title(), detail))
            if rows:
                lines = ['<table>', '<tbody>']
                for label, detail in rows:
                    lines.append(
                      f'<tr><td>{label}</td><td>{detail}</td></tr>'
                    )
                lines.append('</tbody></table>')
                return '\n'.join(lines)
        if isinstance(value, list):
            if value and all(isinstance(i, (dict, list)) for i in value):
                lines = ['<table>', '<tbody>']
                for idx, item in enumerate(value):
                    cell = (
                      to_table(item, f'{prefix}.{idx}', lookup)
                      or html.escape(str(item))
                    )
                    lines.append(
                      f'<tr><td>{idx}</td><td>{cell}</td></tr>'
                    )
                lines.append('</tbody></table>')
                return '\n'.join(lines)
            if all(isinstance(i, (str, int, float)) for i in value):
                if lookup and _is_slo_path(prefix):
                    snips = _slo_snippets(value, lookup)
                    return f"<ul>{''.join(snips)}</ul>" if snips else ''
                return '<br>'.join(
                  html.escape(str(i).strip()) for i in value
                )
        return None

    def flatten(
      obj: Any,
      prefix: str,
      lookup: dict[str, Any] | None,
    ) -> None:
        if isinstance(obj, dict):
            table_value = to_table(obj, prefix, lookup)
            if table_value:
                tags[prefix] = table_value
            for k, v in obj.items():
                flatten(v, f'{prefix}.{k}', lookup)
        elif isinstance(obj, list):
            if all(isinstance(item, (str, int, float)) for item in obj):
                if lookup and _is_slo_path(prefix):
                    snips = _slo_snippets(obj, lookup)
                    tags[prefix] = (
                      f"<ul>{''.join(snips)}</ul>" if snips else ''
                    )
                else:
                    tags[prefix] = ', '.join(str(item) for item in obj)
            else:
                table_value = to_table(obj, prefix, lookup)
                if table_value:
                    tags[prefix] = table_value
                for idx, item in enumerate(obj):
                    flatten(item, f'{prefix}.{idx}', lookup)
        else:
            tags[prefix] = str(obj)

    flatten(data, 'outline', slos_lookup)

    for key, value in list(tags.items()):
        if key.startswith('^'):
            tags[f'outline#{key}'] = value
    return tags
