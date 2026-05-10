"""Push terminal colours to all active PTY sessions via OSC escape sequences.

This module is a first-class part of the terratheme library.  It reads
a rendered foot ``colors.ini``, determines the active mode (dark/light),
and writes OSC 4/10/11/12 escape sequences to every ``/dev/pts/*`` device,
updating all running terminal sessions instantly.

Usage
-----
    from terratheme.terminal_push import push_from_config
    push_from_config("~/.config/foot/colors.ini")

Or from the command line::

    python -m terratheme.terminal_push [path-to-colors.ini]
"""

from __future__ import annotations

import configparser
import glob
import sys
from pathlib import Path

# ── OSC escape template ─────────────────────────────────────────────────
# OSC 4;N;COLOR  — set ANSI palette entry N (0-15)
# OSC 10;COLOR   — set foreground (text)
# OSC 11;COLOR   — set background
# OSC 12;COLOR   — set cursor (foreground colour of the cursor cell)
OSC = "\033]{};{}\007"


# ── Internal helpers ────────────────────────────────────────────────────


def _normalize_color(value: str) -> str:
    """Ensure a colour string has a ``#`` prefix."""
    value = value.strip()
    return value if value.startswith("#") else f"#{value}"


def _send(fd, msg: str) -> None:
    """Write *msg* to an open file descriptor, ignoring errors."""
    try:
        fd.write(msg)
        fd.flush()
    except OSError:
        pass


# ── Public API ──────────────────────────────────────────────────────────


def load_active_theme(config_path: str | Path) -> dict:
    """Read a foot ``colors.ini`` and return the active mode's theme data.

    Returns a dict with keys:
        ``foreground``  — hex colour string
        ``background``  — hex colour string
        ``cursor``      — hex colour string
        ``palette``     — list of 16 hex colour strings (indices 0-15)
    """
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(str(config_path)):
        raise FileNotFoundError(f"Could not read Foot colours file: {config_path}")

    mode = parser["main"]["initial-color-theme"].strip().lower()
    if mode not in {"dark", "light"}:
        raise ValueError(f"Unsupported Foot colour theme: {mode}")

    section = parser[f"colors-{mode}"]

    cursor_parts = section["cursor"].split()
    if len(cursor_parts) != 2:
        raise ValueError(
            f"Expected Foot cursor to have two colours, got: {section['cursor']}"
        )

    palette = [_normalize_color(section[f"regular{i}"]) for i in range(8)]
    palette.extend(_normalize_color(section[f"bright{i}"]) for i in range(8))

    return {
        "foreground": _normalize_color(section["foreground"]),
        "background": _normalize_color(section["background"]),
        "cursor": _normalize_color(cursor_parts[1]),
        "palette": palette,
    }


def push_to_ptys(theme: dict) -> None:
    """Write OSC escape sequences for *theme* to all active PTY sessions.

    Silently skips PTYs that the process does not have permission to write
    to (other users' sessions, already-closed terminals).
    """
    for pts in glob.glob("/dev/pts/[0-9]*"):
        try:
            with open(pts, "w", encoding="utf-8") as fd:
                for idx, color in enumerate(theme["palette"]):
                    _send(fd, OSC.format(f"4;{idx}", color))

                _send(fd, OSC.format("10", theme["foreground"]))
                _send(fd, OSC.format("11", theme["background"]))
                _send(fd, OSC.format("12", theme["cursor"]))
        except PermissionError:
            pass
        except OSError:
            pass


def push_from_config(config_path: str | Path) -> None:
    """Convenience: load theme from *config_path* and push to all PTYs.

    This is the main entry point you'll want to call from other terratheme
    modules (e.g. a target's ``write`` method).
    """
    theme = load_active_theme(config_path)
    push_to_ptys(theme)


# ── CLI entry point ────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point::
    
        python -m terratheme.terminal_push [path-to-colors.ini]
    """
    config_path = (
        Path(sys.argv[1]).expanduser()
        if len(sys.argv) > 1
        else Path.home() / ".config/foot/colors.ini"
    )
    push_from_config(config_path)


if __name__ == "__main__":
    main()
