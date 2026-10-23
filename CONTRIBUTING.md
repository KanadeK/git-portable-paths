# Contributing

Report reproducible bugs and focused proposals through GitHub Issues. Use
synthetic examples and remove personal data. Keep runtime dependencies empty
unless an accepted design change justifies one.

With Python 3.11+ in a virtual environment:

```sh
python -m pip install -e . ruff==0.17.2 build==1.6.1
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
python -m build
```

CI checks Windows, Linux and macOS on Python 3.11 and 3.13. It has read-only
repository permissions and never commits changes. Changes are reviewed by
the maintainer; no automatic dependency-update commits or PR merges are enabled.
Preserve third-party copyrights if you propose third-party code.
