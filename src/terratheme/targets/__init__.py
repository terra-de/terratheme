"""Target registry — discoverable by both ``apply`` and ``set`` commands."""

from __future__ import annotations

from pathlib import Path

from .base import BaseTarget
from .hyprland import HyprlandTarget
from .lf import LfTarget, LfPromptTarget
from .zellij import ZellijTarget

# ---------------------------------------------------------------------------
# Registry — add new targets here
# ---------------------------------------------------------------------------
_TARGETS: dict[str, type[BaseTarget]] = {
    "hyprland":  HyprlandTarget,
    "zellij":    ZellijTarget,
    "lf":        LfTarget,
    "lf-prompt": LfPromptTarget,
}


def get_target(name: str) -> BaseTarget:
    """Return an instantiated target by name.

    Raises ``ValueError`` for unknown targets.
    """
    cls = _TARGETS.get(name)
    if cls is None:
        available = ", ".join(_TARGETS)
        raise ValueError(f"Unknown target '{name}'. Available: {available}")
    return cls()


def list_targets() -> list[dict]:
    """Return metadata for all registered targets."""
    return [
        {"name": name, "description": target_cls.description}
        for name, target_cls in _TARGETS.items()
    ]


def render_all(palette: dict, mode: str) -> list[Path]:
    """Render *all* registered targets and return the list of written paths."""
    paths: list[Path] = []
    for name, target_cls in _TARGETS.items():
        target = target_cls()
        path = target.write(palette, mode)
        paths.append(path)
    return paths
