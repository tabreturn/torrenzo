"""build_stamp — shared utilities for build timestamps and staleness checks."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    """Return the current local time as an ISO-8601 string with UTC offset."""
    return (
      datetime.now(tz=timezone.utc)
      .astimezone()
      .isoformat(timespec='seconds')
    )


def html_comment(source: Path, ts: str) -> str:
    return f'<!-- built: {ts}  source: {source.name} -->\n'


def is_stale(
  source: Path,
  output: Path,
  deps: list[Path] | None = None,
) -> bool:
    """True if output does not exist or is older than source or any dep."""
    if not output.exists():
        return True
    out_mtime = output.stat().st_mtime
    if source.stat().st_mtime > out_mtime:
        return True
    for dep in (deps or []):
        if dep.exists() and dep.stat().st_mtime > out_mtime:
            return True
    return False
