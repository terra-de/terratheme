"""CLI entry point for terratheme."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def display_colors(colors: list[tuple[int, int, int]]) -> None:
    """Print extracted colours to the terminal with ANSI true-colour blocks."""
    print()
    for r, g, b in colors:
        block = f"\033[38;2;{r};{g};{b}m■\033[0m"
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        print(f"  {block}  {hex_code}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terratheme",
        description="Multi-source-color theme generator for Terra DE",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # terratheme extract <image>
    extract = sub.add_parser("extract", help="Extract dominant colours from an image")
    extract.add_argument("image", help="Path to a wallpaper image")

    # terratheme generate <image> [--mode dark|light|auto] [--visualize] [--output PATH] [--stdout]
    gen = sub.add_parser("generate", help="Generate a full palette from an image")
    gen.add_argument("image", help="Path to a wallpaper image")
    gen.add_argument(
        "--mode", choices=("dark", "light", "auto"), default="auto",
        help="Force a palette mode (default: auto-detect from source colours)",
    )
    gen.add_argument(
        "--visualize", "-v", action="store_true",
        help="Display a terminal UI mockup (no file write)",
    )
    gen.add_argument(
        "--output", "-o",
        help="Output path (default: ~/.config/terra/palette.json)",
    )
    gen.add_argument(
        "--stdout", "-s", action="store_true",
        help="Print JSON to stdout instead of writing to file",
    )

    # terratheme set <image> [--mode dark|light|auto] [--no-wallpaper] [--no-palette]
    set_ = sub.add_parser("set", help="Set wallpaper via awww and generate palette")
    set_.add_argument("image", help="Path to a wallpaper image")
    set_.add_argument(
        "--mode", choices=("dark", "light", "auto"), default="auto",
        help="Force a palette mode (default: auto-detect from source colours)",
    )
    set_.add_argument(
        "--no-wallpaper", action="store_true",
        help="Skip setting the wallpaper (palette + state only)",
    )
    set_.add_argument(
        "--no-palette", action="store_true",
        help="Skip palette generation (wallpaper + state only)",
    )

    return parser


def run_extract(args: argparse.Namespace) -> None:
    from terratheme.palette.extract import extract_colors

    colors = extract_colors(args.image)
    display_colors(colors)


def run_generate(args: argparse.Namespace) -> None:
    from terratheme.palette.extract import extract_colors
    from terratheme.palette.derive import derive_palette

    mode: str | None = None if args.mode == "auto" else args.mode
    colors = extract_colors(args.image)
    palette = derive_palette(colors, mode=mode)

    if args.visualize:
        from terratheme.visualize import visualize

        visualize(palette, args.image)
        return

    if args.stdout:
        print(json.dumps(palette, indent=2))
        return

    output_path = Path(args.output) if args.output else Path.home() / ".config/terra/palette.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(palette, indent=2))
    print(f"palette written to {output_path}", file=sys.stderr)


def run_set(args: argparse.Namespace) -> None:
    from terratheme.set_wallpaper import run_awww, update_runtime_state
    from terratheme.palette.extract import extract_colors
    from terratheme.palette.derive import derive_palette

    print(f"terratheme set {args.image}", file=sys.stderr)

    # 1. Set wallpaper via awww (unless --no-wallpaper)
    if not args.no_wallpaper:
        run_awww(args.image)

    # 2. Generate palette (unless --no-palette)
    if not args.no_palette:
        mode: str | None = None if args.mode == "auto" else args.mode
        palette = derive_palette(extract_colors(args.image), mode=mode)
        detected_mode: str = palette["mode"]  # type: ignore[typeddict-item]
        output_path = Path.home() / ".config/terra/palette.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(palette, indent=2))
        print(f"  palette: {output_path}", file=sys.stderr)
    else:
        detected_mode = args.mode if args.mode != "auto" else "dark"

    # 3. Persist to Quickshell runtime state
    update_runtime_state(args.image, dark_mode=(detected_mode == "dark"))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "extract":
        run_extract(args)
    elif args.command == "generate":
        run_generate(args)
    elif args.command == "set":
        run_set(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
