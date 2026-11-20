# Working in this repo

## Environment
- Use `uv run <cmd>` for everything. Add dependencies with `uv add` (or `uv add --dev`), never `pip install`.

## Before you say a change is done
Run these and include a short summary of the output in your final message:

1. `uv run ruff check --fix . && uv run ruff format .`
2. `uv run pyright`
3. `uv run pytest`

## Rules
- Ruff and pyright messages say how to fix the problem. Fix the root cause.
- A `# noqa: CODE` or `# pyright: ignore[rule]` needs a short reason after it, and a mention in your summary.
- Never edit the `[tool.*]` sections of pyproject.toml to get a check passing.

## Hardware safety
- Never run `pytest -m hardware`, or any script that opens a serial/CAN port or commands a device,
  unless I ask. Use the fakes in `tests/` instead.
