#!/usr/bin/env bash
# wait-for-ci.sh — poll gh pr checks until all checks complete or timeout.
#
# Usage: bash .agents/skills/shared/wait-for-ci.sh [<pr-number>]
#
# Emits one JSON object on stdout when all checks have completed:
#   {"total":N,"passing":M,"failing":K,"checks":[...]}
#
# Exit codes:
#   0 — all checks completed and passed (bucket: pass or skipping)
#   1 — one or more checks failed or were cancelled (bucket: fail or cancel)
#   2 — timed out before all checks completed, or gh error
#
# Environment:
#   WAIT_CI_TIMEOUT_MINUTES  — max minutes to wait (default: 10)
#   WAIT_CI_SLEEP            — seconds between polls (default: 30)
set -uo pipefail

TIMEOUT_MINUTES=${WAIT_CI_TIMEOUT_MINUTES:-10}
SLEEP=${WAIT_CI_SLEEP:-30}
MAX_ATTEMPTS=$(( TIMEOUT_MINUTES * 60 / SLEEP ))

PR_ARG=()
if [ "$#" -gt 0 ] && [ -n "${1:-}" ]; then
  PR_ARG=("$1")
fi

for i in $(seq 1 "$MAX_ATTEMPTS"); do
  if ! JSON=$(gh pr checks "${PR_ARG[@]+"${PR_ARG[@]}"}" --json name,bucket,state,startedAt,completedAt 2>&1); then
    echo "❌ wait-for-ci: gh pr checks failed: $JSON" >&2
    exit 2
  fi

  TOTAL=$(printf '%s' "$JSON" | jq 'length')
  PENDING=$(printf '%s' "$JSON" | jq '[.[] | select(.bucket == "pending")] | length')
  FAILING=$(printf '%s' "$JSON" | jq '[.[] | select(.bucket | IN("fail","cancel"))] | length')

  if [ "$TOTAL" -eq 0 ]; then
    echo "… wait-for-ci: no checks found yet (attempt $i/$MAX_ATTEMPTS)" >&2
    if [ "$i" -lt "$MAX_ATTEMPTS" ]; then sleep "$SLEEP"; fi
    continue
  fi

  if [ "$PENDING" -eq 0 ]; then
    PASSING=$(( TOTAL - FAILING ))
    printf '%s' "$JSON" | jq -c --argjson passing "$PASSING" --argjson failing "$FAILING" '{
      total: length,
      passing: $passing,
      failing: $failing,
      checks: .
    }'
    if [ "$FAILING" -gt 0 ]; then
      printf '%s' "$JSON" | jq -r '.[] | select(.bucket | IN("fail","cancel")) | "  ❌ \(.name)"' >&2
      exit 1
    fi
    exit 0
  fi

  echo "… wait-for-ci: $PENDING/$TOTAL check(s) still running (attempt $i/$MAX_ATTEMPTS)" >&2
  if [ "$i" -lt "$MAX_ATTEMPTS" ]; then sleep "$SLEEP"; fi
done

echo "⚠ wait-for-ci: timed out after ${TIMEOUT_MINUTES} minutes." >&2
exit 2
