"""Neovim target — pre-computed colour token file.

Generates ``~/.local/share/nvim/terra_colors.lua`` with ~50 pre-computed
colour tokens so Neovim does **zero** color math at runtime.
"""

from __future__ import annotations

from pathlib import Path

from terratheme.config import load_config
from terratheme.palette.color_utils import (
    clamp_rgb,
    contrast_ratio,
    hex_to_rgb,
    hsl_to_rgb,
    rgb_hex,
    rgb_to_hsl,
)
from terratheme.palette.syntax_palette import derive_syntax
from terratheme.palette.syntax_utils import (
    adjust_contrast,
    blend_hex,
    complementary_hue,
    semantic_diff_fg,
    is_complementary,
    hue_distance,
)
from terratheme.targets.base import BaseTarget


class NeovimTarget(BaseTarget):
    """Generates a Lua file of pre-computed colour tokens for Neovim."""

    name = "nvim"
    description = "Neovim pre-computed colour tokens (terra_colors.lua)"
    output_path = str(Path.home() / ".local/share/nvim" / "terra_colors.lua")

    # ── Background mapping 💡 ──────────────────────────────────────────
    # v2 5-layer → Neovim UI:
    #   bottom (0.04) → bg_recessed  (EndOfBuffer)
    #   low    (0.10) → bg_alt       (LineNr, SignColumn)
    #   base   (0.18) → bg           (Normal, NormalNC)
    #   high   (0.28) → float_bg     (NormalFloat, Pmenu, StatusLineNC)
    #   top    (0.40) → elevated_bg  (PmenuSel, TabLineSel)
    _BG_MAP = [
        ("bg_recessed", "bottom"),
        ("bg_alt", "low"),
        ("bg", "base"),
        ("float_bg", "high"),
        ("elevated_bg", "top"),
    ]

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _hex_to_hsl01(hex_str: str) -> tuple[float, float, float]:
        """Return ``(hue 0-1, sat 0-1, light 0-1)``."""
        r, g, b = hex_to_rgb(hex_str)
        h, s, l = rgb_to_hsl(float(r), float(g), float(b))
        return h / 360.0, s, l

    @staticmethod
    def _hsl01_to_hex(h: float, s: float, l: float) -> str:
        """HSL (0-1 range) → ``#rrggbb``."""
        r, g, b = hsl_to_rgb(h * 360.0, s, l)
        return rgb_hex(*clamp_rgb(r, g, b))

    # ── Lualine hue allocation (ported from hues.lua) ───────────────────

    def _allocate_lualine_hues(self, tokens: dict[str, str]) -> dict[str, float]:
        """Allocate hues for lualine statusline accents."""
        h_c4, _, _ = self._hex_to_hsl01(tokens["c4"])
        h_c3, _, _ = self._hex_to_hsl01(tokens["c3"])
        h_c2, _, _ = self._hex_to_hsl01(tokens["c2"])

        palette_hues = [h_c4, h_c3, h_c2]
        diversity = max(palette_hues) - min(palette_hues)
        h_primary, h_secondary, h_tertiary = h_c4, h_c3, h_c2

        if diversity > 0.15:
            return self._lualine_high(diversity, h_primary, h_secondary, h_tertiary, palette_hues)
        elif diversity > 0.05:
            return self._lualine_medium(diversity, h_primary, h_secondary, h_tertiary, palette_hues)
        else:
            return self._lualine_low(h_primary, h_secondary, h_tertiary)

    def _lualine_high(
        self, _diversity: float,
        h_primary: float, h_secondary: float, h_tertiary: float,
        palette_hues: list[float],
    ) -> dict[str, float]:
        comp_i, comp_j, h_comp1, h_comp2 = None, None, None, None
        for i, h1 in enumerate(palette_hues):
            for j, h2 in enumerate(palette_hues):
                if i != j and is_complementary(h1, h2):
                    comp_i, comp_j, h_comp1, h_comp2 = i, j, h1, h2
                    break
            if comp_i is not None:
                break

        if comp_i is not None and comp_j is not None:
            control = h_comp1
            strings = h_comp2
        else:
            control = h_primary
            strings = (h_tertiary + 0.5) % 1.0

        return {
            "functions": h_primary,
            "types": h_secondary,
            "variables": h_tertiary,
            "operators": complementary_hue(h_secondary, 0.08),
            "meta": (h_primary + h_tertiary) / 2.0,
            "constants": (h_primary + h_secondary) / 2.0,
            "control": control,
            "strings": strings,
        }

    def _lualine_medium(
        self, _diversity: float,
        h_primary: float, h_secondary: float, h_tertiary: float,
        palette_hues: list[float],
    ) -> dict[str, float]:
        comp_i, comp_j, h_comp1, h_comp2 = None, None, None, None
        for i, h1 in enumerate(palette_hues):
            for j, h2 in enumerate(palette_hues):
                if i != j and is_complementary(h1, h2):
                    comp_i, comp_j, h_comp1, h_comp2 = i, j, h1, h2
                    break
            if comp_i is not None:
                break

        if comp_i is not None and comp_j is not None:
            control = h_comp1
            strings = h_comp2
        else:
            control = (h_primary + 0.5) % 1.0
            strings = (h_secondary + 0.5) % 1.0

        return {
            "functions": h_primary,
            "types": h_secondary,
            "variables": h_tertiary,
            "operators": complementary_hue(h_secondary, 0.08),
            "meta": (h_primary + h_tertiary) / 2.0,
            "constants": (h_secondary + h_tertiary) / 2.0,
            "control": control,
            "strings": strings,
        }

    def _lualine_low(
        self, h_primary: float, h_secondary: float, h_tertiary: float,
    ) -> dict[str, float]:
        base_hue = (h_primary + h_secondary + h_tertiary) / 3.0
        spacing = 0.125
        return {
            "functions": base_hue,
            "types": (base_hue + spacing) % 1.0,
            "variables": (base_hue + 2.0 * spacing) % 1.0,
            "control": (base_hue + 3.0 * spacing) % 1.0,
            "constants": (base_hue + 4.0 * spacing) % 1.0,
            "strings": (base_hue + 5.0 * spacing) % 1.0,
            "meta": (base_hue + 6.0 * spacing) % 1.0,
            "operators": (base_hue + 7.0 * spacing) % 1.0,
        }

    def _derive_lualine_accent(
        self,
        hue: float,
        sat: float,
        light: float,
        bg_hex: str,
        target_contrast: float,
    ) -> str:
        """HSL → hex → contrast-adjust to *target_contrast* against *bg*."""
        rgb = self._hsl01_to_hex(hue, sat, light)
        rgb_t = hex_to_rgb(rgb)
        bg_t = hex_to_rgb(bg_hex)
        result = adjust_contrast(
            (float(rgb_t[0]), float(rgb_t[1]), float(rgb_t[2])),
            (float(bg_t[0]), float(bg_t[1]), float(bg_t[2])),
            target_contrast,
        )
        return rgb_hex(*result)

    # ── Contrast validation ─────────────────────────────────────────────

    CONTRAST_RULES: list[tuple[str, list[str], float]] = [
        # (fg_token,          [bg_tokens],              min_ratio)
        # Body text
        ("fg",              ["bg"],                     7.0),
        # Muted / comments — appear on bg and float surfaces
        ("muted",           ["bg", "float_bg"],         3.0),
        # Syntax colours — code on editor + picker backgrounds
        ("keyword",         ["bg", "float_bg"],         4.5),
        ("function",        ["bg", "float_bg"],         4.5),
        ("type",            ["bg", "float_bg"],         4.5),
        ("member",          ["bg", "float_bg"],         4.5),
        ("variable",        ["bg", "float_bg"],         4.5),
        ("parameter",       ["bg", "float_bg"],         4.5),
        ("builtin",         ["bg", "float_bg"],         4.5),
        ("namespace",       ["bg", "float_bg"],         4.5),
        ("constant",        ["bg", "float_bg"],         4.5),
        ("string",          ["bg", "float_bg"],         4.5),
        ("meta",            ["bg", "float_bg"],         4.5),
        ("operator",        ["bg", "float_bg"],         4.5),
        # Accents — these are raw source colours from the wallpaper,
        # used decoratively (Directory, picker highlights, statusline).
        # They are NOT body text and should keep their character even
        # if their natural contrast is below 4.5:1 on some surfaces.
        # No validation rule — they are what the wallpaper gives us.
        # Diff — fg against their own background
        ("diff_red",        ["diff_red_bg"],             3.0),
        ("diff_green",      ["diff_green_bg"],           3.0),
        ("diff_yellow",     ["diff_yellow_bg"],          3.0),
        # Semantic / diagnostic
        ("error",           ["bg", "float_bg"],          4.5),
        ("warning",         ["bg", "float_bg"],          4.5),
        ("info",            ["bg", "float_bg"],          4.5),
        ("hint",            ["bg", "float_bg"],          4.5),
        # UI text on highlighted backgrounds
        ("search_fg",       ["accent"],                  4.5),
        ("incsearch_fg",    ["accent2"],                 4.5),
        ("on_error",        ["error"],                   4.5),
    ]

    @classmethod
    def _validate_all(cls, tokens: dict[str, str]) -> dict[str, str]:
        """Run all contrast rules and adjust any colour that fails.

        Every foreground token is checked against every background it may
        appear on.  Colors that fall below the minimum ratio get lightened
        (or darkened) via binary search until they pass.
        """
        result = dict(tokens)

        for fg_key, bg_keys, target in cls.CONTRAST_RULES:
            if fg_key not in result:
                continue
            fg_hex = result[fg_key]
            fg_rgb = hex_to_rgb(fg_hex)

            # Find the background with the WORST (lowest) contrast
            worst_bg_rgb: tuple[int, int, int] | None = None
            worst_ratio = float("inf")
            for bk in bg_keys:
                if bk not in result:
                    continue
                bg_rgb = hex_to_rgb(result[bk])
                ratio = contrast_ratio(
                    (float(fg_rgb[0]), float(fg_rgb[1]), float(fg_rgb[2])),
                    (float(bg_rgb[0]), float(bg_rgb[1]), float(bg_rgb[2])),
                )
                if ratio < worst_ratio:
                    worst_ratio = ratio
                    worst_bg_rgb = bg_rgb

            if worst_bg_rgb is None or worst_ratio >= target:
                continue

            # Re-adjust against the worst background
            adjusted = adjust_contrast(
                (float(fg_rgb[0]), float(fg_rgb[1]), float(fg_rgb[2])),
                (float(worst_bg_rgb[0]), float(worst_bg_rgb[1]), float(worst_bg_rgb[2])),
                target,
            )
            result[fg_key] = rgb_hex(*adjusted)

        return result

    # ── Main render ────────────────────────────────────────────────────

    def render(self, palette: dict, mode: str) -> str:
        """Generate the complete ``terra_colors.lua`` file content."""
        # ── Light mode gating ───────────────────────────────────────
        config = load_config()
        use_light = config.get("terminal_light_mode", False)
        effective_mode = mode if use_light else "dark"
        vtokens: dict[str, str] = palette[effective_mode]  # type: ignore[typeddict-item]
        is_dark = effective_mode == "dark"

        bg_rgb = hex_to_rgb(vtokens["base"])
        bg_hex = vtokens["base"]
        float_bg_hex = vtokens["high"]

        # ── Collect all tokens into a dict first ────────────────────
        colors: dict[str, str] = {}

        def store(key: str, value: str) -> None:
            colors[key] = value

        # 1. Background layers
        for nv_key, v2_key in self._BG_MAP:
            store(nv_key, vtokens[v2_key])

        # 2. Text
        store("fg", vtokens["standard"])

        # 3. Outlines
        store("outline", vtokens["outline"])
        outline_rgb = hex_to_rgb(vtokens["outline"])
        bg_rgb_t = hex_to_rgb(bg_hex)
        ov = clamp_rgb(
            outline_rgb[0] + (bg_rgb_t[0] - outline_rgb[0]) * 0.4,
            outline_rgb[1] + (bg_rgb_t[1] - outline_rgb[1]) * 0.4,
            outline_rgb[2] + (bg_rgb_t[2] - outline_rgb[2]) * 0.4,
        )
        store("outline_variant", rgb_hex(*ov))

        # 4. Accents
        store("accent", vtokens["c4"])
        store("accent2", vtokens["c3"])
        store("accent3", vtokens["c2"])

        # 5. Syntax palette
        syntax_tokens = dict(vtokens)
        syntax_tokens["bg"] = bg_hex
        syntax_tokens["float_bg"] = vtokens["high"]
        syntax_tokens["elevated_bg"] = vtokens["top"]
        syntax_tokens["fg"] = vtokens["standard"]
        syntax = derive_syntax(syntax_tokens)
        for key in ("keyword", "function", "type", "member", "variable",
                     "parameter", "builtin", "namespace", "constant",
                     "string", "meta", "operator", "muted"):
            store(key, syntax[key])

        # 6. Semantic
        store("error", vtokens["error"])
        store("on_error", vtokens["on_error"])
        warn = blend_hex(vtokens["error"], vtokens["c3"], 0.5)
        store("warning", warn)
        store("info", vtokens["c4"])
        store("hint", vtokens["c3"])

        # 7. Diff colours
        err_rgb = hex_to_rgb(vtokens["error"])
        c4_rgb = hex_to_rgb(vtokens["c4"])
        c3_rgb = hex_to_rgb(vtokens["c3"])

        diff_red_rgb = semantic_diff_fg(
            (float(err_rgb[0]), float(err_rgb[1]), float(err_rgb[2])), 0.0,
        )
        diff_green_rgb = semantic_diff_fg(
            (float(c4_rgb[0]), float(c4_rgb[1]), float(c4_rgb[2])), 0.33,
        )
        diff_yellow_rgb = semantic_diff_fg(
            (float(c3_rgb[0]), float(c3_rgb[1]), float(c3_rgb[2])), 0.16,
        )
        store("diff_red", rgb_hex(*diff_red_rgb))
        store("diff_green", rgb_hex(*diff_green_rgb))
        store("diff_yellow", rgb_hex(*diff_yellow_rgb))
        store("diff_red_bg", blend_hex(rgb_hex(*diff_red_rgb), float_bg_hex, 0.35))
        store("diff_green_bg", blend_hex(rgb_hex(*diff_green_rgb), float_bg_hex, 0.35))
        store("diff_yellow_bg", blend_hex(rgb_hex(*diff_yellow_rgb), float_bg_hex, 0.35))
        store("diff_text_bg", blend_hex(rgb_hex(*diff_yellow_rgb), bg_hex, 0.68))

        # 8. Derived UI
        fbg_h, fbg_s, fbg_l = self._hex_to_hsl01(vtokens["high"])
        bg_h, bg_s, bg_l = self._hex_to_hsl01(bg_hex)
        cursor_l = bg_l + (fbg_l - bg_l) * 0.6
        cursor_bg = self._hsl01_to_hex(bg_h, bg_s, cursor_l)
        store("cursorline_bg", cursor_bg)

        store("visual_bg", blend_hex(vtokens["c4"], bg_hex, 0.35))
        store("matchparen_bg", blend_hex(vtokens["c4"], bg_hex, 0.25))
        store("search_fg", vtokens["on_c4"])
        store("incsearch_fg", vtokens["on_c3"])
        store("lsp_reference_bg", blend_hex(vtokens["c4"], bg_hex, 0.18))
        store("lsp_reference_write_bg", blend_hex(vtokens["c4"], bg_hex, 0.25))

        store("virtual_error_bg", blend_hex(vtokens["error"], bg_hex, 0.28))
        store("virtual_warn_bg", blend_hex(warn, bg_hex, 0.45))
        store("virtual_info_bg", blend_hex(vtokens["c4"], bg_hex, 0.45))
        store("virtual_hint_bg", blend_hex(vtokens["c3"], bg_hex, 0.28))

        # 9. Lualine
        lualine_hues = self._allocate_lualine_hues(vtokens)

        if is_dark:
            func_l, type_l, var_l, const_l, error_l, meta_l, op_l = (
                0.50, 0.55, 0.50, 0.55, 0.50, 0.48, 0.45,
            )
        else:
            func_l, type_l, var_l, const_l, error_l, meta_l, op_l = (
                0.30, 0.35, 0.40, 0.38, 0.32, 0.30, 0.32,
            )

        store("lualine_normal", self._derive_lualine_accent(
            lualine_hues["functions"], 0.75, func_l, bg_hex, 5.0,
        ))
        store("lualine_insert", self._derive_lualine_accent(
            lualine_hues["variables"], 0.65, var_l, bg_hex, 4.5,
        ))
        store("lualine_visual", self._derive_lualine_accent(
            lualine_hues["constants"], 0.70, const_l, bg_hex, 5.0,
        ))
        h_err, _, _ = self._hex_to_hsl01(vtokens["error"])
        store("lualine_replace", self._derive_lualine_accent(
            h_err, 0.80, error_l, bg_hex, 5.0,
        ))
        store("lualine_command", self._derive_lualine_accent(
            lualine_hues["meta"], 0.75, meta_l, bg_hex, 5.0,
        ))

        # 10. Source colours (for reference only — NOT validated)
        for i in range(5):
            store(f"c{i}", vtokens[f"c{i}"])

        # ── Run comprehensive contrast validation ──────────────────────
        colors = self._validate_all(colors)

        # ── Assemble Lua output ─────────────────────────────────────
        lua: list[str] = [
            'return {',
            f'  version = 2,',
            f'  mode = "{effective_mode}",',
            '',
        ]

        def emit(key: str, value: str) -> None:
            quoted = f'["{key}"]' if key in ("function", "end", "while", "for", "repeat", "until") else key
            lua.append(f'  {quoted} = "{value}",')

        # Emit in logical order
        lua.append('  -- Background layers')
        for nv_key, _v2_key in self._BG_MAP:
            emit(nv_key, colors[nv_key])
        lua.append('')

        lua.append('  -- Text')
        emit("fg", colors["fg"])
        lua.append('')

        lua.append('  -- Outlines')
        emit("outline", colors["outline"])
        emit("outline_variant", colors["outline_variant"])
        lua.append('')

        lua.append('  -- Accents')
        emit("accent", colors["accent"])
        emit("accent2", colors["accent2"])
        emit("accent3", colors["accent3"])
        lua.append('')

        lua.append('  -- Syntax palette')
        for k in ("keyword", "function", "type", "member", "variable",
                   "parameter", "builtin", "namespace", "constant",
                   "string", "meta", "operator", "muted"):
            emit(k, colors[k])
        lua.append('')

        lua.append('  -- Semantic')
        emit("error", colors["error"])
        emit("on_error", colors["on_error"])
        emit("warning", colors["warning"])
        emit("info", colors["info"])
        emit("hint", colors["hint"])
        lua.append('')

        lua.append('  -- Diff')
        for k in ("diff_red", "diff_green", "diff_yellow",
                   "diff_red_bg", "diff_green_bg", "diff_yellow_bg",
                   "diff_text_bg"):
            emit(k, colors[k])
        lua.append('')

        lua.append('  -- Derived UI')
        for k in ("cursorline_bg", "visual_bg", "matchparen_bg",
                   "search_fg", "incsearch_fg",
                   "lsp_reference_bg", "lsp_reference_write_bg",
                   "virtual_error_bg", "virtual_warn_bg",
                   "virtual_info_bg", "virtual_hint_bg"):
            emit(k, colors[k])
        lua.append('')

        lua.append('  -- Lualine mode accents')
        for k in ("lualine_normal", "lualine_insert", "lualine_visual",
                   "lualine_replace", "lualine_command"):
            emit(k, colors[k])
        lua.append('')

        lua.append('  -- Source colours (for reference)')
        for i in range(5):
            emit(f"c{i}", colors[f"c{i}"])
        lua.append('}')

        return '\n'.join(lua) + '\n'

    # ── Post-hook ───────────────────────────────────────────────────────

    def post_hook(self) -> list[str]:
        """Optionally notify Neovim to reload via the TerrathemeReload command."""
        return [
            'nvim --headless -c "TerrathemeReload" -c "q" 2>/dev/null || true',
        ]
