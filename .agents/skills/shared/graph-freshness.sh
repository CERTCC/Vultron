#!/usr/bin/env bash
# Report whether this worktree's graphify graph is usable before relying on it.
#
# Usage: bash .agents/skills/shared/graph-freshness.sh [max-commits-behind]
#
# Exit 0: graph present and within the threshold (default 50 commits).
# Exit 1: graph absent or stale — use grep / code search instead, and do not
#         trust community names or document/rationale nodes.
#
# graphify-out/ is gitignored and per-worktree, so a fresh worktree has no
# graph. The post-commit hook only refreshes the AST (code) layer, and only
# when core.hooksPath points at .githooks; document and rationale nodes are as
# of built_at_commit until a full `/graphify . --update` run.

set -u

MAX_BEHIND=${1:-50}
GRAPH=graphify-out/graph.json

cd "$(git rev-parse --show-toplevel)" || exit 1

if [ ! -f "$GRAPH" ]; then
    echo "graph: absent in this worktree — use grep/code search"
    exit 1
fi

BUILT=$(tail -c 200 "$GRAPH" | sed -n 's/.*"built_at_commit": *"\([0-9a-f]*\)".*/\1/p')
if [ -z "$BUILT" ] || ! git cat-file -e "${BUILT}^{commit}" 2>/dev/null; then
    echo "graph: built_at_commit unknown — treat as stale"
    exit 1
fi

BEHIND=$(git rev-list --count "${BUILT}..HEAD")
BUILT_DATE=$(git show -s --format=%cs "$BUILT")
HOOK=$(git config core.hooksPath || true)
HOOK_NOTE=""
[ "$HOOK" = ".githooks" ] || HOOK_NOTE=" (post-commit hook not installed: core.hooksPath='${HOOK}')"

if [ "$BEHIND" -gt "$MAX_BEHIND" ]; then
    echo "graph: STALE — built ${BUILT_DATE}, ${BEHIND} commits behind HEAD${HOOK_NOTE}; use grep/code search, refresh with 'graphify update .'"
    exit 1
fi

echo "graph: ok — built ${BUILT_DATE}, ${BEHIND} commits behind HEAD${HOOK_NOTE}"
