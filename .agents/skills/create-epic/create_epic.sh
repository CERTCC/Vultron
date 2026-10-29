#!/usr/bin/env bash
# create_epic.sh — Create a GitHub Epic issue for CERTCC/Vultron
#
# Usage: create_epic.sh <title> <body> <schedule> <theme> [<second-theme>]
#   schedule      Focus | Now | Next | Later | Someday
#   theme         the Epic's `theme:` label, an active catalog theme
#   second-theme  optional; only when <body> has one line naming both themes
#
# The theme gate (`theme-gate`, notes/epic-themes.md) runs before anything is
# created: the Epic must carry one active theme (or two with a named split),
# and <body> must hold a `Theme: <label> — <outcome>` line naming it
# (PAD-02-015, PAD-02-018). On refusal the script exits 1 and creates nothing.
#
# Prints the new issue number on stdout.
# All other output goes to stderr.
#
# Example:
#   EPIC_NUM=$(./create_epic.sh \
#     "Architecture Hardening (Phase 2): Import violations and BT sync" \
#     "$(cat body.md)" Next theme:capability-architecture)

set -euo pipefail

USAGE="Usage: create_epic.sh <title> <body> <schedule> <theme> [<second-theme>]"
EPIC_TITLE="${1:?${USAGE}}"
EPIC_BODY="${2:?${USAGE}}"
SCHEDULE="${3:?${USAGE}}"
THEMES=("${4:?${USAGE}}")
[[ -n "${5:-}" ]] && THEMES+=("$5")
[[ $# -gt 5 ]] && { echo "${USAGE}" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADD_TO_PROJECT="${SCRIPT_DIR}/../shared/add-to-project.sh"
BOARD_ID="${SCRIPT_DIR}/../shared/board-id.sh"

PROJECT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Theme gate: refuse before creating anything.
GATE_ARGS=(--epic --catalog "${PROJECT_DIR}/notes/epic-themes.md" --body-file -)
for T in "${THEMES[@]}"; do GATE_ARGS+=(--label "${T}"); done
GATE_RC=0
printf '%s' "${EPIC_BODY}" | PYTHONPATH= uv run --quiet --project "${PROJECT_DIR}" \
  python -m vultron.metadata.planning.theme_fit.gate "${GATE_ARGS[@]}" || GATE_RC=$?
if [[ "${GATE_RC}" -ne 0 ]]; then
  echo "ERROR: the theme gate refused the Epic (exit ${GATE_RC}); nothing was created" >&2
  exit 1
fi

# Board IDs are resolved live-and-cached via board-id.sh — never hardcoded.
REPO_NODE_ID=$(bash "$BOARD_ID" repo)
EPIC_TYPE_ID=$(bash "$BOARD_ID" issue-type Epic)

# JSON-encode title and body for safe GraphQL embedding
TITLE_JSON=$(printf '%s' "${EPIC_TITLE}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
BODY_JSON=$(printf '%s' "${EPIC_BODY}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

echo "Creating Epic issue: ${EPIC_TITLE}" >&2

# Step 1: Create the issue via GraphQL with Epic issue type
RESULT=$(gh api graphql -f query="
mutation {
  createIssue(input: {
    repositoryId: \"${REPO_NODE_ID}\"
    title: ${TITLE_JSON}
    body: ${BODY_JSON}
    issueTypeId: \"${EPIC_TYPE_ID}\"
  }) {
    issue { number id url }
  }
}")

EPIC_NUMBER=$(echo "${RESULT}" | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['number'])")
EPIC_URL=$(echo "${RESULT}" | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['url'])")

echo "  Created Epic #${EPIC_NUMBER}: ${EPIC_URL}" >&2

# Step 2: Apply the theme label(s) the gate checked.
THEME_STR=$(IFS=,; echo "${THEMES[*]}")
gh issue edit "${EPIC_NUMBER}" --repo CERTCC/Vultron --add-label "${THEME_STR}" >&2
echo "  Applied labels: ${THEME_STR}" >&2

# Step 3: Add to Project #24 and set Schedule via the shared helper, which is
# the single source of truth for the project/field/option IDs.
bash "${ADD_TO_PROJECT}" "${EPIC_NUMBER}" "${SCHEDULE}"

# Output only the Epic issue number on stdout so callers can capture it directly
echo "${EPIC_NUMBER}"
