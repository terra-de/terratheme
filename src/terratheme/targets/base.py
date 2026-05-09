"""Base target class for terratheme output targets."""

from __future__ import annotations

import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path


class BaseTarget(ABC):
    """A single terratheme output target.

    Each subclass represents one app/system component that consumes
    the Terra DE palette (e.g. Hyprland window borders, Zellij theme).

    Subclasses must define:
      - name, description, output_path (class attributes OR properties)
      - render()
    Subclasses may override:
      - post_hook() to run shell commands after writing
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """CLI-friendly target name (e.g. ``"hyprland"``)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable one-liner."""

    @property
    @abstractmethod
    def output_path(self) -> str:
        """Filesystem path to write to (may contain ``~``)."""

    @abstractmethod
    def render(self, palette: dict, mode: str) -> str:
        """Return the full file content as a string.

        Parameters
        ----------
        palette:
            The full v2 palette dict, e.g. ``{"version": 2, "mode": "dark",
            "dark": {...}, "light": {...}, "contrast_log": {...}}``.
        mode:
            The active mode — ``"dark"`` or ``"light"``.  Use
            ``palette[mode]`` to get the 20-token colour dict for this mode.
        """

    def post_hook(self) -> list[str]:
        """Shell commands to run after the file is written.

        Return an empty list (the default) if no hook is needed.
        """
        return []

    # ------------------------------------------------------------------
    # Public helpers (usually not overridden)
    # ------------------------------------------------------------------

    def write(self, palette: dict, mode: str) -> Path:
        """Render, write to disk, and run post-hooks.

        Returns the :class:`Path` that was written to.
        """
        content = self.render(palette, mode)
        path = Path(self.output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"  {self.name}: {path}", file=sys.stderr)

        for cmd in self.post_hook():
            try:
                subprocess.run(cmd, shell=True, check=False)
            except OSError as exc:
                print(f"  [{self.name}] hook failed: {exc}", file=sys.stderr)

        return path
