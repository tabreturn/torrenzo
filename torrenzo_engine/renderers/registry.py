from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, TypeAlias, Any, Dict, Iterable, Tuple

class Renderer(Protocol):
    def __call__(
        self,
        input_path: Path,
        output_path: Path,
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        ...

RendererFactory: TypeAlias = Callable[[Any], Renderer]

@dataclass
class RendererRecord:
    name: str
    factory: RendererFactory


class RendererRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, RendererFactory] = {}

    def register(self, name: str, factory: RendererFactory) -> None:
        if name in self._registry:
            raise ValueError(f"Renderer '{name}' already registered")
        self._registry[name] = factory

    def get(self, name: str) -> RendererFactory:
        if name not in self._registry:
            raise KeyError(f"Renderer '{name}' not found")
        return self._registry[name]

    def list(self) -> Iterable[str]:
        return tuple(self._registry.keys())

    def clear(self) -> None:
        self._registry.clear()
