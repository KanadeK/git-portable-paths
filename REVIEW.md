# Release review: 0.1.0

Reviewed 2026-10-23 against the cross-platform checkout use case.

- Real Git-object fixtures reproduce Windows-illegal names without materializing
  them on the host. Tests run actual Git and the installed subprocess CLI.
- Index and committed-tree modes work independently; a bare repository without
  an explicit ref fails instead of misleadingly reporting a clean empty index.
- Review found that a nested current directory could restrict index coverage;
  a top-level pathspec now ensures all index paths are checked, with a regression
  test. Inherited Git repository/index overrides are removed for explicit scans.
- All ref resolution uses argument arrays and `--end-of-options`. Only a
  verified hexadecimal tree object ID reaches `ls-tree`. No shell is invoked.
- Paths use NUL-delimited Git output; non-UTF-8 bytes and terminal controls are
  escaped. GitHub annotation escaping has an injection regression case.
- Parent-directory and file/directory collisions, normalization, superscript
  device digits, astral UTF-16 lengths and diagnostic truncation are tested.
- Runtime dependencies are stdlib plus separately installed Git. Source and
  fixtures are original; no vendored source or undisclosed third-party assets.
- Limits are disclosed: conservative casefold policy, listing cap checked after
  spooling, filesystem-dependent length rules, no submodule/content inspection.

31 local tests pass on Windows/Python 3.13.16. Release gates run Ruff correctness
and security rules, formatting, builds, a clean wheel installation and all tests,
`pip check` and uninstall checks. Remote CI results are recorded by GitHub Actions,
not assumed here. No known severe issue remained after this review.
