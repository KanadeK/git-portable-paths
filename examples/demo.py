"""Audit bad path names without creating them on the host filesystem."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    executable = shutil.which("git")
    if executable is None:
        raise SystemExit("Git is required")
    with tempfile.TemporaryDirectory(prefix="git-paths-demo-") as directory:
        root = Path(directory)

        def git(*arguments, data=None):
            return subprocess.run(  # noqa: S603,S607 - fixed Git command and argv
                [executable, "-C", str(root), *arguments],
                input=data,
                capture_output=True,
                check=True,
                timeout=15,
            ).stdout.strip()

        git("init", "--bare")
        blob = git("hash-object", "-w", "--stdin", data=b"demo\n")
        names = [
            b"AUX.txt",
            b"README.md",
            b"Readme.md",
            "cafe\u0301.txt".encode(),
            "café.txt".encode(),
        ]
        tree = git(
            "mktree", "-z", data=b"".join(b"100644 blob " + blob + b"\t" + n + b"\0" for n in names)
        ).decode()
        result = subprocess.run(  # noqa: S603 - module CLI, no shell
            [
                sys.executable,
                "-m",
                "git_portable_paths",
                str(root),
                "--ref",
                tree,
                "--format",
                "json",
            ],
            check=False,
            timeout=30,
        )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
