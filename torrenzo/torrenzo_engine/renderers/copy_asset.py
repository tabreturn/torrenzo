from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Tuple


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    if input_path.is_dir():
        return True, f"{input_path} skipped directory"
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output_path)
        return True, f"{input_path} -> {output_path}"
    except Exception as exc:
        return False, f"{input_path} -> {output_path} failed: {exc}"
