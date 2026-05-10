"""Tests for palette extraction and derivation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from terratheme.palette.color_utils import hex_to_rgb
from terratheme.palette.derive import derive_palette
from terratheme.palette.extract import extract_colors

HERE = Path(__file__).parent
TEST_IMAGE = HERE / "test_5bands.png"


def test_extract_returns_five_colors() -> None:
    colors = extract_colors(str(TEST_IMAGE))
    assert len(colors) == 5
    for r, g, b in colors:
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255


def test_extract_colors_ordered_by_luminance() -> None:
    from terratheme.palette.color_utils import rgb_to_hsl

    colors = extract_colors(str(TEST_IMAGE))
    for i in range(len(colors) - 1):
        _, _, l1 = rgb_to_hsl(float(colors[i][0]), float(colors[i][1]), float(colors[i][2]))
        _, _, l2 = rgb_to_hsl(float(colors[i + 1][0]), float(colors[i + 1][1]), float(colors[i + 1][2]))
        assert l1 <= l2 + 0.01, f"colour {i} not darker than {i + 1}: {l1} vs {l2}"


class TestDerive:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.sources = extract_colors(str(TEST_IMAGE))

    def test_derive_default_mode(self) -> None:
        palette = derive_palette(self.sources)
        assert palette["version"] == 2
        assert palette["mode"] in ("dark", "light")
        assert "light" in palette
        assert "dark" in palette

    def test_derive_forced_modes(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        assert palette["mode"] == "dark"

        palette = derive_palette(self.sources, mode="light")
        assert palette["mode"] == "light"

    def test_all_tokens_present(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        expected_tokens = {
            "bottom", "low", "base", "high", "top",
            "standard", "muted",
            "c0", "c1", "c2", "c3", "c4",
            "on_c0", "on_c1", "on_c2", "on_c3", "on_c4",
            "error", "on_error",
            "outline",
            "ansi_0", "ansi_1", "ansi_2", "ansi_3", "ansi_4", "ansi_5",
            "ansi_6", "ansi_7", "ansi_8",
            "ansi_9", "ansi_10", "ansi_11", "ansi_12", "ansi_13",
            "ansi_14", "ansi_15",
        }
        for mode_name in ("dark", "light"):
            tokens = palette[mode_name]
            assert set(tokens.keys()) == expected_tokens, (
                f"missing or extra tokens in {mode_name} mode: "
                f"{expected_tokens - set(tokens.keys())} extra, "
                f"{set(tokens.keys()) - expected_tokens} missing"
            )

    def test_tokens_are_valid_hex(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        for mode_name in ("dark", "light"):
            for name, hex_str in palette[mode_name].items():
                assert hex_str.startswith("#"), f"{mode_name}.{name}: not a hex string"
                assert len(hex_str) == 7, f"{mode_name}.{name}: wrong length"
                int(hex_str[1:], 16)  # will raise if invalid

    def test_c0_is_background_source_dark_mode(self) -> None:
        """In dark mode, c0 is the darkest source; all bgs derive from it."""
        from terratheme.palette.color_utils import rgb_to_hsl

        palette = derive_palette(self.sources, mode="dark")
        tokens = palette["dark"]

        # c0 should be the darkest of c0-c4
        c_lums = [
            (i, rgb_to_hsl(*hex_to_rgb(tokens[f"c{i}"]))[2])
            for i in range(5)
        ]
        c0_lum = c_lums[0][1]
        for i, lum in c_lums[1:]:
            assert c0_lum <= lum + 0.01, (
                f"dark mode c0 (l={c0_lum:.3f}) not darkest: c{i} (l={lum:.3f})"
            )

        # All backgrounds should originate from the same source as c0
        # (can't directly test, but we can verify they share a hue family)
        bg_lums = [
            rgb_to_hsl(*hex_to_rgb(tokens[name]))[2]
            for name in ("bottom", "low", "base", "high", "top")
        ]
        for i in range(len(bg_lums) - 1):
            assert bg_lums[i] <= bg_lums[i + 1], (
                f"backgrounds out of order at index {i}"
            )

    def test_c0_is_background_source_light_mode(self) -> None:
        """In light mode, c0 is the lightest source (reversed)."""
        from terratheme.palette.color_utils import rgb_to_hsl

        palette = derive_palette(self.sources, mode="light")
        tokens = palette["light"]

        # c0 should be the lightest of c0-c4
        c_lums = [
            (i, rgb_to_hsl(*hex_to_rgb(tokens[f"c{i}"]))[2])
            for i in range(5)
        ]
        c0_lum = c_lums[0][1]
        for i, lum in c_lums[1:]:
            assert c0_lum >= lum - 0.01, (
                f"light mode c0 (l={c0_lum:.3f}) not lightest: c{i} (l={lum:.3f})"
            )

    def test_c0_differs_between_modes(self) -> None:
        """c0 is reversed per mode, so values differ."""
        palette = derive_palette(self.sources, mode="dark")
        dark_c0 = palette["dark"]["c0"]
        light_c0 = palette["light"]["c0"]
        assert dark_c0 != light_c0, "c0 should differ between modes"

    def test_backgrounds_ordered_correctly(self) -> None:
        from terratheme.palette.color_utils import rgb_to_hsl

        palette = derive_palette(self.sources, mode="dark")
        names = ["bottom", "low", "base", "high", "top"]

        # Dark mode: bottom=darkest, top=brightest (ascending)
        dark_values = [rgb_to_hsl(*hex_to_rgb(palette["dark"][n]))[2] for n in names]
        for i in range(len(dark_values) - 1):
            assert dark_values[i] <= dark_values[i + 1], (
                f"dark bg {names[i]} (l={dark_values[i]:.3f}) > "
                f"{names[i + 1]} (l={dark_values[i + 1]:.3f})"
            )

        # Light mode: bottom=brightest, top=darkest (descending)
        light_values = [rgb_to_hsl(*hex_to_rgb(palette["light"][n]))[2] for n in names]
        for i in range(len(light_values) - 1):
            assert light_values[i] >= light_values[i + 1], (
                f"light bg {names[i]} (l={light_values[i]:.3f}) < "
                f"{names[i + 1]} (l={light_values[i + 1]:.3f})"
            )

    def test_contrast_log_populated(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        log = palette["contrast_log"]
        assert len(log) == 12  # 6 pairings × 2 modes
        for key, ratio in log.items():
            assert ratio.endswith(":1")
            value = float(ratio[:-2])
            assert value > 0

    def test_json_serializable(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        dumped = json.dumps(palette)
        loaded = json.loads(dumped)
        assert loaded["version"] == 2

    def test_error_is_reddish(self) -> None:
        """Error should have a strong red component (blended toward bg source)."""
        palette = derive_palette(self.sources, mode="dark")
        r, g, b = hex_to_rgb(palette["dark"]["error"])
        assert r > g * 1.5, f"error {palette['dark']['error']} not reddish enough"
        assert r > b * 1.5, f"error {palette['dark']['error']} not reddish enough"

    def test_outline_differs_from_backgrounds(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        outline = hex_to_rgb(palette["dark"]["outline"])
        for bg_name in ("bottom", "low", "base", "high", "top"):
            bg = hex_to_rgb(palette["dark"][bg_name])
            diff = sum(abs(outline[i] - bg[i]) for i in range(3))
            assert diff > 10, f"outline too close to {bg_name}: diff={diff}"

    # ── ANSI token tests ────────────────────────────────────────────

    def test_ansi_tokens_present(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        for mode_name in ("dark", "light"):
            tokens = palette[mode_name]
            for i in range(16):
                key = f"ansi_{i}"
                assert key in tokens, f"missing {key} in {mode_name} mode"

    def test_ansi_tokens_valid_hex(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        for mode_name in ("dark", "light"):
            for i in range(16):
                hex_str = palette[mode_name][f"ansi_{i}"]
                assert hex_str.startswith("#"), f"{mode_name}.ansi_{i}: not a hex string"
                assert len(hex_str) == 7, f"{mode_name}.ansi_{i}: wrong length"
                int(hex_str[1:], 16)  # will raise if invalid

    def test_ansi_0_is_background(self) -> None:
        """ansi_0 (black) should equal dark-mode base, ansi_8 (br black) should equal dark-mode high."""
        palette = derive_palette(self.sources, mode="dark")
        dark = palette["dark"]
        for mode_name in ("dark", "light"):
            tokens = palette[mode_name]
            assert tokens["ansi_0"] == dark["base"], (
                f"{mode_name}: ansi_0 ({tokens['ansi_0']}) != dark.base ({dark['base']})"
            )
            assert tokens["ansi_8"] == dark["high"], (
                f"{mode_name}: ansi_8 ({tokens['ansi_8']}) != dark.high ({dark['high']})"
            )

    def test_ansi_7_is_light_reference(self) -> None:
        """ansi_7 (white) should equal light-mode base, ansi_15 (br white) should equal light-mode low."""
        palette = derive_palette(self.sources, mode="dark")
        light = palette["light"]
        for mode_name in ("dark", "light"):
            tokens = palette[mode_name]
            assert tokens["ansi_7"] == light["base"], (
                f"{mode_name}: ansi_7 ({tokens['ansi_7']}) != light.base ({light['base']})"
            )
            assert tokens["ansi_15"] == light["low"], (
                f"{mode_name}: ansi_15 ({tokens['ansi_15']}) != light.low ({light['low']})"
            )

    def test_ansi_1_is_reddish(self) -> None:
        """ANSI red slot should have dominant red component."""
        palette = derive_palette(self.sources, mode="dark")
        for mode_name in ("dark", "light"):
            r, g, b = hex_to_rgb(palette[mode_name]["ansi_1"])
            assert r > g, f"{mode_name}.ansi_1 ({palette[mode_name]['ansi_1']}): R={r} <= G={g}"
            assert r > b, f"{mode_name}.ansi_1 ({palette[mode_name]['ansi_1']}): R={r} <= B={b}"

    def test_ansi_bright_differs_from_regular(self) -> None:
        """Bright variant should differ from regular for all chromatic slots."""
        palette = derive_palette(self.sources, mode="dark")
        for slot in range(1, 7):
            for mode_name in ("dark", "light"):
                reg = palette[mode_name][f"ansi_{slot}"]
                bri = palette[mode_name][f"ansi_{slot + 8}"]
                assert reg != bri, (
                    f"{mode_name}.ansi_{slot} ({reg}) == bright ({bri})"
                )

    def test_ansi_bright_lighter_in_dark_mode(self) -> None:
        """In dark mode, bright variants should be lighter than regular for most slots."""
        from terratheme.palette.color_utils import relative_luminance

        palette = derive_palette(self.sources, mode="dark")
        # Slots 1-6 should all have bright lighter than regular in dark mode
        # (slot 4 has +0.02 reg vs +0.18 bright, slot 1/2/3/5/6 have -0.08 reg vs +0.10 bright)
        for slot in range(1, 7):
            reg = hex_to_rgb(palette["dark"][f"ansi_{slot}"])
            bri = hex_to_rgb(palette["dark"][f"ansi_{slot + 8}"])
            reg_lum = relative_luminance(*reg)
            bri_lum = relative_luminance(*bri)
            assert bri_lum > reg_lum, (
                f"dark.ansi_{slot}: bright ({bri_lum:.3f}) not lighter "
                f"than regular ({reg_lum:.3f})"
            )
