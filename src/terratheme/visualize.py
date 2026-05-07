"""Terminal visualisation of a derived palette.

Draws a mock terminal UI using ANSI true-colour escape codes so the
user can preview how the palette will look in practice.
"""

from __future__ import annotations

import os
from typing import Any

from terratheme.palette.color_utils import hex_to_rgb


# ── ANSI helpers ────────────────────────────────────────────────────────


def _ansi(code: int) -> str:
    return f"\033[{code}m"


RESET = _ansi(0)
BOLD = _ansi(1)


def fg(hex_str: str, text: str) -> str:
    """Colour *text* with the given hex foreground."""
    r, g, b = hex_to_rgb(hex_str)
    return f"\033[38;2;{r};{g};{b}m{text}{RESET}"


def bg(hex_str: str, block: str = "  ") -> str:
    """Return *block* with the given hex background colour."""
    r, g, b = hex_to_rgb(hex_str)
    return f"\033[48;2;{r};{g};{b}m{block}{RESET}"


def fg_on_bg(fg_hex: str, bg_hex: str, text: str) -> str:
    """Return *text* with foreground and background colours."""
    r_fg, g_fg, b_fg = hex_to_rgb(fg_hex)
    r_bg, g_bg, b_bg = hex_to_rgb(bg_hex)
    return f"\033[38;2;{r_fg};{g_fg};{b_fg};48;2;{r_bg};{g_bg};{b_bg}m{text}{RESET}"


# ── Layout helpers ──────────────────────────────────────────────────────


def _box(title: str, width: int) -> str:
    top = f"┌─ {title} " + "─" * (width - len(title) - 4) + "┐"
    bot = "└" + "─" * (width - 2) + "┘"
    return f"{BOLD}{top}{RESET}\n{bot}"


def _section_line(label: str, bg_hex: str, fg_hex: str, width: int) -> str:
    """A sample line showing a background colour with sample text."""
    padded = f"  {label:<6}  {fg_on_bg(fg_hex, bg_hex, ' This is sample text ')}  "
    return padded.ljust(width)


# ── Main visualisation ──────────────────────────────────────────────────


def visualize(palette: dict[str, Any], image_path: str) -> None:
    """Print a terminal UI mockup using palette tokens."""
    mode = palette["mode"]
    tokens = palette["dark"]  # always show dark mode in preview
    dark_tokens = palette["dark"]
    light_tokens = palette["light"]
    log = palette["contrast_log"]

    terminal_width = _terminal_width()
    content_width = min(terminal_width - 2, 72)

    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────
    fname = os.path.basename(image_path)
    header = f" Palette: {fname:<30} mode: {mode} "
    lines.append("")
    lines.append(f"{BOLD}{'─' * content_width}{RESET}")
    lines.append(f"{BOLD}│{RESET}{header:<{content_width - 2}}{BOLD}│{RESET}")
    lines.append(f"{BOLD}{'─' * content_width}{RESET}")
    lines.append("")

    # ── Background samples ──────────────────────────────────────────
    lines.append(f"{BOLD}  Backgrounds{RESET}")
    lines.append("")
    for name in ("top", "front", "base", "back"):
        b = tokens[name]
        lines.append(_section_line(name, b, tokens["standard"], content_width))
    lines.append("")

    # ── Separator ───────────────────────────────────────────────────
    lines.append(f"{BOLD}{'─' * content_width}{RESET}")
    lines.append("")

    # ── Semantic colour swatches ────────────────────────────────────
    lines.append(f"{BOLD}  Colours{RESET}")
    lines.append("")
    for i in range(5):
        c = tokens[f"c{i}"]
        oc = tokens[f"on_c{i}"]
        swatch = f"  {bg(c)}  {fg(c, c):<9}  c{i}    {bg(oc)}  {fg(oc, oc):<9}  on_c{i}"
        lines.append(swatch)
    lines.append("")

    # ── Error & Outline ─────────────────────────────────────────────
    err = tokens["error"]
    on_err = tokens["on_error"]
    outline = tokens["outline"]
    line = (
        f"  {bg(err)}  {fg(err, err):<9}  error    "
        f"{bg(on_err)}  {fg(on_err, on_err):<9}  on_error"
    )
    lines.append(line)
    lines.append("")
    # Outline as a coloured bar
    bar_width = content_width - 4
    outline_bar = bg(outline, " " * bar_width)
    lines.append(f"  outline  {outline_bar}  {fg(outline, outline)}")
    lines.append("")

    # ── Separator ───────────────────────────────────────────────────
    lines.append(f"{BOLD}{'─' * content_width}{RESET}")
    lines.append("")

    # ── Contrast ratios ─────────────────────────────────────────────
    lines.append(f"{BOLD}  Contrast ratios{RESET}")
    lines.append("")
    for key, ratio in log.items():
        # Parse ratio value for colour coding
        ratio_val = float(ratio[:-2])
        if ratio_val >= 4.5:
            color = "#33cc33"  # green — excellent
        elif ratio_val >= 3.0:
            color = "#cccc33"  # yellow — okay
        else:
            color = "#cc3333"  # red — bad
        lines.append(f"    {key:<30}  {fg(color, ratio)}")
    lines.append("")

    # ── Footer ──────────────────────────────────────────────────────
    lines.append(f"{BOLD}{'─' * content_width}{RESET}")
    lines.append("")

    print("\n".join(lines))


def _terminal_width() -> int:
    """Detect terminal width, fall back to 80."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80
