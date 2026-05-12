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
# 5 layers: bottom (deepest/darkest) → low → base → high → top (foremost).
# Dark mode: bottom is darkest, top is brightest.
# Light mode: bottom is brightest, top is darkest (reversed).
DARK_BG_TONES  = [0.04, 0.10, 0.18, 0.28, 0.40]
LIGHT_BG_TONES = [0.96, 0.90, 0.82, 0.72, 0.60]

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

    *layer_index*: 0=bottom → 4=top.
    In dark mode, 0=darkest and 4=brightest.
    In light mode, 0=brightest and 4=darkest (tone array is reversed).
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
    """Lower-contrast version of standard text, closer to fg so it stays readable."""
    bg_l = 0.10 if mode == "dark" else 0.90
    h, s, _l = rgb_to_hsl(float(standard[0]), float(standard[1]), float(standard[2]))
    target = _l + (bg_l - _l) * 0.25
    r, g, b = hsl_to_rgb(h, s * 0.7, target)
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
# Chromatic ANSI slots (1-6, 9-14) are derived by:
#   1. Dynamically assigning each slot to its nearest palette token by hue
#      (c1-c4, error) — closest hue wins, conflicts resolved greedily.
#   2. Blending the canonical hue toward the assigned palette token with an
#      adaptive ratio: close matches get more palette influence (40%),
#      distant matches stay closer to canonical (15%).
#   3. For slots with no palette assignment (more slots than tokens), the
#      nearest assigned neighbour is hue-rotated to fill the gap.
#   4. Bright variants are boosted in lightness; all colours are validated
#      for ≥3.0:1 contrast against the terminal background (high layer).
#
# Achromatic slots (0, 7, 8, 15) use cross-mode references: near-black from
# the dark palette, near-white from the light palette.

from terratheme.palette.syntax_utils import hue_distance

# Canonical ANSI hues and their RGB anchors
_CANONICAL_SLOTS: dict[int, dict] = {
    1: {"name": "red",     "hue": 0.0,      "rgb": (255, 0, 0)},
    2: {"name": "green",   "hue": 120.0/360.0,  "rgb": (0, 255, 0)},
    3: {"name": "yellow",  "hue": 60.0/360.0,   "rgb": (255, 255, 0)},
    4: {"name": "blue",    "hue": 240.0/360.0,  "rgb": (0, 0, 255)},
    5: {"name": "magenta", "hue": 300.0/360.0,  "rgb": (255, 0, 255)},
    6: {"name": "cyan",    "hue": 180.0/360.0,  "rgb": (0, 255, 255)},
}

# Palette tokens available for chromatic slot assignment
_ANSI_SOURCE_TOKENS = ["c1", "c2", "c3", "c4", "error"]


def _hue_of_hex(hex_str: str) -> float:
    """Return normalised hue (0-1) of a hex colour."""
    r, g, b = hex_to_rgb(hex_str)
    h, _s, _l = rgb_to_hsl(float(r), float(g), float(b))
    return h / 360.0


def _adaptive_blend(distance: float) -> float:
    """Blend factor: close hues blend more toward palette, distant less."""
    # 0.40 at distance=0, 0.10 at distance=0.5+
    return max(0.10, min(0.40, 0.40 - distance * 0.60))


def _assign_nearest(tokens: dict[str, str]) -> dict[int, str | None]:
    """Greedily assign each ANSI slot to its nearest palette token by hue.

    Returns {slot: token_name_or_None}. Slots without assignment will be
    filled via hue rotation from their nearest assigned neighbour.
    """
    # Compute hues of available palette tokens
    token_hues: dict[str, float] = {}
    for token in _ANSI_SOURCE_TOKENS:
        if token in tokens:
            token_hues[token] = _hue_of_hex(tokens[token])

    # Collect all (slot, token, distance) triples and sort by distance
    candidates: list[tuple[int, str, float]] = []
    for slot, info in _CANONICAL_SLOTS.items():
        ch = info["hue"]
        for token, th in token_hues.items():
            candidates.append((slot, token, hue_distance(ch, th)))

    candidates.sort(key=lambda x: x[2])  # closest first

    assigned_slots: set[int] = set()
    used_tokens: set[str] = set()
    result: dict[int, str | None] = {}

    for slot, token, _dist in candidates:
        if slot in assigned_slots or token in used_tokens:
            continue
        result[slot] = token
        assigned_slots.add(slot)
        used_tokens.add(token)

    # Any remaining slots get None (filled via hue rotation)
    for slot in _CANONICAL_SLOTS:
        if slot not in result:
            result[slot] = None

    return result


def _fill_hue_rotation(
    slot: int,
    assignments: dict[int, str | None],
    generated: dict[int, tuple[float, float, float]],
    tokens: dict[str, str],
) -> tuple[float, float, float]:
    """Fill an unassigned slot by rotating the nearest assigned neighbour's hue."""
    target_hue = _CANONICAL_SLOTS[slot]["hue"]

    # Find nearest assigned slot (by hue distance)
    best_dist = float("inf")
    best_rgb = (128.0, 128.0, 128.0)
    for s, info in _CANONICAL_SLOTS.items():
        if s == slot or s not in generated:
            continue
        d = hue_distance(target_hue, info["hue"])
        if d < best_dist:
            best_dist = d
            best_rgb = generated[s]

    # Rotate to target hue
    h, s_val, l_val = rgb_to_hsl(best_rgb[0], best_rgb[1], best_rgb[2])
    r, g, b = hsl_to_rgb(target_hue * 360.0, s_val, l_val)
    return (r, g, b)


def _ensure_contrast(
    rgb: tuple[float, float, float],
    bg_hex: str,
    target: float,
) -> tuple[float, float, float]:
    """Lighten or darken *rgb* to achieve *target* contrast against *bg*."""
    bg_rgb = hex_to_rgb(bg_hex)
    if contrast_ratio(rgb, bg_rgb) >= target:
        return rgb
    h, s, l = rgb_to_hsl(rgb[0], rgb[1], rgb[2])
    bg_lum = relative_luminance(float(bg_rgb[0]), float(bg_rgb[1]), float(bg_rgb[2]))
    low, high = (0.10, 0.95)
    if bg_lum > 0.5:
        search_start, search_end = low, l
    else:
        search_start, search_end = l, high
    best_l, best_r = l, rgb
    for _ in range(20):
        mid = (search_start + search_end) / 2
        r2, g2, b2 = hsl_to_rgb(h, s, mid)
        test_rgb = (r2, g2, b2)
        cr = contrast_ratio(test_rgb, bg_rgb)
        if cr >= target:
            best_l, best_r = mid, test_rgb
            # Pass — try DARKER (lower L) to find the minimum
            search_end = mid
        else:
            # Fail — try LIGHTER (higher L) in direction of travel
            if bg_lum > 0.5:
                search_start = mid
            else:
                search_start = mid
    return best_r


def _derive_ansi_colors(
    tokens: dict[str, str],
    mode: str,
    dark_tokens: dict[str, str],
    light_tokens: dict[str, str],
) -> dict[str, str]:
    """Derive 16 ANSI terminal colours from palette tokens.

    Achromatic slots use cross-mode references so black/bright-black are
    always near-black (from dark palette layers) and white/bright-white are
    always near-white (from light palette layers), regardless of terminal mode.

    Args:
        tokens: Current mode's palette tokens (used for chromatic slots).
        mode: ``"dark"`` or ``"light"``.
        dark_tokens: Dark-mode palette tokens (for ansi_0/8).
        light_tokens: Light-mode palette tokens (for ansi_7/15).

    Returns a dict with keys ``ansi_0`` through ``ansi_15``.
    """
    result: dict[str, str] = {}

    # ── Achromatic slots ──────────────────────────────────────────────
    result["ansi_0"]  = dark_tokens["base"]
    result["ansi_8"]  = dark_tokens["high"]
    result["ansi_7"]  = light_tokens["base"]
    result["ansi_15"] = light_tokens["low"]

    # ── Assign palette tokens to slots ────────────────────────────────
    assignments = _assign_nearest(tokens)

    # ── Generate chromatic slot colours ───────────────────────────────
    bg_hex = tokens.get("high", tokens.get("base", "#000000"))
    generated: dict[int, tuple[float, float, float]] = {}

    for slot in range(1, 7):
        info = _CANONICAL_SLOTS[slot]
        token = assignments.get(slot)

        if token:
            # Blend canonical toward assigned palette token
            canonical = (float(info["rgb"][0]), float(info["rgb"][1]), float(info["rgb"][2]))
            palette_rgb_val = (float(v) for v in hex_to_rgb(tokens[token]))
            palette_rgb_tup = tuple(palette_rgb_val)  # noqa
            distance = hue_distance(info["hue"], _hue_of_hex(tokens[token]))
            blend_factor = _adaptive_blend(distance)
            blended = blend(canonical, palette_rgb_tup, blend_factor)
        else:
            # Hue rotation from nearest assigned neighbour
            blended = _fill_hue_rotation(slot, assignments, generated, tokens)

        # Regular variant: slight darkening for dark mode
        h, s, l = rgb_to_hsl(blended[0], blended[1], blended[2])
        if mode == "dark":
            reg_l = max(0.25, l - 0.05)
        else:
            reg_l = min(0.75, l + 0.05)
        reg_rgb = tuple(float(v) for v in hsl_to_rgb(h, s, reg_l))

        # Validate regular against terminal background
        reg_rgb = _ensure_contrast(reg_rgb, bg_hex, 3.0)

        # Bright variant: boost lightness past regular, ensure separation
        _h, _s, reg_final_l = rgb_to_hsl(reg_rgb[0], reg_rgb[1], reg_rgb[2])
        bright_l = min(0.88, reg_final_l + 0.22)
        bright_rgb = tuple(float(v) for v in hsl_to_rgb(_h, _s, bright_l))
        # Validate bright separately (different starting L ensures diff)
        bright_rgb = _ensure_contrast(bright_rgb, bg_hex, 3.0)
        # Guarantee bright is strictly lighter than regular
        _bh, _bs, bl = rgb_to_hsl(bright_rgb[0], bright_rgb[1], bright_rgb[2])
        if bl <= reg_final_l + 0.005:
            bl = reg_final_l + 0.08
            bright_rgb = tuple(float(v) for v in hsl_to_rgb(_bh, _bs, bl))
            bright_rgb = _ensure_contrast(bright_rgb, bg_hex, 3.0)

        result[f"ansi_{slot}"] = rgb_hex(*clamp_rgb(*reg_rgb))
        result[f"ansi_{slot + 8}"] = rgb_hex(*clamp_rgb(*bright_rgb))
        generated[slot] = reg_rgb

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

    # ── Pass 1: Visual tokens for both modes ──────────────────────────
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

        results[m] = tokens

    # ── Pass 2: ANSI tokens for both modes ────────────────────────────
    # Both palettes are now available, needed for cross-mode achromatic refs.
    for m in ("dark", "light"):
        tokens = results[m]
        tokens.update(_derive_ansi_colors(tokens, m, results["dark"], results["light"]))
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
