"""Conservative portability rules applied to Git path bytes, without checkout."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

MAX_PATHS = 100_000
MAX_LISTING = 64 * 1024 * 1024
RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³"
}


class InputError(ValueError):
    """An input or Git operation failed; messages are fixed error codes."""


def utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


def canonical(component: str) -> str:
    return unicodedata.normalize("NFC", component).casefold().rstrip(" .")


def git_paths(repo: Path, ref: str | None = None) -> list[bytes]:
    """Read index by default, or any committed tree including a bare repository."""
    executable = shutil.which("git")
    if executable is None:
        raise InputError("git_not_found")
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    # The selected repository must determine object/index paths, not an inherited
    # environment from a parent hook or a caller inspecting another repository.
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
    ):
        env.pop(key, None)

    def run(arguments):
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(  # noqa: S603 - fixed Git executable, argv, no shell
                    [executable, "-C", str(repo.resolve()), *arguments],
                    stdout=output,
                    stderr=subprocess.PIPE,
                    env=env,
                    timeout=30,
                    check=False,
                )
                if result.returncode:
                    raise InputError("git_failed")
                if output.tell() > MAX_LISTING:
                    raise InputError("listing_too_large")
                output.seek(0)
                return output.read()
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            if isinstance(error, InputError):
                raise
            raise InputError("git_unavailable_or_timeout") from None

    if ref is None:
        # Bare indexes would misleadingly report an empty repository.
        if run(["rev-parse", "--is-bare-repository"]).strip() == b"true":
            raise InputError("bare_repository_requires_ref")
        output = run(["ls-files", "--cached", "--deduplicate", "-z", "--full-name", "--", ":/"])
    else:
        if not ref or "\0" in ref:
            raise InputError("invalid_ref")
        tree = run(["rev-parse", "--verify", "--end-of-options", ref + "^{tree}"]).strip()
        if not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", tree):
            raise InputError("invalid_tree")
        output = run(
            ["ls-tree", "-r", "-z", "--name-only", "--full-tree", tree.decode("ascii"), "--"]
        )
    paths = output.split(b"\0")
    if paths and paths[-1] == b"":
        paths.pop()
    if len(paths) > MAX_PATHS:
        raise InputError("too_many_paths")
    return paths


def audit(paths: list[bytes | str], *, max_path_units=240, root_units=0, max_issues=200) -> dict:
    """Audit spelling and node collisions. This never accesses any listed file."""
    if max_path_units < 1 or root_units < 0 or max_issues < 0 or len(paths) > MAX_PATHS:
        raise InputError("invalid_limits")
    report = {"valid": True, "paths": len(paths), "error_count": 0, "issues": [], "counts": {}}
    nodes = {}
    full_paths = set()

    def add(code, path, related=None):
        report["valid"] = False
        report["error_count"] += 1
        report["counts"][code] = report["counts"].get(code, 0) + 1
        if len(report["issues"]) < max_issues:
            item = {"code": code, "path": path}
            if related is not None:
                item["related"] = related
            report["issues"].append(item)

    # Git supplies deterministic ordering, but API callers need not do so.
    for raw in sorted(
        paths, key=lambda p: p.encode("utf-8", "surrogatepass") if isinstance(p, str) else p
    ):
        if isinstance(raw, bytes):
            try:
                path = raw.decode("utf-8")
            except UnicodeError:
                add("non_utf8_path", raw.decode("utf-8", errors="backslashreplace"))
                continue
        else:
            path = raw
        if any(0xD800 <= ord(char) <= 0xDFFF for char in path):
            add("invalid_unicode", path)
            continue
        if path in full_paths:
            continue
        full_paths.add(path)
        parts = path.split("/")
        if not path or path.startswith("/") or any(p in ("", ".", "..") for p in parts):
            add("non_relative_path", path)
            continue
        if utf16_units(path) + root_units > max_path_units:
            add("path_budget", path)
        for i, part in enumerate(parts):
            prefix = "/".join(parts[: i + 1])
            if any(ord(char) < 32 or char in '<>:"\\|?*' for char in part):
                add("windows_character", prefix)
            if part.endswith((" ", ".")):
                add("trailing_dot_or_space", prefix)
            if part.split(".", 1)[0].rstrip(" ").upper() in RESERVED:
                add("windows_device", prefix)
            if utf16_units(part) > 255:
                add("component_budget", prefix)
            if canonical(part) == ".git":
                add("git_metadata_alias", prefix)
            key = tuple(canonical(p) for p in parts[: i + 1])
            kind = "file" if i == len(parts) - 1 else "directory"
            if key not in nodes:
                nodes[key] = {"first": prefix, "spellings": {prefix}, "kinds": {kind}}
                continue
            node = nodes[key]
            if prefix not in node["spellings"]:
                add("name_collision", prefix, node["first"])
                node["spellings"].add(prefix)
            if kind not in node["kinds"]:
                add("file_directory_collision", prefix, node["first"])
                node["kinds"].add(kind)
    report["counts"] = dict(sorted(report["counts"].items()))
    report["issues_omitted"] = report["error_count"] - len(report["issues"])
    return report
