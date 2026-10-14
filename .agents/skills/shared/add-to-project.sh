#!/usr/bin/env bash
# add-to-project.sh — add a GitHub issue to Project #24 and set its Schedule.
# Usage: bash .agents/skills/shared/add-to-project.sh <ISSUE_NUMBER> [SCHEDULE]
#   ISSUE_NUMBER  GitHub issue number to add
#   SCHEDULE      Schedule value: Focus | Now | Next | Later | Someday (default: Someday)
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: add-to-project.sh <ISSUE_NUMBER> [SCHEDULE]}"
SCHEDULE="${2:-Someday}"

bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/set-board-field.sh" \
  "$ISSUE_NUMBER" schedule "$SCHEDULE"
