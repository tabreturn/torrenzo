from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Protocol

from .renderers.registry import RendererRegistry, RendererFactory


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


class Pipeline:
    def __init__(self, root: Path, build_dir: Path, registry: RendererRegistry) -> None:
        self.root = root
        self.build_dir = build_dir
        self.registry = registry

    def iter_jobs(self, job_specs: Iterable[RenderJob]) -> Iterable[RenderJob]:
        for spec in job_specs:
            yield spec

    def execute(self, job_specs: Iterable[RenderJob]) -> List[str]:
        diagnostics: List[str] = []
        for job in self.iter_jobs(job_specs):
            output_dir = self.build_dir / job.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            renderer_factory = self.registry.get(job.renderer)
            renderer = renderer_factory(None)
            for input_path in sorted(self.root.glob(job.input_pattern)):
                output_path = output_dir / input_path.with_suffix('.pdf').name
                success, msg = renderer(input_path, output_path, job.context)
                diagnostics.append(f"{job.name}: {msg}")
        return diagnostics
