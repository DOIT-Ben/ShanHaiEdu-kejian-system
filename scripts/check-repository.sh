#!/usr/bin/env bash
# Shell entry points must remain LF-only for Git Bash and Linux CI.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

git diff --check
if [[ -x "$repo_root/.venv/Scripts/python.exe" ]]; then
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

"$repository_python" scripts/build_frontend_package.py --check
unzip -t deliverables/shanhaiedu-frontend-package.zip >/dev/null
package_dir=$(mktemp -d "${TMPDIR:-/tmp}/shanhaiedu-package-check.XXXXXX")
trap 'rm -rf "$package_dir"' EXIT
unzip -q deliverables/shanhaiedu-frontend-package.zip -d "$package_dir"
(
  cd "$package_dir/shanhaiedu-frontend-package"
  sha256sum -c --quiet CHECKSUMS.sha256
)

echo "repository contracts, documents, checksums and archive are valid"
