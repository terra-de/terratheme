"""Configuration loader for terratheme.

Reads ``~/.config/terra/terratheme.json`` and merges with sensible defaults.
Missing, partial, or malformed files fall back gracefully.

Usage
-----
    from terratheme.config import load_config

    cfg = load_config()
    if cfg.get("terminal_light_mode"):
        # terminal follows palette mode
    else:
        # terminal stays in dark mode
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── Default configuration path ──────────────────────────────────────────

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "terra" / "terratheme.json"

# ── Defaults ────────────────────────────────────────────────────────────
# ``terminal_light_mode``: when ``false`` (default), the terminal always
# operates in dark mode regardless of the palette mode.  Set to ``true``
# to let the terminal follow the palette's light/dark mode.

DEFAULTS: dict[str, object] = {
    "terminal_light_mode": False,
}

# Module-level cache so repeated calls are cheap.
_config_cache: dict[str, object] | None = None


# ── Public API ──────────────────────────────────────────────────────────


def load_config(config_path: str | Path | None = None) -> dict[str, object]:
    """Load terratheme config, merging with defaults.

    Results are cached after the first call so that multiple targets
    can query config without re-reading the file.

    Args:
        config_path: Optional explicit path.  Defaults to
            ``~/.config/terra/terratheme.json``.

    Returns:
        A dict with all config keys guaranteed to be present (merged
        with ``DEFAULTS``).
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    config: dict[str, object] = dict(DEFAULTS)

    if path.exists():
        try:
            with open(path) as f:
                user_config = json.load(f)
            if isinstance(user_config, dict):
                config.update(user_config)
        except (json.JSONDecodeError, OSError) as exc:
            print(
                f"[terratheme] warning: failed to load config from {path}: {exc}",
                file=sys.stderr,
            )

    _config_cache = config
    return config


def clear_cache() -> None:
    """Clear the config cache.

    Useful in tests or when the config file may have changed at runtime.
    """
    global _config_cache
    _config_cache = None
