"""Full palette derivation from 5 source colours.

Takes extracted source colours (c0–c4) and produces the complete
20-token palette for a given mode (light or dark), plus a contrast log.
"""

from __future__ import annotations

from terratheme.palette.color_utils import (
    adjust_tone,
    blend,
    clamp_rgb,
    contrast_ratio,
    hsl_to_rgb,
    reduce_chroma,
    relative_luminance,
    rgb_hex,
    rgb_to_hsl,
)

# ── Background target tones ─────────────────────────────────────────────
# layer 0=back, 1=base, 2=front, 3=top
DARK_BG_TONES = [0.05, 0.08, 0.11, 0.15]
LIGHT_BG_TONES = [0.85, 0.90, 0.94, 0.97]

# Source colour → layer mapping
BG_SOURCE_LAYERS = [
    (3, 0),   # back  ← c3, layer 0
    (0, 1),   # base  ← c0, layer 1
    (1, 2),   # front ← c1, layer 2
    (2, 3),   # top   ← c2, layer 3
]

BG_NAMES = ["back", "base", "front", "top"]


# ── Derivation helpers ──────────────────────────────────────────────────


def _detect_mode(sources: list[tuple[int, int, int]]) -> str:
    """Auto-detect mode from average source colour luminance.

    Returns ``"dark"`` if average luminance < 0.5, ``"light"`` otherwise.
    """
    total_l = 0.0
    for r, g, b in sources:
        _h, _s, l = rgb_to_hsl(float(r), float(g), float(b))
        total_l += l
    return "dark" if (total_l / len(sources)) < 0.5 else "light"


def _derive_background(
    source: tuple[int, int, int],
    mode: str,
    layer_index: int,
) -> tuple[int, int, int]:
    """Produce a background tone from a source colour.

    *layer_index*: 0=back → 3=top (darkest → lightest).
    """
    tones = DARK_BG_TONES if mode == "dark" else LIGHT_BG_TONES
    target = tones[layer_index]
    r, g, b = adjust_tone(float(source[0]), float(source[1]), float(source[2]), target)
    r, g, b = reduce_chroma(r, g, b, factor=0.55)
    return clamp_rgb(r, g, b)


def _derive_standard_text(mode: str, tint_from: tuple[int, int, int]) -> tuple[int, int, int]:
    """Near-white (dark mode) or near-black (light mode) with slight tint."""
    target_l = 0.95 if mode == "dark" else 0.05
    # Tint very slightly by blending in a tiny amount of the tint source
    base = (255, 255, 255) if mode == "dark" else (0, 0, 0)
    r, g, b = adjust_tone(float(base[0]), float(base[1]), float(base[2]), target_l)
    # Blend 5% toward the tint source for a subtle palette tie-in
    r, g, b = blend((r, g, b), (float(tint_from[0]), float(tint_from[1]), float(tint_from[2])), 0.05)
    return clamp_rgb(r, g, b)


def _derive_muted_text(
    standard: tuple[int, int, int],
    mode: str,
) -> tuple[int, int, int]:
    """Lower-contrast version of standard text.

    Shift tone 40% toward the mode's average background luminance.
    """
    bg_l = 0.10 if mode == "dark" else 0.90
    h, s, _l = rgb_to_hsl(float(standard[0]), float(standard[1]), float(standard[2]))
    target = _l + (bg_l - _l) * 0.4
    r, g, b = hsl_to_rgb(h, s * 0.5, target)
    return clamp_rgb(r, g, b)


def _derive_on_color(
    base_color: tuple[int, int, int],
    accent_source: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Adjust an accent source colour for readability on *base_color*.

    Uses WCAG relative luminance to determine whether the on-color should
    be light or dark, then shifts the accent's tone for contrast and
    slightly boosts chroma for visual interest.
    """
    base_lum = relative_luminance(*base_color)
    src_h, src_s, _src_l = rgb_to_hsl(
        float(accent_source[0]), float(accent_source[1]), float(accent_source[2]),
    )

    # The equal-contrast point (where light and dark text give the same
    # WCAG ratio against the base) is at base luminance ~0.20, but since
    # HSL→WCAG luminance mapping is hue-dependent, a small buffer at 0.21
    # prevents flip-flopping for borderline mid-tone bases.
    if base_lum < 0.21:
        target_tone = 0.85  # light on dark
    else:
        target_tone = 0.15  # dark on light

    # Boost chroma slightly (cap at 1.0)
    chroma = min(src_s * 1.2, 1.0)
    r, g, b = hsl_to_rgb(src_h, chroma, target_tone)
    return clamp_rgb(r, g, b)


def _derive_outline(
    c0: tuple[int, int, int],
    mode: str,
) -> tuple[int, int, int]:
    """Derive outline from c0 by shifting in the opposite direction of *mode*."""
    target_l = 0.40 if mode == "dark" else 0.60
    r, g, b = adjust_tone(float(c0[0]), float(c0[1]), float(c0[2]), target_l)
    r, g, b = reduce_chroma(r, g, b, factor=0.40)
    return clamp_rgb(r, g, b)


def _derive_error(c0: tuple[int, int, int]) -> tuple[int, int, int]:
    """Start from red, blend slightly toward c0."""
    red = (255.0, 0.0, 0.0)
    r, g, b = blend(red, (float(c0[0]), float(c0[1]), float(c0[2])), 0.2)
    return clamp_rgb(r, g, b)


def _derive_on_error(
    error: tuple[int, int, int],
    c1: tuple[int, int, int],
    mode: str,
) -> tuple[int, int, int]:
    """Readable colour on error, blended slightly toward c1.

    Error is always a dark red regardless of mode, so on_error always
    targets a light tone for readability.
    """
    r, g, b = adjust_tone(255.0, 255.0, 255.0, 0.90)
    r, g, b = blend((r, g, b), (float(c1[0]), float(c1[1]), float(c1[2])), 0.15)
    return clamp_rgb(r, g, b)


# ── Public API ──────────────────────────────────────────────────────────


PaletteDict = dict[str, str | dict[str, str]]


def derive_palette(
    sources: list[tuple[int, int, int]],
    mode: str | None = None,
) -> PaletteDict:
    """Produce the full 20-token palette from 5 source colours.

    Args:
        sources: 5 ``(R, G, B)`` tuples, c0–c4 in order of prevalence.
        mode: ``"dark"``, ``"light"``, or ``None`` for auto-detect.

    Returns:
        A dict with ``"version"``, ``"mode"``, ``"light"``, ``"dark"``,
        and ``"contrast_log"`` keys.  The ``"light"`` and ``"dark"`` values
        are dicts mapping token names to hex colour strings.

        The logical structure is::

            {
                "version": 2,
                "mode": "dark",
                "light": { … 20 tokens … },
                "dark":  { … 20 tokens … },
                "contrast_log": { … },
            }
    """
    if mode is None:
        mode = _detect_mode(sources)

    c = sources  # c0–c4
    result: dict[str, dict[str, str]] = {}

    for m in ("dark", "light"):
        tokens: dict[str, str] = {}

        # ── Backgrounds ─────────────────────────────────────────────
        for src_idx, layer_idx in BG_SOURCE_LAYERS:
            name = BG_NAMES[layer_idx]
            rgb = _derive_background(c[src_idx], m, layer_idx)
            tokens[name] = rgb_hex(*rgb)

        # ── Text ────────────────────────────────────────────────────
        std = _derive_standard_text(m, c[0])
        tokens["standard"] = rgb_hex(*std)
        tokens["muted"] = rgb_hex(*_derive_muted_text(std, m))

        # ── Semantic colours (c0–c4, on_c0–on_c4) ──────────────────
        on_chain = [1, 2, 3, 4, 0]  # on_cN borrows from c(N+1), c4 wraps to c0
        for i in range(5):
            tokens[f"c{i}"] = rgb_hex(*c[i])
            on_rgb = _derive_on_color(c[i], c[on_chain[i]])
            tokens[f"on_c{i}"] = rgb_hex(*on_rgb)

        # ── Error ───────────────────────────────────────────────────
        err = _derive_error(c[0])
        tokens["error"] = rgb_hex(*err)
        tokens["on_error"] = rgb_hex(*_derive_on_error(err, c[1], m))

        # ── Outline ─────────────────────────────────────────────────
        tokens["outline"] = rgb_hex(*_derive_outline(c[0], m))

        result[m] = tokens

    # ── Contrast log ─────────────────────────────────────────────────
    contrast_log: dict[str, str] = {}
    for m in ("dark", "light"):
        t = result[m]
        pairs: list[tuple[str, str]] = [
            ("on_c0", "c0"),
            ("on_c1", "c1"),
            ("on_c2", "c2"),
            ("on_c3", "c3"),
            ("on_c4", "c4"),
            ("on_error", "error"),
        ]
        for on_name, base_name in pairs:
            on_hex = t[on_name]
            base_hex = t[base_name]
            on_rgb = (int(on_hex[1:3], 16), int(on_hex[3:5], 16), int(on_hex[5:7], 16))
            base_rgb = (int(base_hex[1:3], 16), int(base_hex[3:5], 16), int(base_hex[5:7], 16))
            ratio = contrast_ratio(on_rgb, base_rgb)
            key = f"{on_name}_on_{base_name} ({m})"
            contrast_log[key] = f"{ratio:.1f}:1"

    return {
        "version": 2,
        "mode": mode,
        "light": result["light"],
        "dark": result["dark"],
        "contrast_log": contrast_log,
    }
