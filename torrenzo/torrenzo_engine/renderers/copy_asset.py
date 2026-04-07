from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Dict, Tuple

from ..build_stamp import now_iso


def _copy_svg(input_path: Path, output_path: Path, ts: str) -> None:
    text = input_path.read_text(encoding="utf-8")
    comment = f"<!-- built: {ts}  source: {input_path.name} -->"
    # Insert after the XML declaration if present, otherwise prepend
    xml_decl = re.match(r"<\?xml[^?]*\?>", text)
    if xml_decl:
        insert_at = xml_decl.end()
        text = text[:insert_at] + "\n" + comment + text[insert_at:]
    else:
        text = comment + "\n" + text
    output_path.write_text(text, encoding="utf-8")


def _copy_png(input_path: Path, output_path: Path, ts: str) -> None:
    try:
        from PIL import Image, PngImagePlugin
        img = Image.open(input_path)
        info = PngImagePlugin.PngInfo()
        for key, val in (img.info or {}).items():
            if isinstance(key, str) and isinstance(val, str):
                try:
                    info.add_text(key, val)
                except Exception:
                    pass
        info.add_text("Comment", f"built: {ts}  source: {input_path.name}")
        img.save(output_path, "PNG", pnginfo=info)
    except ImportError:
        shutil.copy2(input_path, output_path)


def render(input_path: Path, output_path: Path, context: Dict[str, Any]) -> Tuple[bool, str]:
    if input_path.is_dir():
        return True, f"{input_path} skipped directory"
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = input_path.suffix.lower()
        ts = now_iso()
        if suffix == ".svg":
            _copy_svg(input_path, output_path, ts)
        elif suffix == ".png":
            _copy_png(input_path, output_path, ts)
        else:
            shutil.copy2(input_path, output_path)
        return True, f"{input_path} -> {output_path}"
    except Exception as exc:
        return False, f"{input_path} -> {output_path} failed: {exc}"
