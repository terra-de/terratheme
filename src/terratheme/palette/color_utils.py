"""Shared colour math utilities for terratheme.

All functions operate on ``(R, G, B)`` tuples with values in 0-255 range
unless otherwise noted.
"""

from __future__ import annotations

import math


# ── Conversion ──────────────────────────────────────────────────────────


def rgb_to_hsl(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Return ``(hue 0-360, saturation 0-1, lightness 0-1)``."""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0

    if mx == mn:
        return 0.0, 0.0, l

    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)

    if mx == r:
        h = (g - b) / d + (6.0 if g < b else 0.0)
    elif mx == g:
        h = (b - r) / d + 2.0
    else:
        h = (r - g) / d + 4.0
    h /= 6.0

    return h * 360.0, s, l


def hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    """Convert HSL to ``(R, G, B)`` in 0-255 range.

    *h* in 0-360, *s* and *l* in 0-1.
    """
    h = h / 360.0

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0.0:
            t += 1.0
        if t > 1.0:
            t -= 1.0
        if t < 1.0 / 6.0:
            return p + (q - p) * 6.0 * t
        if t < 1.0 / 2.0:
            return q
        if t < 2.0 / 3.0:
            return p + (q - p) * (2.0 / 3.0 - t) * 6.0
        return p

    if s == 0.0:
        r = g = b = l
    else:
        q = l * (1.0 + s) if l < 0.5 else l + s - l * s
        p = 2.0 * l - q
        r = hue_to_rgb(p, q, h + 1.0 / 3.0)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1.0 / 3.0)

    return r * 255.0, g * 255.0, b * 255.0


def rgb_hex(r: int, g: int, b: int) -> str:
    """Return ``#rrggbb`` for an (R, G, B) tuple."""
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse ``#rrggbb`` or ``rrggbb`` to ``(R, G, B)``."""
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ── Perceptual math ─────────────────────────────────────────────────────


def relative_luminance(r: float, g: float, b: float) -> float:
    """WCAG 2.1 relative luminance of an sRGB colour (values 0-255)."""
    def linearize(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (
        0.2126 * linearize(r)
        + 0.7152 * linearize(g)
        + 0.0722 * linearize(b)
    )


def contrast_ratio(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    """WCAG 2.1 contrast ratio between two sRGB colours."""
    l1 = relative_luminance(*a)
    l2 = relative_luminance(*b)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def rgb_euclidean(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    """Simple RGB Euclidean distance — cheap delta-E proxy."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


# ── Manipulation ────────────────────────────────────────────────────────


def reduce_chroma(
    r: float, g: float, b: float, factor: float = 0.1,
) -> tuple[float, float, float]:
    """Desaturate a colour toward neutral grey while preserving luminance.

    *factor* = 0 → fully grey, *factor* = 1 → unchanged.
    """
    h, s, l = rgb_to_hsl(r, g, b)
    new_s = s * factor
    return hsl_to_rgb(h, new_s, l)


def adjust_tone(
    r: float, g: float, b: float, target_luminance: float,
) -> tuple[float, float, float]:
    """Shift a colour's lightness to *target_luminance* (0-1) while preserving
    hue and chroma as much as possible.

    This does a HSL-space tone shift, which preserves hue but may change
    perceived saturation slightly — acceptable for our use.
    """
    h, s, _l = rgb_to_hsl(r, g, b)
    # Clamp target so we don't lose all saturation at extremes
    clamped = max(0.02, min(0.98, target_luminance))
    return hsl_to_rgb(h, s, clamped)


def blend(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    t: float = 0.5,
) -> tuple[float, float, float]:
    """Linearly interpolate between two colours (t=0 → a, t=1 → b)."""
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def clamp_rgb(r: float, g: float, b: float) -> tuple[int, int, int]:
    """Round and clamp to 0-255."""
    return (
        max(0, min(255, round(r))),
        max(0, min(255, round(g))),
        max(0, min(255, round(b))),
    )
