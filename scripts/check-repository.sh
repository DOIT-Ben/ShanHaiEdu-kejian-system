#!/usr/bin/env bash
# Shell entry points must remain LF-only for Git Bash and Linux CI.
set -euo pipefail

repo_root=$(GIT_INDEX_FILE=/dev/null GIT_OPTIONAL_LOCKS=0 git rev-parse --show-toplevel)
cd "$repo_root"
source "$repo_root/scripts/readonly_git_index.sh"
prepare_readonly_git_index
trap cleanup_readonly_git_index EXIT

git diff --check
if [[ -x "$repo_root/.venv/bin/python" ]]; then
  repository_python="$repo_root/.venv/bin/python"
elif [[ -x "$repo_root/.venv/Scripts/python.exe" ]]; then
  repository_python="$repo_root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
  repository_python=python3
elif command -v python >/dev/null 2>&1 && python --version >/dev/null 2>&1; then
  repository_python=python
else
  echo "Python 3 is required to validate the repository" >&2
  exit 1
fi
"$repository_python" scripts/check_repository.py

pnpm contracts:lint
pnpm contracts:schema

echo "repository contracts and documents are valid"
