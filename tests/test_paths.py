import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from git_portable_paths.cli import annotation
from git_portable_paths.core import InputError, audit, git_paths, utf16_units


def git(root, *args, data=None):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        input=data,
        capture_output=True,
        timeout=15,
        check=True,
    ).stdout.strip()


def make_tree(root, names):
    """Create raw Git tree objects; no checkout or fixture commit is necessary."""
    blob = git(root, "hash-object", "-w", "--stdin", data=b"synthetic\n").decode()
    entries = b"".join(b"100644 blob " + blob.encode() + b"\t" + name + b"\0" for name in names)
    return git(root, "mktree", "-z", data=entries).decode()


class RuleTests(unittest.TestCase):
    def codes(self, *paths, **options):
        return set(audit(list(paths), **options)["counts"])

    def test_clean_paths(self):
        self.assertTrue(audit(["README.md", "src/tool.py", "docs/中文.md"])["valid"])

    def test_device_names_in_all_components(self):
        for device in ("CON", "aux.txt", "nul.tar.gz", "COM9", "LPT¹.log", "COM²", "CONIN$"):
            with self.subTest(device=device):
                self.assertIn("windows_device", self.codes("dir/" + device + "/child"))
        self.assertNotIn("windows_device", self.codes("COM10.txt", "console.txt"))

    def test_forbidden_characters_and_controls(self):
        for char in '<>:"\\|?*\x00\x01\n':
            with self.subTest(char=char):
                self.assertIn("windows_character", self.codes("a" + char + "b"))

    def test_trailing_dot_and_space(self):
        for path in ("a.", "a ", "dir./child"):
            self.assertIn("trailing_dot_or_space", self.codes(path))

    def test_case_collision_files(self):
        self.assertIn("name_collision", self.codes("README.md", "Readme.md"))

    def test_case_collision_parent_directories(self):
        result = audit(["Docs/a.md", "docs/b.md"])
        self.assertEqual(result["counts"], {"name_collision": 1})
        self.assertEqual(result["issues"][0]["path"], "docs")

    def test_file_directory_collision(self):
        self.assertIn("file_directory_collision", self.codes("A", "a/child"))
        self.assertIn("file_directory_collision", self.codes("a", "a/child"))

    def test_unicode_normalization_collision(self):
        self.assertIn("name_collision", self.codes("café.txt", "cafe\u0301.txt"))

    def test_unicode_casefold_policy(self):
        self.assertIn("name_collision", self.codes("Straße/a", "STRASSE/b"))

    def test_trailing_alias_collision(self):
        self.assertIn("name_collision", self.codes("a", "a."))

    def test_utf16_budget_counts_astral_characters(self):
        self.assertEqual(utf16_units("a😀"), 3)
        self.assertIn("path_budget", self.codes("😀😀", max_path_units=3))
        self.assertNotIn("path_budget", self.codes("😀😀", max_path_units=4))

    def test_root_budget(self):
        self.assertIn("path_budget", self.codes("a/b", max_path_units=6, root_units=4))

    def test_component_budget(self):
        self.assertIn("component_budget", self.codes("x" * 256, max_path_units=1000))

    def test_non_relative_components(self):
        for path in ("", "/absolute", "a/../b", "./a", "a//b"):
            with self.subTest(path=path):
                self.assertIn("non_relative_path", self.codes(path))

    def test_git_metadata_alias(self):
        self.assertIn("git_metadata_alias", self.codes(".GiT/config"))

    def test_non_utf8_paths(self):
        result = audit([b"bad-\xff.txt"])
        self.assertEqual(result["counts"], {"non_utf8_path": 1})
        self.assertNotIn("\ufffd", result["issues"][0]["path"])

    def test_unpaired_surrogate(self):
        self.assertIn("invalid_unicode", self.codes("a\ud800"))

    def test_dedup_and_deterministic_order(self):
        paths = ["A", "a", "a", "b."]
        self.assertEqual(audit(paths), audit(list(reversed(paths))))
        self.assertEqual(audit(paths)["counts"]["name_collision"], 1)

    def test_issue_limit_preserves_total(self):
        result = audit(["AUX", "NUL", "CON"], max_issues=1)
        self.assertEqual(result["error_count"], 3)
        self.assertEqual(result["issues_omitted"], 2)

    def test_annotation_injection_is_escaped(self):
        line = annotation({"code": "windows_character", "path": "a%,:\r\n::warning::\x1b.txt"})
        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)
        self.assertNotIn("\x1b", line)
        self.assertIn("%25%2C%3A%0D%0A", line)

    def test_invalid_limits(self):
        for options in ({"max_path_units": 0}, {"root_units": -1}, {"max_issues": -1}):
            with self.assertRaises(InputError):
                audit([], **options)


class GitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        git(self.root, "init", "-b", "main")

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "git_portable_paths", str(self.root), *args],
            capture_output=True,
            timeout=20,
        )

    def test_raw_tree_illegal_on_host(self):
        tree = make_tree(
            self.root, [b"AUX.txt", b"Readme.md", b"README.md", b"colon:name", b"line\nbreak"]
        )
        paths = git_paths(self.root, tree)
        self.assertEqual(len(paths), 5)
        result = self.cli("--ref", tree, "--format", "json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("windows_device", json.loads(result.stdout)["counts"])
        self.assertEqual(list(self.root.iterdir()), [self.root / ".git"])

    def test_clean_tree(self):
        tree = make_tree(self.root, [b"README.md", b"normal.txt"])
        result = self.cli("--ref", tree, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_bare_repository_tree(self):
        bare = self.root / "remote.git"
        git(self.root, "init", "--bare", str(bare))
        tree = make_tree(bare, [b"NUL"])
        self.assertIn("windows_device", audit(git_paths(bare, tree))["counts"])
        with self.assertRaisesRegex(InputError, "bare_repository_requires_ref"):
            git_paths(bare)

    def test_index_with_unmaterialized_paths(self):
        blob = git(self.root, "hash-object", "-w", "--stdin", data=b"x").decode()
        git(
            self.root,
            "-c",
            "core.protectNTFS=false",
            "update-index",
            "--add",
            "--cacheinfo",
            f"100644,{blob},AUX.txt",
        )
        self.assertEqual(git_paths(self.root), [b"AUX.txt"])
        self.assertFalse((self.root / "AUX.txt").exists())

    def test_index_from_nested_directory_covers_root(self):
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "b.txt").write_text("y", encoding="utf-8")
        git(self.root, "add", ".")
        self.assertEqual(git_paths(nested), [b"a.txt", b"nested/b.txt"])

    def test_index_does_not_follow_symlinks(self):
        blob = git(self.root, "hash-object", "-w", "--stdin", data=b"../outside").decode()
        git(self.root, "update-index", "--add", "--cacheinfo", f"120000,{blob},link")
        self.assertTrue(audit(git_paths(self.root))["valid"])

    def test_inherited_git_dir_does_not_override_target(self):
        original = os.environ.get("GIT_DIR")
        os.environ["GIT_DIR"] = str(self.root / "missing")
        try:
            self.assertEqual(git_paths(self.root), [])
        finally:
            if original is None:
                del os.environ["GIT_DIR"]
            else:
                os.environ["GIT_DIR"] = original

    def test_invalid_ref_cannot_inject_options(self):
        result = self.cli("--ref=--output=UNEXPECTED_FILE", "--format", "json")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "UNEXPECTED_FILE").exists())

    def test_invalid_repository(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(InputError):
            git_paths(Path(directory))

    def test_version(self):
        self.assertEqual(self.cli("--version").stdout.strip(), b"0.1.0")


if __name__ == "__main__":
    unittest.main()
