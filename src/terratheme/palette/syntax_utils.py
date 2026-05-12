"""Hue math and contrast utilities for syntax palette derivation.

Port of the Lua matugen utils that handle hue operations, contrast
adjustment, and semantic colour derivation — everything needed to
pre-compute Neovim's syntax palette in Python instead of Lua.
"""

from __future__ import annotations

import math

from terratheme.palette.color_utils import (
    clamp_rgb,
    contrast_ratio,
    hsl_to_rgb,
    rgb_hex,
    rgb_to_hsl,
    relative_luminance,
)


# ── Hue operations ───────────────────────────────────────────────────────


def hue_distance(h1: float, h2: float) -> float:
    """Shortest arc between two hues (0-1 range)."""
    diff = abs(h1 - h2)
    return 1.0 - diff if diff > 0.5 else diff


def hue_mix(h1: float, h2: float, amount: float) -> float:
    """Blend two hues along the shortest arc.

    *amount* = 0 → h1, *amount* = 1 → h2.
    """
    diff = ((h2 - h1 + 0.5) % 1.0) - 0.5
    return (h1 + diff * amount) % 1.0


def hue_midpoint(h1: float, h2: float) -> float:
    """Exact midpoint (hue_mix at 0.5)."""
    return hue_mix(h1, h2, 0.5)


def complementary_hue(hue: float, shift: float = 0.5) -> float:
    """Shift a hue by *shift* (default 0.5 = opposite)."""
    return (hue + shift) % 1.0


def circular_mean(
    entries: list[dict],
) -> float:
    """Weighted circular mean of a list of hue entries.

    Each *entry* must have ``"hue"`` (float 0-1) and ``"weight"`` (float).
    Uses vector addition (cos/sin) for correct circular averaging.
    """
    x = 0.0
    y = 0.0

    for entry in entries:
        hue = entry["hue"]
        weight = entry.get("weight", 1.0)
        angle = hue * math.pi * 2.0
        x += math.cos(angle) * weight
        y += math.sin(angle) * weight

    if x == 0.0 and y == 0.0:
        return 0.0

    angle = math.atan2(y, x)
    if angle < 0.0:
        angle += math.pi * 2.0
    return angle / (math.pi * 2.0)


def hue_diversity(sources: tuple[dict, dict, dict]) -> float:
    """Max minus min hue of the first three sources (primary/secondary/tertiary).

    Returns 0 if fewer than 2 sources.
    """
    hues = [s["hue"] for s in sources if s is not None]
    if len(hues) < 2:
        return 0.0
    return max(hues) - min(hues)


def is_complementary(h1: float, h2: float, tolerance: float = 0.08) -> bool:
    """Check if two hues are ~180 degrees apart (within *tolerance*)."""
    diff = abs(h1 - h2)
    if diff > 0.5:
        diff = 1.0 - diff
    return abs(diff - 0.5) < tolerance


def find_complementary_pair(
    hues: list[float],
) -> tuple[int | None, int | None, float | None, float | None]:
    """Find the first complementary pair in a list of hues.

    Returns ``(i, j, h1, h2)`` or ``(None, None, None, None)``.
    """
    for i, h1 in enumerate(hues):
        for j, h2 in enumerate(hues):
            if i != j and is_complementary(h1, h2):
                return i, j, h1, h2
    return None, None, None, None


def ensure_hue_spacing(
    hues: dict[str, float],
    min_difference: float,
) -> dict[str, float]:
    """Iteratively push hues apart to enforce minimum spacing."""
    sorted_items = sorted(hues.items(), key=lambda x: x[1])  # (name, hue) pairs
    items = [{"name": name, "hue": hue} for name, hue in sorted_items]

    for _ in range(10):
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                diff = hue_distance(items[i]["hue"], items[j]["hue"])
                if diff < min_difference and diff > 0:
                    shift = (min_difference - diff) / 2
                    if items[i]["hue"] > 0.5:
                        items[i]["hue"] -= shift
                        items[j]["hue"] += shift
                    else:
                        items[i]["hue"] += shift
                        items[j]["hue"] -= shift

    return {item["name"]: item["hue"] for item in items}


# ── Contrast adjustment ──────────────────────────────────────────────────


def adjust_contrast(
    rgb: tuple[float, float, float],
    bg_rgb: tuple[float, float, float],
    target_ratio: float,
) -> tuple[int, int, int]:
    """Binary search on lightness to achieve *target_ratio* contrast against *bg*.

    Preserves hue and saturation. Returns the original colour if the target
    is unreachable.
    """
    if contrast_ratio(rgb, bg_rgb) >= target_ratio:
        return clamp_rgb(rgb[0], rgb[1], rgb[2])

    h, s, l = rgb_to_hsl(rgb[0], rgb[1], rgb[2])
    bg_lum = relative_luminance(*bg_rgb)
    min_l = 0.10
    max_l = 0.90

    if bg_lum > 0.5:
        low, high = min_l, l
    else:
        low, high = l, max_l

    best_l = l
    best_ratio = contrast_ratio(rgb, bg_rgb)

    for _ in range(30):
        mid = (low + high) / 2
        r_test, g_test, b_test = hsl_to_rgb(h, s, mid)
        test_rgb = clamp_rgb(r_test, g_test, b_test)
        ratio = contrast_ratio(test_rgb, bg_rgb)

        if ratio >= target_ratio:
            # Pass — set high = mid to try DARKER (lower L) and find
            # the minimum lightness that still meets the target.
            if ratio > best_ratio:
                best_ratio = ratio
                best_l = mid
            high = mid
        else:
            # Fail — set low = mid to try LIGHTER (higher L) and
            # push further in the contrast-improving direction.
            low = mid

    r, g, b = hsl_to_rgb(h, s, best_l)
    return clamp_rgb(r, g, b)


# ── Colour manipulation ──────────────────────────────────────────────────


def boost(
    rgb: tuple[float, float, float],
    saturation_delta: float = 0.0,
    contrast_delta: float = 0.0,
) -> tuple[float, float, float]:
    """Increase saturation additively and stretch lightness contrast from 0.5."""
    h, s, l = rgb_to_hsl(rgb[0], rgb[1], rgb[2])
    if saturation_delta:
        s = max(0.0, min(1.0, s + saturation_delta))
    if contrast_delta:
        l = 0.5 + (l - 0.5) * (1.0 + contrast_delta)
        l = max(0.0, min(1.0, l))
    r, g, b = hsl_to_rgb(h, s, l)
    return clamp_rgb(r, g, b)


def blend_hex(fg_hex: str, bg_hex: str, alpha: float) -> str:
    """Standard alpha blend of two hex colours.  alpha=1 → full fg."""
    from terratheme.palette.color_utils import hex_to_rgb

    fr, fg, fb = hex_to_rgb(fg_hex)
    br, bg_c, bb = hex_to_rgb(bg_hex)
    r = int(alpha * fr + (1.0 - alpha) * br + 0.5)
    g = int(alpha * fg + (1.0 - alpha) * bg_c + 0.5)
    b = int(alpha * fb + (1.0 - alpha) * bb + 0.5)
    return rgb_hex(*clamp_rgb(float(r), float(g), float(b)))


def shift_to_hue(
    source_rgb: tuple[float, float, float],
    target_hue: float,
    shift_amount: float = 1.0,
) -> tuple[float, float, float]:
    """Take source's S/L, apply target hue, blend via hue_mix."""
    h, s, l = rgb_to_hsl(source_rgb[0], source_rgb[1], source_rgb[2])
    mixed = hue_mix(h, target_hue, shift_amount)
    r, g, b = hsl_to_rgb(mixed, s, l)
    return clamp_rgb(r, g, b)


def semantic_diff_fg(
    source_rgb: tuple[float, float, float],
    semantic_hue: float,
) -> tuple[float, float, float]:
    """Borrow S/L from a source colour, force hue to *semantic_hue* (0-1).

    Boosts saturation 1.5x (max 0.95), darkens to 35% minimum lightness.
    """
    h, s, l = rgb_to_hsl(source_rgb[0], source_rgb[1], source_rgb[2])
    s = min(s * 1.5, 0.95)
    l = max(l * 0.65, 0.35)
    r, g, b = hsl_to_rgb(semantic_hue * 360.0, s, l)
    return clamp_rgb(r, g, b)
