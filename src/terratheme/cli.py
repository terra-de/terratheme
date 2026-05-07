"""CLI entry point for terratheme."""

from __future__ import annotations

import argparse
import json
import sys


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

    # terratheme generate <image> [--mode dark|light|auto] [--visualize]
    gen = sub.add_parser("generate", help="Generate a full palette from an image")
    gen.add_argument("image", help="Path to a wallpaper image")
    gen.add_argument(
        "--mode", choices=("dark", "light", "auto"), default="auto",
        help="Force a palette mode (default: auto-detect from source colours)",
    )
    gen.add_argument(
        "--visualize", "-v", action="store_true",
        help="Display a terminal UI mockup instead of JSON output",
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
    else:
        print(json.dumps(palette, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "extract":
        run_extract(args)
    elif args.command == "generate":
        run_generate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
