#!/usr/bin/env bash
# merge-state.sh — report an open PR's mergeability against its base branch,
# polling past GitHub's transient UNKNOWN state.
#
# GitHub computes `mergeable` lazily: the first query after a push almost always
# returns UNKNOWN. Callers that treat UNKNOWN as "fine" silently ship conflicted
# PRs, so this script polls until GitHub answers (or gives up loudly).
#
# Usage: bash .agents/skills/shared/merge-state.sh [<pr-number>]
#
# Emits one line of JSON on stdout:
#   {"pr":N,"mergeable":"MERGEABLE","merge_state_status":"CLEAN",
#    "is_draft":false,"base_ref":"main","head_ref":"task/123-slug"}
#
# Exit codes:
#   0 — MERGEABLE (no conflicts with base)
#   1 — CONFLICTING (merge conflicts; must be resolved before merge)
#   2 — UNKNOWN after polling, or an error (no PR, gh failure, bad args)
set -uo pipefail

ATTEMPTS=${MERGE_STATE_ATTEMPTS:-6}
SLEEP=${MERGE_STATE_SLEEP:-5}

PR_ARG=()
if [ "$#" -gt 0 ] && [ -n "${1:-}" ]; then
  PR_ARG=("$1")
fi

FIELDS="number,mergeable,mergeStateStatus,isDraft,baseRefName,headRefName,state"

for i in $(seq 1 "$ATTEMPTS"); do
  if ! JSON=$(gh pr view "${PR_ARG[@]+"${PR_ARG[@]}"}" --json "$FIELDS" 2>&1); then
    echo "❌ merge-state: gh pr view failed: $JSON" >&2
    exit 2
  fi

  MERGEABLE=$(printf '%s' "$JSON" | jq -r '.mergeable // "UNKNOWN"')

  if [ "$MERGEABLE" != "UNKNOWN" ] || [ "$i" -eq "$ATTEMPTS" ]; then
    printf '%s' "$JSON" | jq -c '{
      pr: .number,
      mergeable: (.mergeable // "UNKNOWN"),
      merge_state_status: (.mergeStateStatus // "UNKNOWN"),
      is_draft: .isDraft,
      base_ref: .baseRefName,
      head_ref: .headRefName,
      state: .state
    }'
    break
  fi

  echo "… merge-state: GitHub still computing mergeability (attempt $i/$ATTEMPTS)" >&2
  sleep "$SLEEP"
done

case "$MERGEABLE" in
  MERGEABLE)
    exit 0
    ;;
  CONFLICTING)
    echo "⚠ merge-state: PR has merge conflicts with its base branch." >&2
    exit 1
    ;;
  *)
    echo "⚠ merge-state: mergeability still UNKNOWN after $ATTEMPTS attempts." >&2
    exit 2
    ;;
esac
