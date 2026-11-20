## Python (this repo)

### Environment
- Use `uv run <cmd>` for everything. Add dependencies with `uv add` (or `uv add --dev`), never `pip install`.

### Checks to run
- `./check` runs every check (hooks, ruff, pyright, pytest) and prints one line per step, with the failing lines
  and a log path when something fails. Paste its summary into the PR's Evidence section.
- `./check --quick` skips the slow steps while you iterate; run the full `./check` before you say
  you're done. `./check --list` shows exactly what runs.
- The commit hooks check only the files you commit. `./check` checks the whole project, and a change
  can break a file you didn't touch, so run the full `./check` before you open a PR.
- `pytest -m hardware` touches devices and is never part of `./check`: see Hardware safety.

### Conventions
- Type hints on every function. Tests that need a device are marked `@pytest.mark.hardware`.
- Don't edit the `[tool.*]` sections of `pyproject.toml` to pass a check.
