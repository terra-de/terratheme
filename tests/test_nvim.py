"""Tests for the Neovim target — terra_colors.lua generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from terratheme.palette.color_utils import contrast_ratio, hex_to_rgb, relative_luminance
from terratheme.palette.derive import derive_palette
from terratheme.palette.extract import extract_colors
from terratheme.targets.nvim import NeovimTarget

HERE = Path(__file__).parent
TEST_IMAGE = HERE / "test_5bands.png"


@pytest.fixture(scope="module")
def palette() -> dict:
    sources = extract_colors(str(TEST_IMAGE))
    return derive_palette(sources, mode="dark")


@pytest.fixture(scope="module")
def content(palette: dict) -> str:
    target = NeovimTarget()
    return target.render(palette, "dark")


@pytest.fixture(scope="module")
def tokens(content: str) -> dict[str, str]:
    """Execute the generated Lua and return the table."""
    import re
    ns: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        # Match: key = "value"  or  ["key"] = "value"
        m = re.match(r'(?:\[")?(\w+)(?:"\])?\s*=\s*"([^"]+)"', line)
        if m:
            ns[m.group(1)] = m.group(2)
    return ns


# ── Structural tests ───────────────────────────────────────────────────


def test_output_contains_version(content: str) -> None:
    assert 'version = 2' in content


def test_output_contains_mode(content: str) -> None:
    assert 'mode = "dark"' in content or 'mode = "light"' in content


EXPECTED_KEYS = {
    # Backgrounds
    "bg", "bg_alt", "bg_recessed", "float_bg", "elevated_bg",
    # Text & outlines
    "fg", "outline", "outline_variant",
    # Accents
    "accent", "accent2", "accent3",
    # Syntax palette
    "keyword", "function", "type", "member", "variable",
    "parameter", "builtin", "namespace", "constant",
    "string", "meta", "operator", "muted",
    # Semantic
    "error", "on_error", "warning", "info", "hint",
    # Diff
    "diff_red", "diff_green", "diff_yellow",
    "diff_red_bg", "diff_green_bg", "diff_yellow_bg",
    "diff_text_bg",
    # Derived UI
    "cursorline_bg", "visual_bg", "matchparen_bg",
    "search_fg", "incsearch_fg",
    "lsp_reference_bg", "lsp_reference_write_bg",
    "virtual_error_bg", "virtual_warn_bg",
    "virtual_info_bg", "virtual_hint_bg",
    # Lualine
    "lualine_normal", "lualine_insert", "lualine_visual",
    "lualine_replace", "lualine_command",
    # Source colours
    "c0", "c1", "c2", "c3", "c4",
}


def test_all_expected_keys_present(tokens: dict[str, str]) -> None:
    missing = EXPECTED_KEYS - set(tokens.keys())
    extra = set(tokens.keys()) - EXPECTED_KEYS - {"version", "mode"}
    assert not missing, f"missing keys: {missing}"
    assert not extra, f"unexpected keys: {extra}"


def test_all_values_are_valid_hex(tokens: dict[str, str]) -> None:
    for key, value in tokens.items():
        if key in ("version", "mode"):
            continue
        assert value.startswith("#"), f"{key}: not a hex string ({value})"
        assert len(value) == 7, f"{key}: wrong length ({value})"
        int(value[1:], 16)  # raises if invalid


# ── Background hierarchy tests ─────────────────────────────────────────


def test_backgrounds_ordered_by_lightness(tokens: dict[str, str]) -> None:
    """bg_recessed (bottom) < bg_alt (low) < bg (base) < float_bg (high) < elevated_bg (top)."""
    names = ["bg_recessed", "bg_alt", "bg", "float_bg", "elevated_bg"]
    lums = []
    for name in names:
        r, g, b = hex_to_rgb(tokens[name])
        lums.append(relative_luminance(float(r), float(g), float(b)))
    for i in range(len(lums) - 1):
        assert lums[i] < lums[i + 1], (
            f"{names[i]} (l={lums[i]:.4f}) not darker than {names[i + 1]} (l={lums[i + 1]:.4f})"
        )


# ── Syntax palette tests ────────────────────────────────────────────────


def test_syntax_colors_differ(tokens: dict[str, str]) -> None:
    """Syntax colors should be distinct from each other."""
    syn_keys = ["keyword", "function", "type", "constant", "string", "meta"]
    values = [tokens[k] for k in syn_keys]
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            if values[i] == values[j]:
                # Allow occasional collision with neutral-ish hues
                r, g, b = hex_to_rgb(values[i])
                sat = max(r, g, b) - min(r, g, b)
                assert sat < 30, f"{syn_keys[i]} == {syn_keys[j]} == {values[i]}"


# ── Diff colour tests ───────────────────────────────────────────────────


def test_diff_red_is_reddish(tokens: dict[str, str]) -> None:
    r, g, b = hex_to_rgb(tokens["diff_red"])
    assert r > g and r > b, f"diff_red ({tokens['diff_red']}) not reddish"


def test_diff_green_not_red(tokens: dict[str, str]) -> None:
    r, g, b = hex_to_rgb(tokens["diff_green"])
    assert g >= r * 0.8, f"diff_green ({tokens['diff_green']}) too red"


# ── Lualine tests ───────────────────────────────────────────────────────


def test_lualine_colors_differ(tokens: dict[str, str]) -> None:
    """At least some lualine accents should differ."""
    modes = ["normal", "insert", "visual", "replace", "command"]
    values = [tokens[f"lualine_{m}"] for m in modes]
    unique = len(set(values))
    assert unique >= 3, f"too many identical lualine colours: {values}"


# ── Contrast safety tests ────────────────────────────────────────────────


def test_muted_contrast_on_practical_backgrounds(tokens: dict[str, str]) -> None:
    """Muted >= 3.0:1 on bg and float_bg (where comments actually appear)."""
    for bg_name in ("bg", "float_bg"):
        muted = hex_to_rgb(tokens["muted"])
        bg = hex_to_rgb(tokens[bg_name])
        ratio = contrast_ratio(muted, bg)
        assert ratio >= 3.0, (
            f"muted on {bg_name}: {ratio:.2f}:1 < 3.0:1"
        )


def test_syntax_contrast_on_editor_surfaces(tokens: dict[str, str]) -> None:
    """Syntax >= 4.5:1 on bg/float_bg; >= 3.0:1 on elevated_bg."""
    all_layers = ["bg_recessed", "bg_alt", "bg", "float_bg", "elevated_bg"]
    syn_keys = ["keyword", "function", "type", "constant", "string", "meta", "namespace", "builtin"]
    failures = []
    for sk in syn_keys:
        fg = hex_to_rgb(tokens[sk])
        for bg_name in all_layers:
            bg = hex_to_rgb(tokens[bg_name])
            ratio = contrast_ratio(fg, bg)
            if bg_name in ("elevated_bg",):
                target = 3.0
            else:
                target = 4.5
            if ratio < target:
                failures.append(f"{sk} on {bg_name}: {ratio:.2f}:1 (target {target})")
    assert not failures, "contrast failures:\n  " + "\n  ".join(failures)
