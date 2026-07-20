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

"$repository_python" scripts/build_frontend_package.py --check
unzip -t deliverables/shanhaiedu-frontend-package.zip >/dev/null
package_dir=$(mktemp -d "${TMPDIR:-/tmp}/shanhaiedu-package-check.XXXXXX")
cleanup_repository_check() {
  cleanup_readonly_git_index
  rm -rf -- "$package_dir"
}
trap cleanup_repository_check EXIT
unzip -q deliverables/shanhaiedu-frontend-package.zip -d "$package_dir"
(
  cd "$package_dir/shanhaiedu-frontend-package"
  sha256sum -c --quiet CHECKSUMS.sha256
)

echo "repository contracts, documents, checksums and archive are valid"
