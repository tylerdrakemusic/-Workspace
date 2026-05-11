#!/usr/bin/env bash
# pre-commit-worktree-guard.sh
# FR-20260511-worktree-local-migration
#
# Blocks accidental staging of .worktrees/ paths.
# Install as the repo's pre-commit hook:
#
#   cp .github/hooks/scripts/pre-commit-worktree-guard.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Or source it from an existing pre-commit hook:
#   source "$(git rev-parse --show-toplevel)/.github/hooks/scripts/pre-commit-worktree-guard.sh"

set -euo pipefail

# Detect staged files that live under .worktrees/
BLOCKED=$(git diff --cached --name-only | grep -E "^\.worktrees/" || true)

if [[ -n "$BLOCKED" ]]; then
    echo ""
    echo "❌ pre-commit guard: .worktrees/ paths must never be committed."
    echo "   Blocked files:"
    echo "$BLOCKED" | sed 's/^/     /'
    echo ""
    echo "   .worktrees/ is gitignored workspace-local storage for git worktrees."
    echo "   Run:  git restore --staged <file>  to unstage."
    echo ""
    exit 1
fi
