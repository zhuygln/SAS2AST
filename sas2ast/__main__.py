"""CLI entry point for sas2ast.

Usage:
  python -m sas2ast parse FILE [--format tree|json|rich|html|summary] [--output FILE]
  python -m sas2ast analyze FILE [--format tree|json|rich|html|summary|dot] [--output FILE]
  python -m sas2ast batch DIR [--format summary|json] [--output FILE]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

from sas2ast._version import __version__


def _parse_cmd(args: argparse.Namespace) -> int:
    """Handle the 'parse' subcommand."""
    from sas2ast.parser import parse
    from sas2ast.formatters import get_formatter

    source = _read_file(args.file)
    if source is None:
        return 1

    result = parse(source)

    fmt_name = args.format or "tree"
    formatter = _get_formatter_safe(fmt_name)
    if formatter is None:
        return 1

    filename = os.path.basename(args.file)
    output = formatter.format_ast(result, filename=filename)
    _write_output(output, args.output)
    return 0


def _analyze_cmd(args: argparse.Namespace) -> int:
    """Handle the 'analyze' subcommand."""
    from sas2ast.analyzer import analyze
    from sas2ast.formatters import get_formatter

    source = _read_file(args.file)
    if source is None:
        return 1

    graph = analyze(source)

    fmt_name = args.format or "summary"

    # Handle dot format specially via existing exporter
    if fmt_name == "dot":
        from sas2ast.analyzer.exporters import to_dot
        output = to_dot(graph)
        _write_output(output, args.output)
        return 0

    formatter = _get_formatter_safe(fmt_name)
    if formatter is None:
        return 1

    filename = os.path.basename(args.file)
    output = formatter.format_graph(graph, filename=filename)
    _write_output(output, args.output)
    return 0


def _batch_cmd(args: argparse.Namespace) -> int:
    """Handle the 'batch' subcommand."""
    from sas2ast.parser import parse
    from sas2ast.analyzer import analyze
    from sas2ast.formatters import get_formatter

    directory = args.directory
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        return 1

    # Glob for .sas files recursively
    sas_files = sorted(glob.glob(os.path.join(directory, "**", "*.sas"), recursive=True))
    if not sas_files:
        print(f"No .sas files found in {directory}", file=sys.stderr)
        return 1

    fmt_name = args.format or "summary"
    formatter = _get_formatter_safe(fmt_name)
    if formatter is None:
        return 1

    outputs = []
    errors = 0
    for filepath in sas_files:
        try:
            source = Path(filepath).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
            errors += 1
            continue

        relpath = os.path.relpath(filepath, directory)

        if fmt_name == "json":
            graph = analyze(source)
            output = formatter.format_graph(graph, filename=relpath)
            outputs.append(output)
        else:
            # Default: summary of both parse and analyze
            result = parse(source)
            output = formatter.format_ast(result, filename=relpath)
            outputs.append(output)

    final = "\n\n".join(outputs)
    if errors:
        final += f"\n\n({errors} file(s) could not be read)"
    _write_output(final, args.output)
    return 0


def _read_file(filepath: str) -> str | None:
    """Read a file, returning None on error."""
    try:
        return Path(filepath).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return None
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error: Could not read {filepath}: {e}", file=sys.stderr)
        return None


def _get_formatter_safe(name: str):
    """Import a formatter, printing errors on failure."""
    from sas2ast.formatters import get_formatter
    try:
        return get_formatter(name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None
    except ImportError as e:
        print(f"Error: Could not load formatter {name!r}: {e}", file=sys.stderr)
        return None


def _write_output(text: str, output_path: str | None) -> None:
    """Write text to stdout or a file."""
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        print(f"Written to {output_path}", file=sys.stderr)
    else:
        print(text)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sas2ast",
        description="Parse SAS code into AST and dependency graphs",
    )
    parser.add_argument("--version", action="version", version=f"sas2ast {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # parse subcommand
    parse_parser = subparsers.add_parser("parse", help="Parse a SAS file into an AST")
    parse_parser.add_argument("file", help="Path to SAS file")
    parse_parser.add_argument(
        "--format", "-f",
        choices=["tree", "json", "rich", "html", "summary"],
        default=None,
        help="Output format (default: tree)",
    )
    parse_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write output to file instead of stdout",
    )

    # analyze subcommand
    analyze_parser = subparsers.add_parser("analyze", help="Analyze dependencies in a SAS file")
    analyze_parser.add_argument("file", help="Path to SAS file")
    analyze_parser.add_argument(
        "--format", "-f",
        choices=["tree", "json", "rich", "html", "summary", "dot"],
        default=None,
        help="Output format (default: summary)",
    )
    analyze_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write output to file instead of stdout",
    )

    # batch subcommand
    batch_parser = subparsers.add_parser("batch", help="Process all .sas files in a directory")
    batch_parser.add_argument("directory", help="Directory containing SAS files")
    batch_parser.add_argument(
        "--format", "-f",
        choices=["summary", "json"],
        default=None,
        help="Output format (default: summary)",
    )
    batch_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write output to file instead of stdout",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "parse":
        return _parse_cmd(args)
    elif args.command == "analyze":
        return _analyze_cmd(args)
    elif args.command == "batch":
        return _batch_cmd(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
