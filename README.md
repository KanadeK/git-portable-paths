# git-portable-paths

[![CI](https://github.com/KanadeK/git-portable-paths/actions/workflows/ci.yml/badge.svg)](https://github.com/KanadeK/git-portable-paths/actions/workflows/ci.yml)

Catch paths that break cross-platform Git checkouts **before checking them out**.
Audit the index or a committed tree, including a bare repository. Python 3.11+,
Git 2.31+, no Python runtime package dependencies. [中文说明](README.zh-CN.md)

A Linux contributor can add `AUX.txt`, both `README.md` and `Readme.md`, or two
Unicode spellings of the same name. A Windows/macOS colleague may then be unable
to check out that tree. This command reads path bytes from Git, checks parent
directories as well as files, and produces actionable positional-free path
diagnostics. It never renames, checks out, opens or follows the listed files.

## Install and run

```sh
git clone https://github.com/KanadeK/git-portable-paths.git
cd git-portable-paths
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell instead: .\.venv\Scripts\Activate.ps1
python -m pip install .
git-portable-paths . --ref HEAD --format json
python examples/demo.py
```

The self-audit exits **0**. The demo intentionally exits **1** and reports three
findings: a Windows device name, a case collision, and a Unicode normalization
collision. It creates a temporary bare Git repository and writes objects only;
the problematic paths are never created on disk. All temporary objects are
removed when the process exits normally. No credentials or fixture commits are
needed. The demo's source is included in repository and source releases.

If activation is restricted, use `.venv\Scripts\python.exe -m git_portable_paths`
on Windows or `.venv/bin/python -m git_portable_paths` on Unix. This project is
installed from the repository; no PyPI publication is implied.

For your own repository (quote paths containing spaces):

```sh
git-portable-paths /path/to/repo --index
git-portable-paths /path/to/repo --ref main --format json
git-portable-paths /path/to/bare.git --ref main --format json
git-portable-paths . --ref HEAD --root-units 60 --max-path-units 240
```

The default is `--index`: all tracked paths in the index, including staged new
paths and paths absent from the working tree. A bare repository requires
`--ref`. Tree refs can be commits, tags or tree IDs; they resolve to a verified
tree object before listing. Untracked files, submodule contents, symlink targets
and other branches are not scanned. A Git failure exits **2**, including a
missing ref or missing Git executable. An empty index is valid.

## Checks and policy

| Code | Meaning |
|---|---|
| `windows_device` | Reserved device basename in any component, including extensions and superscript COM/LPT digits |
| `windows_character` | Windows-forbidden punctuation or control characters |
| `trailing_dot_or_space` | A component ends in an ASCII space or period |
| `name_collision` | Distinct file/directory spellings share a normalized comparison key |
| `file_directory_collision` | A file and directory occupy the same comparison key |
| `component_budget` | A component exceeds 255 UTF-16 code units |
| `path_budget` | Relative path plus configured root budget exceeds the chosen UTF-16 budget |
| `git_metadata_alias` | A component normalizes to `.git` |
| `non_utf8_path` / `invalid_unicode` | Path cannot be represented as valid Unicode under this policy |
| `non_relative_path` | Empty, absolute, dot or parent component (library input) |

Comparison policy is NFC normalization, Unicode `casefold`, then trailing ASCII
space/dot removal, component by component. This deliberately conservative rule
is **not an exact NTFS/APFS/HFS+ simulator**; e.g. `Straße`/`STRASSE` may be flagged
even where a specific filesystem distinguishes them. Git doesn't require UTF-8;
this project deliberately flags non-UTF-8 names for portable sharing. Their
bytes are escaped rather than replaced silently.

`--max-path-units` defaults to 240; `--root-units` defaults to 0 and is the budget
for the absolute checkout root **including its trailing separator**. Astral
characters consume two UTF-16 units. These budgets are advisories chosen by your
team, not a guarantee that every Windows API will accept a path. Long-path
settings, actual checkout root, filesystem-specific byte limits and 8.3 aliases
still matter. `--max-path-units 32767` can relax your relative-path policy.

## CI and hooks

Exit codes: **0** no findings, **1** findings, **2** invocation/Git failure.
`--format json` emits one JSON object. Text output uses JSON-escaped paths to
avoid terminal control injection. Findings include `path` and, for collisions,
`related`. `--max-issues 200` limits detail retention; all paths are still checked
and totals plus `issues_omitted` are reported. Zero stored details is allowed.

In a GitHub Actions job after installation:

```yaml
- run: git-portable-paths . --ref HEAD --format github
```

Annotation properties escape percent signs, separators, newlines and ASCII
controls; messages use escaped JSON. For local pre-commit use:

```yaml
repos:
  - repo: https://github.com/KanadeK/git-portable-paths
    rev: v0.1.0
    hooks:
      - id: git-portable-paths
```

No hook is installed automatically. Your index is inspected read-only;
`GIT_OPTIONAL_LOCKS=0` is set, and inherited repository/index-location overrides
are removed so the explicit repository controls the scan.

## Alternatives and limits

[pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) offers useful
case-conflict and illegal-Windows-name hooks. [pathvalidate](https://github.com/thombashi/pathvalidate)
validates individual strings. [repo-portability](https://github.com/maomao-1937/repo-portability)
also audits tracked names. This project adds committed-tree/bare-repository
inspection, normalized directory collisions, UTF-16 budgets and CI annotations
in a single dependency-free command. No competitor code is copied.

At most 100,000 listed paths and 64 MiB of Git listing output are accepted.
Each Git command has a 30-second timeout. Git output is spooled to a temporary
file before its size is checked; the listing cap is not a disk quota. Memory
scales with the listed paths and their directory prefixes. Use trusted Git and
repository configuration; this command is not a sandbox for malicious Git
installations or a general repository security scanner. It does not claim
universal filesystem compatibility or check file content.

## Develop and remove

See [CONTRIBUTING](CONTRIBUTING.md), [security reporting](SECURITY.md),
[third-party notes](THIRD_PARTY.md) and [release review](REVIEW.md).

```sh
python -m unittest discover -s tests -v
python -m pip uninstall git-portable-paths
```

No persistent cache/config is created. Delete the cloned directory and its
virtual environment to remove a source installation. MIT license, version 0.1.0.
