#!/usr/bin/env bash
set -euo pipefail

repo_root="$(GIT_INDEX_FILE=/dev/null GIT_OPTIONAL_LOCKS=0 git rev-parse --show-toplevel)"
cd "$repo_root"
source "$repo_root/scripts/readonly_git_index.sh"
prepare_readonly_git_index
trap cleanup_readonly_git_index EXIT

uv run python scripts/check_linux_dev_environment.py
uv run alembic upgrade head
uv run python scripts/smoke_local_stack.py
uv run python -m workers.main --check
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest tests/unit
uv run pytest tests/integration
pnpm contracts:check
uv run python scripts/check_repository.py
uv run python scripts/check_tracked_secrets.py
git diff --check
git diff --cached --check
