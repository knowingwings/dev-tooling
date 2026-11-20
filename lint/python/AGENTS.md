## Python (this repo)

### Environment
- Use `uv run <cmd>` for everything. Add dependencies with `uv add` (or `uv add --dev`), never `pip install`.

### Checks to run
1. `uv run ruff check --fix . && uv run ruff format .`
2. `uv run pyright`
3. `uv run pytest` (hardware tests are deselected; `pytest -m hardware` touches devices: see Hardware safety)

### Conventions
- Type hints on every function. Tests that need a device are marked `@pytest.mark.hardware`.
- Don't edit the `[tool.*]` sections of `pyproject.toml` to pass a check.
