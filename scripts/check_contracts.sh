#!/usr/bin/env bash
set -euo pipefail

repo_root="$(GIT_INDEX_FILE=/dev/null GIT_OPTIONAL_LOCKS=0 git rev-parse --show-toplevel)"
cd "$repo_root"
source "$repo_root/scripts/readonly_git_index.sh"
prepare_readonly_git_index
trap cleanup_readonly_git_index EXIT

pnpm contracts:lint
pnpm contracts:surface
pnpm contracts:schema
pnpm contracts:generate
pnpm contracts:typecheck
pnpm contracts:test
pnpm contracts:generate
git diff --exit-code -- contracts/generated
