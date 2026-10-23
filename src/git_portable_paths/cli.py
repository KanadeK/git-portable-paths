"""Command-line output with escaped terminal and GitHub Actions diagnostics."""

import argparse
import json
from pathlib import Path

from . import __version__
from .core import InputError, audit, git_paths


def integer(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def annotation(issue):
    def escape(value, prop=False):
        result = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        if prop:
            result = result.replace(":", "%3A").replace(",", "%2C")
            result = "".join(
                f"%{ord(c):02X}" if ord(c) < 32 or ord(c) == 127 else c for c in result
            )
        return result

    # The message is JSON-escaped too, preventing terminal escape sequences.
    message = json.dumps(issue, ensure_ascii=True, sort_keys=True)
    return f"::error file={escape(issue['path'], True)},title=Path portability::{escape(message)}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Git path portability audit.")
    parser.add_argument("repo", type=Path, nargs="?", default=Path("."))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--ref", help="commit/tag/tree to audit without checking out (works in bare repos)"
    )
    mode.add_argument("--index", action="store_true", help="audit the index (default)")
    parser.add_argument(
        "--max-path-units",
        type=integer,
        default=240,
        help="relative path plus root budget in UTF-16 units",
    )
    parser.add_argument(
        "--root-units",
        type=integer,
        default=0,
        help="budget for checkout-root prefix, including its separator",
    )
    parser.add_argument("--max-issues", type=integer, default=200)
    parser.add_argument("--format", choices=("text", "json", "github"), default="text")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    try:
        result = audit(
            git_paths(args.repo, args.ref),
            max_path_units=args.max_path_units,
            root_units=args.root_units,
            max_issues=args.max_issues,
        )
        status = 0 if result["valid"] else 1
    except (InputError, OSError) as error:
        result = {
            "valid": False,
            "error": str(error) if isinstance(error, InputError) else "io_error",
        }
        status = 2
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    elif "error" in result:
        print("ERROR: " + result["error"])
    else:
        for issue in result["issues"]:
            print(
                annotation(issue)
                if args.format == "github"
                else json.dumps(issue, ensure_ascii=True, sort_keys=True)
            )
        print(
            f"{'PASS' if result['valid'] else 'FAIL'} paths={result['paths']} errors={result['error_count']} issues_omitted={result['issues_omitted']}"
        )
    return status
