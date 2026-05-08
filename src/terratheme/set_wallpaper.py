"""Wallpaper setting and runtime state persistence for terratheme set."""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path


# ── Random transition generation ────────────────────────────────────────

_TRANSITION_TYPES = [
    "simple", "fade", "left", "right", "top", "bottom",
    "wipe", "wave", "grow", "center", "any", "outer",
]


def _random_transition_args() -> list[str]:
    """Build a list of ``awww img`` flags with randomised transition values."""
    ttype = random.choice(_TRANSITION_TYPES)
    args: list[str] = [
        "--transition-type", ttype,
        "--transition-duration", f"{random.uniform(0.3, 0.8):.2f}",
        "--transition-fps", "60",
    ]

    # Directional transitions can take an angle
    if ttype in ("wipe", "wave"):
        args += ["--transition-angle", str(random.randint(0, 360))]

    # Grow / outer can take a position
    if ttype in ("grow", "outer") and random.random() < 0.3:
        x = random.uniform(0.1, 0.9)
        y = random.uniform(0.1, 0.9)
        args += ["--transition-pos", f"{x:.2f},{y:.2f}"]

    return args


# ── awww call ────────────────────────────────────────────────────────────


def run_awww(image_path: str) -> None:
    """Set the wallpaper display via ``awww img`` with random transitions."""
    cmd = ["awww", "img", image_path, *_random_transition_args()]
    print(f"  wallpaper: awww img {Path(image_path).name}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  warning: awww exited with code {result.returncode}", file=sys.stderr)
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                print(f"    {line}", file=sys.stderr)


# ── Runtime state persistence ────────────────────────────────────────────


_RUNTIME_STATE_PATH = Path.home() / ".local/state/quickshell/runtime_state.json"


def _read_runtime_state() -> dict[str, object]:
    """Read the current Quickshell runtime state, or return defaults."""
    if _RUNTIME_STATE_PATH.exists():
        try:
            data = json.loads(_RUNTIME_STATE_PATH.read_text())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "wallpaperPath": "",
        "darkModeEnabled": True,
        "notificationsDndEnabled": False,
    }


def update_runtime_state(image_path: str, dark_mode: bool) -> None:
    """Persist the wallpaper path and dark mode to Quickshell's state file.

    Writes atomically via a temporary file + rename.
    The wallpaper path is resolved to an absolute path before saving.
    """
    state = _read_runtime_state()
    state["wallpaperPath"] = str(Path(image_path).resolve())
    state["darkModeEnabled"] = dark_mode

    _RUNTIME_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _RUNTIME_STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, _RUNTIME_STATE_PATH)
    print(f"  state:   {_RUNTIME_STATE_PATH}", file=sys.stderr)
