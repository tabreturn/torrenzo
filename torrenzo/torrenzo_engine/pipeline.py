
import json

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Protocol

from .renderers.registry import RendererRegistry
from .build_stamp import is_stale, now_iso


RESET = '\033[0m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'
BOLD = '\033[1m'


def fmt(level: str, message: str) -> str:
    if level == 'info':
        return f'{GREEN}✓{RESET} {message}'
    if level == 'warning':
        return f'{YELLOW}!{RESET} {message}'
    return f'{RED}✗{RESET} {message}'


def order_levels(
  entries: List[tuple[str, str]],
) -> List[tuple[str, str]]:
    level_rank = {'info': 0, 'warning': 1, 'error': 2}
    return sorted(
      entries,
      key=lambda item: (level_rank.get(item[0], 3), entries.index(item)),
    )


class DiagnosticLevel(str):
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'


@dataclass
class RenderJob:
    name: str
    input_pattern: str
    output_dir: Path
    renderer: str
    context: Dict[str, Any]
    output_ext: str = ''
    output_namer: Callable[[Path], str] | None = None
    deps: List[Path] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.deps is None:
            self.deps = []


class Pipeline:
    def __init__(
      self,
      root: Path,
      build_dir: Path,
      registry: RendererRegistry,
    ) -> None:
        self.root = root
        self.build_dir = build_dir
        self.registry = registry

    def _shorten(self, msg: str) -> str:
        """Replace absolute subject-root and build-dir prefixes with
        relative paths in a renderer message string."""
        msg = msg.replace(str(self.root) + '/', '')
        msg = msg.replace(str(self.build_dir) + '/', 'build/')
        return msg

    def iter_jobs(
      self,
      job_specs: Iterable[RenderJob],
    ) -> Iterable[RenderJob]:
        for spec in job_specs:
            yield spec

    def execute(
      self,
      job_specs: Iterable[RenderJob],
      force: bool = False,
    ) -> List[str]:
        entries: List[tuple[str, str]] = []
        built_files: List[str] = []
        built_count = 0
        skipped_count = 0
        expected_outputs: set[Path] = set()
        seen_outputs: dict[Path, Path] = {}

        job_list = list(self.iter_jobs(job_specs))

        for job in job_list:
            output_dir = self.build_dir / job.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            renderer_factory = self.registry.get(job.renderer)
            renderer = renderer_factory(None)
            for input_path in sorted(self.root.glob(job.input_pattern)):
                if input_path.is_dir():
                    continue
                if job.output_namer:
                    output_name = job.output_namer(input_path)
                elif job.output_ext:
                    output_name = input_path.with_suffix(job.output_ext).name
                else:
                    output_name = input_path.name

                output_path = output_dir / output_name
                if output_path in seen_outputs:
                    entries.append((
                        'warning',
                        f'{job.name}: collision — {self._shorten(str(input_path))} '
                        f'and {self._shorten(str(seen_outputs[output_path]))} '
                        f'both target {self._shorten(str(output_path))}',
                    ))
                else:
                    seen_outputs[output_path] = input_path
                expected_outputs.add(output_path)

                if not force and not is_stale(
                  input_path, output_path, job.deps
                ):
                    skipped_count += 1
                    continue

                result = renderer(input_path, output_path, job.context)
                render_warnings: list[str] = []
                if isinstance(result, tuple) and len(result) == 3:
                    success, msg, render_warnings = result
                else:
                    success, msg = result
                level = 'info' if success else 'error'
                entries.append((level, f'{job.name}: {self._shorten(msg)}'))
                for warning in render_warnings:
                    entries.append((
                      'warning',
                      f'{job.name}: {input_path.name}: {warning}',
                    ))
                if success:
                    built_count += 1
                    built_files.append(self._shorten(str(output_path)))

        log_path = self.build_dir / 'build-log.json'
        prior_entries: list[dict] = []
        if log_path.exists():
            try:
                prior_entries = json.loads(log_path.read_text())
            except (json.JSONDecodeError, ValueError):
                prior_entries = []
        expected_outputs.add(log_path)

        pruned_count = self._prune_orphans(expected_outputs)

        ordered_entries = order_levels(entries)
        formatted = [fmt(level, msg) for level, msg in ordered_entries]
        if pruned_count:
            formatted.append(fmt(
              'info',
              f'{pruned_count} orphaned file(s) removed from build/',
            ))
        if skipped_count:
            formatted.append(fmt(
              'info',
              f'{skipped_count} file(s) up-to-date, skipped',
            ))
        if built_count:
            formatted.append(fmt(
              'info',
              f'{built_count} file(s) newly built',
            ))
            for f in built_files:
                formatted.append(f'  {f}')
            prior_entries.append({
                'built_at': now_iso(),
                'files': built_files,
            })
            log_path.write_text(
                json.dumps(prior_entries, indent=2) + '\n',
                encoding='utf-8',
            )
            formatted.append(fmt(
              'info',
              f'build log → {self._shorten(str(log_path))}',
            ))
        return formatted

    def _prune_orphans(self, expected_outputs: set[Path]) -> int:
        """Remove files in build_dir that are no longer expected outputs."""
        removed = 0
        for existing in list(self.build_dir.rglob('*')):
            if existing.is_file() and existing not in expected_outputs:
                existing.unlink()
                removed += 1
        for existing in sorted(self.build_dir.rglob('*'), reverse=True):
            if existing.is_dir():
                try:
                    existing.rmdir()
                except OSError:
                    pass
        return removed
