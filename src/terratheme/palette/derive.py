"""Full palette derivation from 5 source colours.

Takes extracted source colours (c0–c4) and produces the complete
20-token palette for a given mode (light or dark), plus a contrast log.

Semantic model
--------------
- c0 is always the **background source** (darkest in dark mode, lightest in light).
- c1–c4 are **accents**; c4 gives the highest contrast against the mode's
  background (lightest in dark mode, darkest in light mode).
- In dark mode the sources are used as-is (dark → light).
- In light mode the source list is reversed so that c0 is the lightest
  (colours that pop on light backgrounds are dark = higher indices).
"""

from __future__ import annotations

from terratheme.palette.color_utils import (
    adjust_tone,
    blend,
    clamp_rgb,
    contrast_ratio,
    hex_to_rgb,
    hsl_to_rgb,
    reduce_chroma,
    relative_luminance,
    rgb_hex,
    rgb_to_hsl,
)

# ── Background target tones ─────────────────────────────────────────────
# 5 layers: bottom (deepest/darkest) → low → base → high → top (foremost)
DARK_BG_TONES  = [0.04, 0.10, 0.18, 0.28, 0.40]
LIGHT_BG_TONES = [0.60, 0.72, 0.82, 0.90, 0.96]

BG_NAMES = ["bottom", "low", "base", "high", "top"]


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

    *layer_index*: 0=bottom → 4=top (darkest → lightest).
    All backgrounds derive from the same source (c0) for a cohesive look.
    """
    tones = DARK_BG_TONES if mode == "dark" else LIGHT_BG_TONES
    target = tones[layer_index]
    r, g, b = adjust_tone(float(source[0]), float(source[1]), float(source[2]), target)
    r, g, b = reduce_chroma(r, g, b, factor=0.75)
    return clamp_rgb(r, g, b)


def _derive_standard_text(mode: str, tint_from: tuple[int, int, int]) -> tuple[int, int, int]:
    """Near-white (dark mode) or near-black (light mode) with slight tint."""
    target_l = 0.95 if mode == "dark" else 0.05
    base = (255, 255, 255) if mode == "dark" else (0, 0, 0)
    r, g, b = adjust_tone(float(base[0]), float(base[1]), float(base[2]), target_l)
    r, g, b = blend((r, g, b), (float(tint_from[0]), float(tint_from[1]), float(tint_from[2])), 0.05)
    return clamp_rgb(r, g, b)


def _derive_muted_text(
    standard: tuple[int, int, int],
    mode: str,
) -> tuple[int, int, int]:
    """Lower-contrast version of standard text."""
    bg_l = 0.10 if mode == "dark" else 0.90
    h, s, _l = rgb_to_hsl(float(standard[0]), float(standard[1]), float(standard[2]))
    target = _l + (bg_l - _l) * 0.4
    r, g, b = hsl_to_rgb(h, s * 0.5, target)
    return clamp_rgb(r, g, b)


def _derive_on_color(
    base_color: tuple[int, int, int],
    accent_source: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Readable on-colour with saturation preserved as much as possible.

    Picks the best tone direction (light or dark) for contrast, then tries
    progressively reduced chroma levels.  The most colourful candidate that
    still passes **3.0:1** is chosen, so on-colours keep a tint of their
    accent source instead of always collapsing to grey.
    """
    base_lum = relative_luminance(*base_color)
    src_h, src_s, _src_l = rgb_to_hsl(
        float(accent_source[0]), float(accent_source[1]), float(accent_source[2]),
    )
    chroma = min(src_s * 1.2, 1.0)

    if base_lum < 0.21:
        tones = (0.85, 0.15)
    else:
        tones = (0.15, 0.85)

    best = None
    best_score = -1.0

    # Try multiple chroma levels — colourful first, grey last
    for tone in tones:
        for ch in (chroma, chroma * 0.7, chroma * 0.4, 0.0):
            r, g, b = hsl_to_rgb(src_h, ch, tone)
            result = clamp_rgb(r, g, b)
            on_lum = relative_luminance(*result)
            lighter = max(base_lum, on_lum)
            darker = min(base_lum, on_lum)
            ratio = (lighter + 0.05) / (darker + 0.05)

            # Score: contrast first, chroma bonus for colourfulness
            score = ratio + ch * 0.1
            if score > best_score:
                best_score = score
                best = result

    return best


def _shift_tone(
    rgb: tuple[float, float, float],
    delta: float,
) -> tuple[int, int, int]:
    """Shift a colour's HSL lightness by ``delta`` (0-1 range), clamped safely."""
    h, s, l = rgb_to_hsl(rgb[0], rgb[1], rgb[2])
    new_l = max(0.02, min(0.98, l + delta))
    r, g, b = hsl_to_rgb(h, s, new_l)
    return clamp_rgb(r, g, b)


def _derive_outline(
    c0: tuple[int, int, int],
    mode: str,
) -> tuple[int, int, int]:
    """Derive outline from the background source colour."""
    target_l = 0.40 if mode == "dark" else 0.60
    r, g, b = adjust_tone(float(c0[0]), float(c0[1]), float(c0[2]), target_l)
    r, g, b = reduce_chroma(r, g, b, factor=0.40)
    return clamp_rgb(r, g, b)


def _derive_error(c0: tuple[int, int, int]) -> tuple[int, int, int]:
    """Start from red, blend slightly toward the background source."""
    red = (255.0, 0.0, 0.0)
    r, g, b = blend(red, (float(c0[0]), float(c0[1]), float(c0[2])), 0.2)
    return clamp_rgb(r, g, b)


def _derive_on_error(
    error: tuple[int, int, int],
    c1: tuple[int, int, int],
    mode: str,
) -> tuple[int, int, int]:
    """Readable colour on error, blended slightly toward c1."""
    r, g, b = adjust_tone(255.0, 255.0, 255.0, 0.90)
    for blend_factor in (0.15, 0.10, 0.05, 0.0):
        candidate = blend((r, g, b), (float(c1[0]), float(c1[1]), float(c1[2])), blend_factor)
        candidate_rgb = clamp_rgb(*candidate)
        cr = contrast_ratio(candidate_rgb, error)
        if cr >= 3.0:
            return candidate_rgb
    return clamp_rgb(255, 255, 255)


# ── ANSI terminal colour derivation ─────────────────────────────────────
#
# Each chromatic ANSI slot (1-6, 9-14) starts from a canonical hue anchor,
# blends it 60/40 toward a designated palette token, then applies a
# luminance shift to separate the regular vs bright variant.
# Achromatic slots (0, 7, 8, 15) map directly to background/text tokens.
#
# The blend targets and tone shifts match the values used in the matugen
# foot.ini / ghostty templates (your dotfiles), so the result should be
# comparable.  Values are tunable — update the dicts below to taste.

_CANONICAL_ANCHORS: dict[int, tuple[int, int, int]] = {
    1: (255, 0, 0),      # red
    2: (0, 255, 0),      # green
    3: (255, 255, 0),    # yellow
    4: (0, 0, 255),      # blue
    5: (255, 0, 255),    # magenta
    6: (0, 255, 255),    # cyan
}

# Which palette token each chromatic slot blends toward.
_BLEND_TARGETS: dict[int, str] = {
    1: "error",   # red → error (already red-anchored)
    2: "c4",      # green → loudest accent
    3: "c3",      # yellow → 2nd loudest accent
    4: "c2",      # blue → cooler accent
    5: "c4",      # magenta → loudest accent
    6: "c1",      # cyan → supporting accent
}

# Tone shifts per slot: (regular_delta, bright_delta) for (dark, light).
# These match the matugen foot.ini template values exactly.
_TONE_SHIFTS: dict[int, tuple[tuple[float, float], tuple[float, float]]] = {
    1: ((-0.08, 0.10), (0.06, 0.16)),
    2: ((-0.08, 0.10), (-0.25, -0.10)),
    3: ((-0.08, 0.10), (-0.18, -0.10)),
    4: ((0.02, 0.18), (0.06, 0.20)),
    5: ((-0.08, 0.10), (-0.18, -0.10)),
    6: ((-0.08, 0.10), (-0.18, -0.10)),
}


def _derive_ansi_colors(
    tokens: dict[str, str],
    mode: str,
    dark_tokens: dict[str, str] | None = None,
) -> dict[str, str]:
    """Derive 16 ANSI terminal colours from palette tokens.

    Args:
        tokens: Current mode's palette tokens.
        mode: ``"dark"`` or ``"light"``.
        dark_tokens: Dark-mode palette tokens (needed for achromatic slots
            that should always be dark — ANSI 0/8).  Passed explicitly so
            light mode doesn't use light backgrounds for "black".

    Returns a dict with keys ``ansi_0`` through ``ansi_15``.
    """
    result: dict[str, str] = {}

    # Achromatic slots
    # ANSI black (0/8) and white (7/15) always use dark-mode values
    # regardless of terminal mode, matching the matugen template approach.
    text_src = dark_tokens if dark_tokens is not None else tokens
    result["ansi_0"] = text_src["bottom"]
    result["ansi_8"] = text_src["base"]
    result["ansi_7"] = text_src["muted"]
    result["ansi_15"] = text_src["standard"]

    if mode == "dark":
        shifts = {s: v[0] for s, v in _TONE_SHIFTS.items()}
    else:
        shifts = {s: v[1] for s, v in _TONE_SHIFTS.items()}

    # Pre-parse blend-target palette colours to RGB
    palette_rgb: dict[str, tuple[int, int, int]] = {}
    for target_name in set(_BLEND_TARGETS.values()):
        palette_rgb[target_name] = hex_to_rgb(tokens[target_name])

    for slot in range(1, 7):
        canonical = _CANONICAL_ANCHORS[slot]
        target_name = _BLEND_TARGETS[slot]
        target = palette_rgb[target_name]
        reg_delta, bright_delta = shifts[slot]

        # Blend: 60% canonical, 40% palette
        blended = blend(
            (float(canonical[0]), float(canonical[1]), float(canonical[2])),
            (float(target[0]), float(target[1]), float(target[2])),
            0.4,
        )

        # Regular
        reg = _shift_tone(blended, reg_delta)
        result[f"ansi_{slot}"] = rgb_hex(*reg)

        # Bright
        bright = _shift_tone(blended, bright_delta)
        result[f"ansi_{slot + 8}"] = rgb_hex(*bright)

    return result


# ── Public API ──────────────────────────────────────────────────────────


PaletteDict = dict[str, str | dict[str, str]]


def derive_palette(
    sources: list[tuple[int, int, int]],
    mode: str | None = None,
) -> PaletteDict:
    """Produce the full 20-token palette from 5 source colours.

    Args:
        sources: 5 ``(R, G, B)`` tuples, sorted dark → light.
        mode: ``"dark"``, ``"light"``, or ``None`` for auto-detect.

    Returns:
        A dict with ``"version"``, ``"mode"``, ``"light"``, ``"dark"``,
        and ``"contrast_log"`` keys.

    Token semantics
    ---------------
    - **c0** – background source (darkest in dark mode, lightest in light).
    - **c1–c4** – accents where higher index = more visual pop against the
      mode's background.
    - **on_c0–on_c4** – readable foreground colours for each accent.
    - **bottom/low/base/high/top** – cohesive single-hue background layers.
    """
    if mode is None:
        mode = _detect_mode(sources)

    results: dict[str, dict[str, str]] = {}

    for m in ("dark", "light"):
        tokens: dict[str, str] = {}

        # Reverse sources for light mode so c0 is always background source
        # (darkest in dark mode, lightest in light mode).
        if m == "dark":
            working = list(sources)      # c0=darkest, c4=lightest
        else:
            working = list(reversed(sources))  # c0=lightest, c4=darkest

        # ── Backgrounds (all from working[0]) ────────────────────────
        bg_source = working[0]
        for i, name in enumerate(BG_NAMES):
            rgb = _derive_background(bg_source, m, i)
            tokens[name] = rgb_hex(*rgb)

        # ── Text ────────────────────────────────────────────────────
        std = _derive_standard_text(m, working[0])
        tokens["standard"] = rgb_hex(*std)
        tokens["muted"] = rgb_hex(*_derive_muted_text(std, m))

        # ── Semantic colours (c0–c4, on_c0–on_c4) ──────────────────
        on_chain = [1, 2, 3, 4, 0]  # on_cN borrows from c(N+1), c4 wraps to c0
        for i in range(5):
            tokens[f"c{i}"] = rgb_hex(*working[i])
            on_rgb = _derive_on_color(working[i], working[on_chain[i]])
            tokens[f"on_c{i}"] = rgb_hex(*on_rgb)

        # ── Error ───────────────────────────────────────────────────
        err = _derive_error(working[0])
        tokens["error"] = rgb_hex(*err)
        tokens["on_error"] = rgb_hex(*_derive_on_error(err, working[1], m))

        # ── Outline ─────────────────────────────────────────────────
        tokens["outline"] = rgb_hex(*_derive_outline(working[0], m))

        # ── ANSI terminal colours ───────────────────────────────────
        # For dark mode, dark_tokens is the current tokens (self).
        # For light mode, dark_tokens is the already-computed dark palette.
        dark_tokens = tokens if m == "dark" else results["dark"]
        tokens.update(_derive_ansi_colors(tokens, m, dark_tokens))

        results[m] = tokens

    # ── Contrast log ─────────────────────────────────────────────────
    contrast_log: dict[str, str] = {}
    for m in ("dark", "light"):
        t = results[m]
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
        "light": results["light"],
        "dark": results["dark"],
        "contrast_log": contrast_log,
    }
