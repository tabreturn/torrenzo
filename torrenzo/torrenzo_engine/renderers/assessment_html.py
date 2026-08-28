from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from ..build_stamp import html_comment, now_iso
from ..cc_export import _assignment_description_html, _module_css
from ..preprocess import collect_valid_outputs


def render(
  input_path: Path,
  output_path: Path,
  context: Dict[str, Any],
) -> Tuple[bool, str, list[str]]:
    """Render an assessment brief as a Canvas-style description HTML page."""
    warnings: list[str] = []
    subject_root = context.get(
      'subject_root', input_path.parent.parent.parent)
    ass_num = int(input_path.parent.name.split('_')[1])
    ass_dir_name = input_path.parent.name

    module_css = _module_css(subject_root)
    valid_targets = collect_valid_outputs(subject_root)

    ass = {
      'num': ass_num,
      'ass_dir_name': ass_dir_name,
      'pdf_filename': f'{ass_dir_name}.pdf',
      'title': f'Assessment {ass_num}',
      'assignment_id': ass_dir_name,
    }

    html = _assignment_description_html(
      ass, input_path, module_css, valid_targets, subject_root,
      cache_bust=context.get('cache_bust', ''),
    )

    # rewrite cartridge-only placeholders to local preview paths
    pdf_dir = f'assessments/{ass_dir_name}'
    html = html.replace(
      f'$IMS-CC-FILEBASE$/{pdf_dir}/{ass_dir_name}.pdf',
      f'../assessments_briefs/{ass_dir_name}.pdf',
    )
    html = html.replace(
      f'$IMS-CC-FILEBASE$/{pdf_dir}/assets/',
      f'../assessments_briefs/',
    )
    # fix module page wiki-links to point at ../modules_html/
    html = html.replace(
      'href="mod_', 'href="../modules_html/mod_'
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
      html_comment(input_path, now_iso()) + html,
      encoding='utf-8',
    )
    return True, f'{input_path} -> {output_path}', warnings
