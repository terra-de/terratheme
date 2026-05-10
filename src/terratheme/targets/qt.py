"""Qt target — writes KDE colour scheme to ``~/.local/share/color-schemes/Matugen.colors``.

Used by qt5ct / qt6ct with ``custom_palette=true``.
"""

from __future__ import annotations

from .base import BaseTarget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_rgb(hex_str: str) -> str:
    """Convert ``#rrggbb`` to ``R,G,B`` decimal (KDE colorscheme format)."""
    h = hex_str.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"


# ---------------------------------------------------------------------------
# Section definitions: {section: {property: token}}
# ---------------------------------------------------------------------------
_SECTIONS: dict[str, dict[str, str]] = {
    "ColorEffects:Disabled": {
        "Color": "base",
        "ColorAmount": "0",
        "ColorEffect": "0",
        "ContrastAmount": "0.65",
        "ContrastEffect": "1",
        "IntensityAmount": "0.1",
        "IntensityEffect": "2",
    },
    "ColorEffects:Inactive": {
        "ChangeSelectionColor": "true",
        "Color": "base",
        "ColorAmount": "0.025",
        "ColorEffect": "2",
        "ContrastAmount": "0.1",
        "ContrastEffect": "2",
        "Enable": "false",
        "IntensityAmount": "0",
        "IntensityEffect": "0",
    },
    "Colors:Button": {
        "BackgroundAlternate": "low",
        "BackgroundNormal": "top",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c4",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c3",
        "ForegroundNormal": "standard",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "Colors:Complementary": {
        "BackgroundAlternate": "low",
        "BackgroundNormal": "base",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c2",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c3",
        "ForegroundNormal": "standard",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "Colors:Header": {
        "BackgroundAlternate": "base",
        "BackgroundNormal": "high",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c2",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c3",
        "ForegroundNormal": "standard",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "Colors:Header[Inactive]": {
        "BackgroundAlternate": "base",
        "BackgroundNormal": "base",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c2",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c3",
        "ForegroundNormal": "standard",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "Colors:Selection": {
        "BackgroundAlternate": "base",
        "BackgroundNormal": "c4",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "on_c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c2",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c1",
        "ForegroundNormal": "on_c4",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "Colors:Tooltip": {
        "BackgroundAlternate": "base",
        "BackgroundNormal": "high",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c2",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c3",
        "ForegroundNormal": "standard",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "Colors:View": {
        "BackgroundAlternate": "high",
        "BackgroundNormal": "base",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c2",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c3",
        "ForegroundNormal": "standard",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "Colors:Window": {
        "BackgroundAlternate": "base",
        "BackgroundNormal": "high",
        "DecorationFocus": "c4",
        "DecorationHover": "c4",
        "ForegroundActive": "c4",
        "ForegroundInactive": "muted",
        "ForegroundLink": "c2",
        "ForegroundNegative": "error",
        "ForegroundNeutral": "c3",
        "ForegroundNormal": "standard",
        "ForegroundPositive": "c3",
        "ForegroundVisited": "standard",
    },
    "WM": {
        "activeBackground": "c4",
        "activeBlend": "on_c4",
        "activeForeground": "on_c4",
        "inactiveBackground": "base",
        "inactiveBlend": "standard",
        "inactiveForeground": "standard",
    },
}

class QtTarget(BaseTarget):
    """Generate a KDE colour scheme at ``~/.local/share/color-schemes/Matugen.colors``.

    The dotfiles reference this file in both qt5ct and qt6ct config files:
      color_scheme_path=~/.local/share/color-schemes/Matugen.colors
    """

    name = "qt"
    description = "KDE Qt colour scheme"
    output_path = "~/.local/share/color-schemes/Matugen.colors"

    def render(self, palette: dict, mode: str) -> str:
        colors = palette[mode]
        lines: list[str] = []

        for section_name, props in _SECTIONS.items():
            lines.append(f"[{section_name}]")
            for prop, token in props.items():
                # Resolve to R,G,B decimal (KDE colorscheme format) if token
                # exists in palette, otherwise pass through as literal
                # ("0", "true", "0.65", etc.)
                if token in colors:
                    lines.append(f"{prop}={_to_rgb(colors[token])}")
                else:
                    lines.append(f"{prop}={token}")
            lines.append("")

        # Metadata sections
        lines.append("[General]")
        lines.append("ColorScheme=Matugen")
        lines.append("Name=Matugen")
        lines.append("")
        lines.append("[Appearance]")
        lines.append("color_scheme=Matugen")
        lines.append("")
        lines.append("[KDE]")
        lines.append("contrast=4")
        lines.append("")

        return "\n".join(lines)
