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
            "back", "base", "front", "top",
            "standard", "muted",
            "c0", "c1", "c2", "c3", "c4",
            "on_c0", "on_c1", "on_c2", "on_c3", "on_c4",
            "error", "on_error",
            "outline",
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

    def test_mode_sensitive_tokens_differ(self) -> None:
        """Backgrounds, text, and outlines differ per mode.

        Raw source colours (c0-c4), error base, and on_error are the
        same in both modes — error is always a dark red regardless
        of mode, so on_error is always light for readability.
        """
        palette = derive_palette(self.sources, mode="dark")
        dark = palette["dark"]
        light = palette["light"]

        # Should differ between modes
        mode_sensitive = {"back", "base", "front", "top", "standard", "muted",
                          "outline"}
        for name in mode_sensitive:
            assert dark[name] != light[name], (
                f"token {name} is identical across modes: {dark[name]}"
            )

        # Should be identical between modes (raw source or fixed derivation)
        mode_stable = {"c0", "c1", "c2", "c3", "c4", "error", "on_error",
                       "on_c0", "on_c1", "on_c2", "on_c3", "on_c4"}
        for name in mode_stable:
            assert dark[name] == light[name], (
                f"token {name} differs across modes: dark={dark[name]} light={light[name]}"
            )

    def test_backgrounds_ordered_correctly(self) -> None:
        from terratheme.palette.color_utils import relative_luminance

        palette = derive_palette(self.sources, mode="dark")
        # In dark mode: back < base < front < top (all low luminance)
        names = ["back", "base", "front", "top"]
        values = [relative_luminance(*hex_to_rgb(palette["dark"][n])) for n in names]
        eps = 0.005  # HSL lightness is strictly ordered; WCAG luminance
                       # can invert for very close tones with different hues
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1] + eps, (
                f"dark bg {names[i]} ({values[i]:.3f}) > {names[i + 1]} ({values[i + 1]:.3f})"
            )

        palette = derive_palette(self.sources, mode="light")
        values = [relative_luminance(*hex_to_rgb(palette["light"][n])) for n in names]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1] + eps, (
                f"light bg {names[i]} ({values[i]:.3f}) > {names[i + 1]} ({values[i + 1]:.3f})"
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
        """Error should have a strong red component (blended toward c0)."""
        palette = derive_palette(self.sources, mode="dark")
        r, g, b = hex_to_rgb(palette["dark"]["error"])
        assert r > g * 1.5, f"error {palette['dark']['error']} not reddish enough"
        assert r > b * 1.5, f"error {palette['dark']['error']} not reddish enough"

    def test_outline_differs_from_backgrounds(self) -> None:
        palette = derive_palette(self.sources, mode="dark")
        outline = hex_to_rgb(palette["dark"]["outline"])
        for bg_name in ("back", "base", "front", "top"):
            bg = hex_to_rgb(palette["dark"][bg_name])
            # Should be visibly different from each background
            diff = sum(abs(outline[i] - bg[i]) for i in range(3))
            assert diff > 10, f"outline too close to {bg_name}: diff={diff}"
