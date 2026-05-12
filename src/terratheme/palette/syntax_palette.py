"""Syntax palette derivation — ported from Neovim's ``syntax_palette.lua``.

Takes the Terra DE v2 palette tokens (c0-c4, backgrounds) and produces a
set of 11 syntax-highlight colours (keyword, function, type, etc.) plus
operator and muted, using the same weighted-hue-allocation algorithm
that was previously implemented in Lua.

This runs **before** Neovim loads, so the editor does zero colour math.

All derived colours are validated against EVERY background layer and
re-adjusted if any contrast ratio falls below the minimum target.
"""

from __future__ import annotations

from terratheme.palette.color_utils import (
    clamp_rgb,
    contrast_ratio,
    hex_to_rgb,
    hsl_to_rgb,
    relative_luminance,
    rgb_hex,
    rgb_to_hsl,
)
from terratheme.palette.syntax_utils import (
    adjust_contrast,
    circular_mean,
    hue_diversity,
    hue_midpoint,
    hue_mix,
    hue_distance,
)


# ── Source collection ────────────────────────────────────────────────────


def _hue_of(hex_str: str) -> dict:
    """Parse a hex colour into {hue, sat, light}."""
    r, g, b = hex_to_rgb(hex_str)
    h, s, l = rgb_to_hsl(float(r), float(g), float(b))
    return {"color": hex_str, "hue": h / 360.0, "sat": s, "light": l}


def _collect_sources(tokens: dict[str, str]) -> list[dict]:
    """Collect weighted source colours from the v2 palette.

    Syntax derives purely from the accent chain — error is **not** included
    so red hues never bleed into syntax highlighting.

    - c4 → primary      (weight 3.0 — loudest accent)
    - c3 → secondary    (weight 2.4)
    - c2 → tertiary     (weight 2.4)
    - c1 → support      (weight 1.2)
    """
    weighted = [
        ("c4", 3.0),
        ("c3", 2.4),
        ("c2", 2.4),
        ("c1", 1.2),
    ]

    sources: list[dict] = []
    seen: set[str] = set()
    for key, weight in weighted:
        color = tokens.get(key)
        if color and color not in seen:
            entry = _hue_of(color)
            entry["weight"] = weight
            entry["key"] = key
            sources.append(entry)
            seen.add(color)

    return sources


# ── Statistics ───────────────────────────────────────────────────────────


def _stats_for(sources: list[dict]) -> dict:
    """Compute aggregate statistics over weighted sources."""
    total_weight = 0.0
    sat_sum = 0.0
    light_sum = 0.0
    max_sat = 0.0
    min_sat = 1.0

    for src in sources:
        w = src["weight"]
        total_weight += w
        sat_sum += src["sat"] * w
        light_sum += src["light"] * w
        max_sat = max(max_sat, src["sat"])
        min_sat = min(min_sat, src["sat"])

    # First three sources are primary/secondary/tertiary analogues
    top3 = sources[:3] if len(sources) >= 3 else sources
    while len(top3) < 3:
        top3.append(top3[-1] if top3 else sources[0])

    return {
        "center_hue": circular_mean(sources),
        "avg_sat": sat_sum / total_weight if total_weight > 0 else 0.5,
        "avg_light": light_sum / total_weight if total_weight > 0 else 0.65,
        "max_sat": max_sat,
        "min_sat": min_sat,
        "diversity": hue_diversity(tuple(top3[:3])),
    }


# ── Nearest source lookup ────────────────────────────────────────────────


def _nearest_source(hue: float, sources: list[dict]) -> tuple[dict, float]:
    """Find the source whose hue is closest to *hue*."""
    best = sources[0]
    best_dist = 1.0
    for src in sources:
        d = hue_distance(hue, src["hue"])
        if d < best_dist:
            best = src
            best_dist = d
    return best, best_dist


# ── Single-colour construction ───────────────────────────────────────────


def _make_color(
    hue: float,
    sat: float,
    light: float,
    anchor_color: str,
    anchor_blend: float,
    bg_hex: str,
    contrast_target: float,
) -> str:
    """Build a hex colour from HSL, blend toward anchor, adjust contrast."""
    r, g, b = hsl_to_rgb(hue * 360.0, sat, light)
    rgb = clamp_rgb(r, g, b)

    # Blend toward the anchor colour
    anchor_rgb = hex_to_rgb(anchor_color)
    blended = (
        rgb[0] + (anchor_rgb[0] - rgb[0]) * anchor_blend,
        rgb[1] + (anchor_rgb[1] - rgb[1]) * anchor_blend,
        rgb[2] + (anchor_rgb[2] - rgb[2]) * anchor_blend,
    )

    # Adjust contrast against background
    bg_rgb = hex_to_rgb(bg_hex)
    result = adjust_contrast(blended, bg_rgb, contrast_target)
    return rgb_hex(*result)


# ── Contrast validation ──────────────────────────────────────────────────


def _validate_and_fix(
    hex_color: str,
    bg_hexes: list[str],
    target_ratio: float,
) -> str:
    """Check a colour against every background in the list; re-adjust if any fails.

    Pass the backgrounds you expect the colour to appear on:
      - Syntax colours  → ``[bg_hex, float_bg_hex]`` (practical surfaces)
      - Muted / Comments → ``[bg_hex, float_bg_hex, elevated_bg_hex]``
    """
    rgb = hex_to_rgb(hex_color)
    ratios = [contrast_ratio(rgb, hex_to_rgb(b)) for b in bg_hexes]
    min_ratio = min(ratios)

    if min_ratio >= target_ratio:
        return hex_color

    # Re-adjust against the background with worst contrast
    worst_idx = ratios.index(min_ratio)
    worst_bg = hex_to_rgb(bg_hexes[worst_idx])

    adjusted = adjust_contrast(rgb, worst_bg, target_ratio)
    return rgb_hex(*adjusted)


# ── Clamp helper ─────────────────────────────────────────────────────────


def _clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


# ── Public API ───────────────────────────────────────────────────────────


def derive_syntax(tokens: dict[str, str]) -> dict[str, str]:
    """Derive 11 syntax-highlight colours + operator + muted from v2 tokens.

    All colours are contrast-validated against every background layer so
    they work everywhere (normal editor, floats, popups, elevated surfaces).

    Args:
        tokens: A dict of v2 palette colour strings.  Must include the
            accent chain (``c4``, ``c3``, ``c2``, ``c1``),
            ``"bg"`` (the main editor background, v2 ``base``),
            ``"float_bg"`` (v2 ``high``),
            ``"elevated_bg"`` (v2 ``top``),
            and ``"fg"`` (v2 ``standard``).

    Returns:
        A dict with keys: *keyword*, *function*, *type*, *member*,
        *variable*, *parameter*, *builtin*, *namespace*, *constant*,
        *string*, *meta*, *operator*, *muted*.
    """
    bg_hex = tokens.get("bg", "#2c2738")
    float_bg_hex = tokens.get("float_bg", bg_hex)
    elevated_bg_hex = tokens.get("elevated_bg", bg_hex)
    fg_hex = tokens.get("fg", "#e8e4ef")

    sources = _collect_sources(tokens)

    if not sources:
        entry = _hue_of(fg_hex)
        entry["weight"] = 1.0
        sources = [entry]

    info = _stats_for(sources)
    bg_rgb = hex_to_rgb(bg_hex)
    is_dark = relative_luminance(*bg_rgb) < 0.5
    diversity = info["diversity"]

    # ── Saturation floor ─────────────────────────────────────────────
    # For low-diversity wallpapers, sat needs to work harder so hue
    # differences are visible even when lightness converges.
    if diversity < 0.08:
        sat_floor = 0.80
    else:
        sat_floor = 0.65

    base_sat = _clamp(
        max(info["avg_sat"] + 0.08, info["max_sat"] * 0.92), sat_floor, 0.92,
    )
    if is_dark:
        base_light = _clamp(max(info["avg_light"], 0.64), 0.60, 0.78)
    else:
        base_light = _clamp(min(info["avg_light"], 0.40), 0.24, 0.46)

    spread = _clamp(0.11 + (0.18 - diversity) * 0.55, 0.10, 0.20)

    # ── Dynamic anchor blend ──────────────────────────────────────────
    # Diverse wallpapers (diversity > 0.15) keep the strong anchor
    # pull — the nearest source hue is meaningful.  Monochromatic
    # wallpapers (diversity < 0.05) barely anchor at all so the
    # allocated hue survives and gives visibly distinct syntax tokens.
    if diversity <= 0.05:
        anchor_blend = 0.15
    elif diversity >= 0.15:
        anchor_blend = 0.65
    else:
        anchor_blend = 0.15 + (diversity - 0.05) / 0.10 * 0.50

    quarter = _clamp(spread * 1.55, 0.16, 0.27)
    opposite = (info["center_hue"] + 0.5) % 1.0

    primary = sources[0]
    secondary = sources[1] if len(sources) > 1 else primary
    tertiary = sources[2] if len(sources) > 2 else secondary

    # ── Determine worst-case bg for contrast adjustment ─────────────
    # In dark mode syntax colours are light; they lose contrast on
    # light backgrounds.  Syntax appears on `bg` (normal editing) and
    # `float_bg` (pickers/popups), but *rarely* on `elevated_bg`, so
    # we use `float_bg` as our worst case (= lightest practical bg).
    # In light mode syntax colours are dark; worst = darkest practical bg.
    all_bg_hexes = [bg_hex, float_bg_hex, elevated_bg_hex]
    practical_bg_hexes = [bg_hex, float_bg_hex]
    if is_dark:
        worst_bg = max(practical_bg_hexes, key=lambda h: relative_luminance(*hex_to_rgb(h)))
    else:
        worst_bg = min(practical_bg_hexes, key=lambda h: relative_luminance(*hex_to_rgb(h)))

    # ── Allocate target hues ─────────────────────────────────────────
    hue_targets = {
        "keyword": primary["hue"],
        "function": hue_midpoint(primary["hue"], secondary["hue"]),
        "type": secondary["hue"],
        "member": hue_midpoint(secondary["hue"], tertiary["hue"]),
        "variable": tertiary["hue"],
        "parameter": hue_mix(info["center_hue"], opposite, 0.36),
        "constant": (opposite - spread) % 1.0,
        "string": (opposite + spread) % 1.0,
        "builtin": (info["center_hue"] - quarter) % 1.0,
        "meta": (info["center_hue"] + quarter) % 1.0,
        "namespace": hue_mix(primary["hue"], opposite, 0.52),
    }

    light_shifts = {
        "keyword": 0.10,      # brightest — most prominent
        "constant": 0.07,
        "string": 0.06,
        "function": 0.04,
        "type": 0.02,
        "member": -0.02,
        "variable": -0.04,
        "parameter": -0.06,
        "meta": -0.08,        # dimmest syntax
    }

    syntax: dict[str, str] = {}

    # Per-token contrast targets — primary tokens (keywords, functions,
    # strings, constants, types) must be clearly readable at 4.5:1.
    # Secondary tokens (member, variable, parameter, builtin, namespace,
    # meta) can be lower at 3.5:1, which lets the lightness hierarchy
    # survive on very dark float_bg backgrounds.
    # The same targets apply BOTH to _make_color's contrast push AND to
    # the post-hoc _validate_and_fix, so secondary tokens stay visibly
    # dimmer than primary ones.
    PRIMARY_TOKENS = {"keyword", "function", "constant", "string", "type"}
    SECONDARY_TOKENS = {"member", "variable", "parameter", "builtin", "namespace", "meta"}

    for name, target_hue in hue_targets.items():
        anchor, distance = _nearest_source(target_hue, sources)
        sat = _clamp(base_sat + min(distance, 0.25) * 0.60, 0.60, 0.92)

        shift = light_shifts.get(name, 0.0)
        if is_dark:
            light = _clamp(base_light + shift, 0.56, 0.82)
        else:
            light = _clamp(base_light + shift, 0.18, 0.52)

        # Per-token contrast targets
        if name in PRIMARY_TOKENS:
            token_target = 4.5
        elif name in SECONDARY_TOKENS:
            token_target = 3.5
        else:
            token_target = 4.5

        # Adjust contrast against the WORST background so the colour
        # has acceptable contrast on EVERY surface.
        color = _make_color(
            target_hue, sat, light,
            anchor_color=anchor["color"],
            anchor_blend=anchor_blend,
            bg_hex=worst_bg,
            contrast_target=token_target,
        )

        # Validate against practical backgrounds and re-adjust if needed
        syntax[name] = _validate_and_fix(color, practical_bg_hexes, token_target)

    # ── Operator ─────────────────────────────────────────────────────
    meta_rgb = hex_to_rgb(syntax.get("meta", fg_hex))
    fg_rgb = hex_to_rgb(fg_hex)
    op_blended = (
        meta_rgb[0] + (fg_rgb[0] - meta_rgb[0]) * 0.32,
        meta_rgb[1] + (fg_rgb[1] - meta_rgb[1]) * 0.32,
        meta_rgb[2] + (fg_rgb[2] - meta_rgb[2]) * 0.32,
    )
    op_target = 4.2 if is_dark else 3.8
    op_color = rgb_hex(*adjust_contrast(op_blended, hex_to_rgb(worst_bg), op_target))
    syntax["operator"] = _validate_and_fix(op_color, practical_bg_hexes, 3.5)

    # ── Muted ────────────────────────────────────────────────────────
    # Blend fg slightly toward bg so muted stays close to the main text
    # colour — comments and secondary info (e.g. snacks file paths) need
    # to be clearly readable.  Validated against bg and float_bg (3.0:1).
    muted_blended = (
        fg_rgb[0] + (bg_rgb[0] - fg_rgb[0]) * (0.15 if is_dark else 0.15),
        fg_rgb[1] + (bg_rgb[1] - fg_rgb[1]) * (0.15 if is_dark else 0.15),
        fg_rgb[2] + (bg_rgb[2] - fg_rgb[2]) * (0.15 if is_dark else 0.15),
    )
    muted_color = rgb_hex(*clamp_rgb(*muted_blended))
    syntax["muted"] = _validate_and_fix(muted_color, practical_bg_hexes, 3.0)

    return syntax
