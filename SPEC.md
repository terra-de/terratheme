# terratheme — Color Token Specification

> Version 2 of the Terra DE palette system.
> Intended to replace the Material 3–based `palette.json` v1.

## Overview

A fully-derived palette system: extract 5 dominant colors from an image, then algorithmically produce 20 tokens per mode (light/dark) covering backgrounds, text, semantic colors, error, and outlines.

## Source Colors

```
c0  most prevalent color in the image  → main surface
c1  second most prevalent               → elevated surfaces
c2  third most prevalent                 → very front surfaces
c3  fourth most prevalent                → deepest surfaces
c4  fifth most prevalent                 → spare accent, feeds on_c3 only
```

The 5 source colors are ordered by prevalence (how much of the image they occupy). They are accessed directly as `c0`–`c4` in the palette — there is no separate `source_colors` field.

## Token Categories

### 1. Backgrounds (4 tokens)

| Token | Source | Role |
|-------|--------|------|
| `back` | c3, adjusted | Deepest layer (bar bg, desktop backdrop) |
| `base` | c0, adjusted | Main surface (panel bg, window bg) |
| `front` | c1, adjusted | Elevated (menus, tooltips, notifications) |
| `top` | c2, adjusted | Very front (OSD, modal popups) |

**Adjustment**: take the source color, reduce chroma to ~5–10% of original, and shift tone:

- **Dark mode**: tones from 3–15% luminance (back is darkest, top is lightest)
- **Light mode**: tones from 85–97% luminance (back is darkest, top is lightest)

Layer ordering within each mode: `back` → `base` → `front` → `top` (darkest to lightest in dark mode, or the reverse luminance ordering for light mode so they remain visually distinct).

### 2. Text / Foreground (2 tokens)

| Token | Role |
|-------|------|
| `standard` | Primary body text, highest contrast |
| `muted` | Secondary info, captions, placeholders |

**Derivation**: start from near-white (dark mode) or near-black (light mode), optionally tint slightly toward c0 for a subtle palette tie-in. `muted` is the same hue as `standard` but shifted toward the background tone by ~40% to reduce contrast.

All 5 semantic colors (`c0`–`c4`) plus `error` should also be usable as text colors directly.

### 3. Semantic Colors (5 base + 5 on-)

| Token | Source | Derivation |
|-------|--------|------------|
| `c0` | source color 0 | Raw extracted color, most prevalent |
| `on_c0` | c1, adjusted | c1 adjusted for readability on c0 |
| `c1` | source color 1 | Raw extracted color |
| `on_c1` | c2, adjusted | c2 adjusted for readability on c1 |
| `c2` | source color 2 | Raw extracted color |
| `on_c2` | c3, adjusted | c3 adjusted for readability on c2 |
| `c3` | source color 3 | Raw extracted color |
| `on_c3` | c4, adjusted | c4 adjusted for readability on c3 |
| `c4` | source color 4 | Raw extracted color, least prevalent |
| `on_c4` | c0, adjusted | c0 adjusted for readability on c4 |

**On-color derivation**: take the source color (e.g., c1 for `on_c0`), shift its tone (luminance) to ensure reasonable contrast against the paired base color, and boost chroma slightly so it reads as a distinct accent rather than a washed-out variant.

**Contrast logging**: all ratios are logged during generation in a `contrast_log` section. Low contrast is accepted for now — the log provides data for future tuning.

The chain-linking (`on_c0` borrows from c1, `on_c1` borrows from c2, etc.) creates a playful cross-hue effect: text on a c0 background has a different hue than the background itself, making the palette feel cohesive but not boring.

### 4. Error (1 base + 1 on-)

| Token | Derivation |
|-------|------------|
| `error` | Start from pure red (`#ff0000`), blend ~20% toward c0 |
| `on_error` | Appropriate contrast for red, blended ~20% toward c1 |

The red anchor ensures error states are universally recognizable. The blend toward c0/c1 ties it to the palette.

### 5. Outline (1 token)

| Token | Derivation |
|-------|------------|
| `outline` | Take c0, shift in the opposite direction of the current mode |

- **Dark mode**: make it *lighter* than c0 (visible against dark backgrounds)
- **Light mode**: make it *darker* than c0 (visible against light backgrounds)

Chroma is reduced so it reads as a border, not an accent. This is a deliberately simple derivation — outlines just need to separate visual regions, not be beautiful.

## Mode Structure

```json
{
  "version": 2,
  "mode": "dark",
  "light": { ... 20 tokens ... },
  "dark": { ... 20 tokens ... },
  "contrast_log": {
    "on_c0_on_c0": "3.2:1",
    "on_c1_on_c1": "4.8:1",
    ...
  }
}
```

`mode` can be `"light"`, `"dark"`, or `"auto"` (pick based on image luminance analysis at generation time).

## Complete Token List (20 per mode)

```
back
base
front
top
standard
muted
c0           on_c0
c1           on_c1
c2           on_c2
c3           on_c3
c4           on_c4
error        on_error
outline
```

## CLI

```bash
terratheme extract <image>                       # Show 5 source colors
terratheme generate <image>                      # Full palette.json → ~/.config/terra/palette.json
terratheme generate <image> --mode dark          # Force dark mode
terratheme generate <image> --mode light         # Force light mode
terratheme generate <image> --stdout             # Print JSON to stdout (pipe-friendly)
terratheme generate <image> --output custom.json # Write to custom path
terratheme generate <image> --visualize          # Terminal preview (no file write)
```

## Key Design Principles

1. **Purpose-based with hue awareness**: Most tokens are named by role (back, base, standard), not by hue (red, blue). The hue wheel emerges naturally from what the image provides.
2. **Borrow, don't invent**: On-colors borrow from adjacent source colors rather than falling back to white/black. This keeps palettes playful.
3. **Backgrounds are subdued**: High-chroma colors belong to semantic/role colors, not backgrounds. Backgrounds are desaturated derivatives.
4. **Error stays red**: One hardcoded hue anchor for universal recognition, blended just enough to fit the palette.
5. **Everything logged**: Contrast ratios are generated but not enforced — we collect data first, tune thresholds later.

## Open Items (Future Phases)

- ANSI terminal color mapping (16 colors from this palette)
- Template rendering (foot, zellij, nvim, lf, gtk, qt, hyprland, etc.)
- `terratheme apply` command
- TTheme v2 to consume palette.json v2
