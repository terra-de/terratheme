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
        block = f"\033[38;2;{r};{g};{b}m\u25a0\033[0m"
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        print(f"  {block}  {hex_code}")
    print()


def _load_palette(path: Path | None = None) -> dict:
    """Read a v2 palette JSON from disk (default ``~/.config/terra/palette.json``)."""
    if path is None:
        path = Path.home() / ".config/terra/palette.json"
    if not path.exists():
        print(f"error: palette not found at {path}", file=sys.stderr)
        print("  Run 'terratheme generate <image>' or 'terratheme set <image>' first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def _apply_targets(
    palette: dict,
    mode: str,
    target_names: list[str] | None = None,
) -> None:
    """Apply targets (or all if *target_names* is ``None`` / empty)."""
    from terratheme.targets import get_target, list_targets, render_all

    if target_names:
        for name in target_names:
            target = get_target(name)
            target.write(palette, mode)
    else:
        render_all(palette, mode)


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
    #                       [--targets LIST] [--no-apply]
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
    set_.add_argument(
        "--no-apply", action="store_true",
        help="Skip applying targets after palette generation",
    )
    set_.add_argument(
        "--targets",
        help="Comma-separated list of targets to apply (default: all)",
    )

    # terratheme apply [target ...] [--mode dark|light]
    apply_ = sub.add_parser("apply", help="Apply targets from existing palette")
    apply_.add_argument(
        "targets", nargs="*",
        help="Target(s) to apply (default: all registered targets)",
    )
    apply_.add_argument(
        "--mode", choices=("dark", "light"),
        help="Override the mode stored in the palette file",
    )

    # terratheme list-targets
    sub.add_parser("list-targets", help="List available output targets")

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
        palette = _load_palette()

    # 3. Persist to Quickshell runtime state
    update_runtime_state(args.image, dark_mode=(detected_mode == "dark"))

    # 4. Apply targets (unless --no-apply)
    if not args.no_apply:
        target_names = (
            [t.strip() for t in args.targets.split(",") if t.strip()]
            if args.targets
            else None
        )
        print("  applying targets …", file=sys.stderr)
        _apply_targets(palette, detected_mode, target_names)


def run_apply(args: argparse.Namespace) -> None:
    palette = _load_palette()
    mode: str = args.mode if args.mode else palette["mode"]
    _apply_targets(palette, mode, args.targets or None)


def run_list_targets(args: argparse.Namespace) -> None:  # noqa: ARG001
    from terratheme.targets import list_targets

    targets = list_targets()
    if not targets:
        print("no targets registered", file=sys.stderr)
        return
    print("Available targets:\n")
    for t in targets:
        print(f"  {t['name']:20s}  {t['description']}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    command_map = {
        "extract": run_extract,
        "generate": run_generate,
        "set": run_set,
        "apply": run_apply,
        "list-targets": run_list_targets,
    }

    handler = command_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
