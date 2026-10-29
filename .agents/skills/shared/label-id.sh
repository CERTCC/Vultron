#!/usr/bin/env bash
# label-id.sh — print the GraphQL node ID of a repository label.
#
# Usage: label-id.sh <OWNER/NAME> <label-name>
#
# Exit codes: 0 printed the ID; 1 the label does not exist; 2 gh failed.
# The scripts behind `create-issue` and `create-epic` resolve every
# label before they create an issue, so the labels go into the create mutation
# itself: an issue is never left without the theme label the gate checked.
set -euo pipefail

REPO="${1:?Usage: label-id.sh <OWNER/NAME> <label-name>}"
NAME="${2:?Usage: label-id.sh <OWNER/NAME> <label-name>}"

NAME_JSON=$(printf '%s' "${NAME}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

REPLY=$(gh api graphql -f query="{ repository(owner:\"${REPO%%/*}\", name:\"${REPO##*/}\") {
  label(name: ${NAME_JSON}) { id } } }") || exit 2

ID=$(python3 -c "
import json, sys
label = json.load(sys.stdin)['data']['repository']['label']
print(label['id'] if label else '')
" <<< "${REPLY}") || exit 2

if [[ -z "${ID}" ]]; then
  echo "ERROR: label '${NAME}' does not exist in ${REPO}" >&2
  exit 1
fi
echo "${ID}"
