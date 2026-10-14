#!/usr/bin/env bash
# epic-hold.sh — is this issue held by an epic run on its Epic? (PAD-19-002/003)
# Usage: bash .agents/skills/shared/epic-hold.sh <ISSUE_NUMBER> [<EPIC_RUN>]
#   ISSUE_NUMBER  the issue about to be claimed
#   EPIC_RUN      the Epic the caller is running for (build --epic-run <Epic>)
#
# A Task or Feature whose nearest Epic ancestor is assigned is held: an epic
# run (work-epic-tasks) owns it, even in a later wave. Bugs, Ideas, and Concerns
# are never held. Every agent runs as the same GitHub user, so the assignee
# cannot tell the run from a stray session; only EPIC_RUN naming that Epic can.
#
# Exit codes: 0 free (or held by EPIC_RUN); 3 held — the reason is on stderr;
#             2 API error.
set -euo pipefail

ISSUE_NUMBER="${1:?Usage: epic-hold.sh <ISSUE_NUMBER> [<EPIC_RUN>]}"
EPIC_RUN="${2:-}"

# Four parent hops reach the nearest Epic from any depth PAD-01-002 allows,
# with one to spare for an Epic nested under another.
PARENT='number issueType { name } assignees(first: 5) { nodes { login } }'
Q="parent { ${PARENT} }"
for _ in 1 2 3; do Q="parent { ${PARENT} ${Q} }"; done

if ! DATA=$(gh api graphql -f query="{
  repository(owner:\"CERTCC\", name:\"Vultron\") {
    issue(number: ${ISSUE_NUMBER}) { issueType { name } ${Q} }
  }
}"); then
  echo "❌ epic-hold: could not read #${ISSUE_NUMBER} and its parents." >&2
  exit 2
fi

TYPE=$(jq -r '.data.repository.issue.issueType.name // ""' <<<"$DATA")
case "$TYPE" in
  Task|Feature) ;;
  *) exit 0 ;;  # only the build lane is held (PAD-19-002)
esac

# The nearest ancestor whose type is Epic, as "<number> <login,login>", or
# nothing when there is none. A jq failure is an error, never "free".
if ! NEAREST=$(jq -r '
  [.data.repository.issue | recurse(.parent // empty) | select(.number != null)]
  | map(select(.issueType.name == "Epic")) | first // empty
  | "\(.number) \([.assignees.nodes[].login] | join(","))"' <<<"$DATA"); then
  echo "❌ epic-hold: unreadable reply for #${ISSUE_NUMBER}." >&2
  exit 2
fi
EPIC="${NEAREST%% *}"
LOGINS="${NEAREST#* }"

if [ -z "${NEAREST}" ] || [ -z "${LOGINS}" ]; then
  exit 0
fi
if [ "$EPIC_RUN" = "$EPIC" ]; then
  exit 0
fi

echo "⏸  #${ISSUE_NUMBER} is held: its Epic #${EPIC} is claimed by an epic run" \
  "(assigned to ${LOGINS}). Only that run may build it (--epic-run ${EPIC})." >&2
exit 3
