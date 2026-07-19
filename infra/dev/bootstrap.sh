#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "bootstrap must run inside the Linux workspace container" >&2
  exit 1
fi

git config --global --replace-all safe.directory /workspace
git config --global core.autocrlf input

if [[ ! -f .venv/pyvenv.cfg ]]; then
  uv venv --python /usr/local/bin/python --allow-existing .venv
fi

uv sync --frozen --python /usr/local/bin/python
pnpm install --frozen-lockfile
uv run alembic upgrade head
uv run python scripts/check_linux_dev_environment.py
