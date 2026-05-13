#!/usr/bin/env bash
# manage_github_issue.sh — Create or update a GitHub Issue with structured
# relationships (parent/child sub-issues, blocking/blocked-by) via GraphQL.
#
# Usage:
#   manage_github_issue.sh [OPTIONS]
#
# Options:
#   --repo OWNER/NAME       Repository (default: CERTCC/Vultron)
#   --issue-number N        Issue number to update (triggers update mode)
#   --title TEXT            Issue title
#   --body TEXT             Issue body markdown
#   --label LABEL           Label to apply (repeatable)
#   --issue-type-id ID      GraphQL node ID for the issue type
#   --parent N              Set this issue as sub-issue of parent #N
#   --blocked-by N          This issue is blocked by #N (repeatable, idempotent)
#   --blocks N              This issue blocks #N (repeatable, idempotent)
#   --sub-issue N           Add #N as sub-issue of this issue (repeatable, idempotent)
#   --clean-body            Strip legacy relationship markers from the issue body
#
# Outputs:
#   Issue number on stdout. Progress and status on stderr.
#
# Examples:
#   # Create with parent and blocker:
#   NUM=$(.agents/skills/manage-github-issue/manage_github_issue.sh \
#     --title "Implement X" --body "..." \
#     --label "group:unscheduled,size:M" \
#     --parent 42 --blocked-by 50)
#
#   # Wire relationships on an existing issue:
#   .agents/skills/manage-github-issue/manage_github_issue.sh \
#     --issue-number 99 --blocked-by 50 --blocks 100 --clean-body
#
#   # Add sub-issues to a parent:
#   .agents/skills/manage-github-issue/manage_github_issue.sh \
#     --issue-number 42 --sub-issue 99 --sub-issue 100

set -euo pipefail

REPO="CERTCC/Vultron"
ISSUE_NUMBER=""
TITLE=""
BODY=""
LABELS=()
ISSUE_TYPE_ID=""
PARENT_ISSUE=""
BLOCKED_BY=()
BLOCKS=()
SUB_ISSUES=()
CLEAN_BODY=0

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)          REPO="$2";          shift 2 ;;
    --issue-number)  ISSUE_NUMBER="$2";  shift 2 ;;
    --title)         TITLE="$2";         shift 2 ;;
    --body)          BODY="$2";          shift 2 ;;
    --label)         LABELS+=("$2");     shift 2 ;;
    --issue-type-id) ISSUE_TYPE_ID="$2"; shift 2 ;;
    --parent)        PARENT_ISSUE="$2";  shift 2 ;;
    --blocked-by)    BLOCKED_BY+=($2);   shift 2 ;;
    --blocks)        BLOCKS+=($2);       shift 2 ;;
    --sub-issue)     SUB_ISSUES+=("$2"); shift 2 ;;
    --clean-body)    CLEAN_BODY=1;       shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

REPO_OWNER="${REPO%%/*}"
REPO_NAME="${REPO##*/}"

# ── helpers ──────────────────────────────────────────────────────────────────

json_encode() {
  python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))"
}

graphql() {
  gh api graphql -f query="$1"
}

# Resolve a single issue node ID by number
resolve_node_id() {
  local number="$1"
  graphql "{ repository(owner:\"${REPO_OWNER}\", name:\"${REPO_NAME}\") {
    issue(number: ${number}) { id }
  } }" | python3 -c \
    "import json,sys; print(json.load(sys.stdin)['data']['repository']['issue']['id'])"
}

# Resolve the repository node ID
resolve_repo_id() {
  graphql "{ repository(owner:\"${REPO_OWNER}\", name:\"${REPO_NAME}\") { id } }" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['repository']['id'])"
}

# ── Step 1: Create or update ──────────────────────────────────────────────────

if [[ -z "${ISSUE_NUMBER}" ]]; then
  # CREATE mode
  [[ -z "${TITLE}" ]] && { echo "ERROR: --title is required when creating an issue" >&2; exit 1; }

  REPO_NODE_ID=$(resolve_repo_id)

  TITLE_JSON=$(printf '%s' "${TITLE}" | json_encode)
  BODY_JSON=$(printf '%s' "${BODY}" | json_encode)

  # Build optional fields
  TYPE_FIELD=""
  [[ -n "${ISSUE_TYPE_ID}" ]] && TYPE_FIELD="issueTypeId: \"${ISSUE_TYPE_ID}\""

  PARENT_FIELD=""
  PARENT_NODE_ID=""
  if [[ -n "${PARENT_ISSUE}" ]]; then
    PARENT_NODE_ID=$(resolve_node_id "${PARENT_ISSUE}")
    PARENT_FIELD="parentIssueId: \"${PARENT_NODE_ID}\""
  fi

  echo "Creating issue: ${TITLE}" >&2

  RESULT=$(graphql "
  mutation {
    createIssue(input: {
      repositoryId: \"${REPO_NODE_ID}\"
      title: ${TITLE_JSON}
      body: ${BODY_JSON}
      ${TYPE_FIELD}
      ${PARENT_FIELD}
    }) {
      issue { number id url }
    }
  }")

  ISSUE_NUMBER=$(python3 -c \
    "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['number'])" \
    <<< "${RESULT}")
  THIS_NODE_ID=$(python3 -c \
    "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['id'])" \
    <<< "${RESULT}")
  ISSUE_URL=$(python3 -c \
    "import json,sys; print(json.load(sys.stdin)['data']['createIssue']['issue']['url'])" \
    <<< "${RESULT}")

  echo "  Created #${ISSUE_NUMBER}: ${ISSUE_URL}" >&2

  # Apply labels (REST accepts label names directly)
  if [[ ${#LABELS[@]} -gt 0 ]]; then
    LABEL_STR=$(IFS=,; echo "${LABELS[*]}")
    gh issue edit "${ISSUE_NUMBER}" \
      --repo "${REPO}" \
      --add-label "${LABEL_STR}" >&2
    echo "  Applied labels: ${LABEL_STR}" >&2
  fi

  # Parent was set at create time; clear PARENT_ISSUE to skip Step 2
  PARENT_ISSUE=""

else
  # UPDATE mode
  THIS_NODE_ID=$(resolve_node_id "${ISSUE_NUMBER}")
  echo "Updating issue #${ISSUE_NUMBER}" >&2

  if [[ -n "${TITLE}" || -n "${BODY}" ]]; then
    TITLE_JSON=$(printf '%s' "${TITLE}" | json_encode)
    BODY_JSON=$(printf '%s' "${BODY}" | json_encode)

    TITLE_FIELD=""
    [[ -n "${TITLE}" ]] && TITLE_FIELD="title: ${TITLE_JSON}"
    BODY_FIELD=""
    [[ -n "${BODY}" ]] && BODY_FIELD="body: ${BODY_JSON}"

    graphql "
    mutation {
      updateIssue(input: {
        id: \"${THIS_NODE_ID}\"
        ${TITLE_FIELD}
        ${BODY_FIELD}
      }) {
        issue { number url }
      }
    }" > /dev/null
    echo "  Updated title/body" >&2
  fi

  if [[ ${#LABELS[@]} -gt 0 ]]; then
    LABEL_STR=$(IFS=,; echo "${LABELS[*]}")
    gh issue edit "${ISSUE_NUMBER}" \
      --repo "${REPO}" \
      --add-label "${LABEL_STR}" >&2
    echo "  Applied labels: ${LABEL_STR}" >&2
  fi
fi

# ── Step 2: Wire parent (if not set at create time) ───────────────────────────

if [[ -n "${PARENT_ISSUE}" ]]; then
  EXISTING_PARENT=$(graphql "{
    repository(owner:\"${REPO_OWNER}\", name:\"${REPO_NAME}\") {
      issue(number: ${ISSUE_NUMBER}) { parent { number } }
    }
  }" | python3 -c "
import json, sys
p = json.load(sys.stdin)['data']['repository']['issue']['parent']
print(p['number'] if p else '')
")

  if [[ "${EXISTING_PARENT}" == "${PARENT_ISSUE}" ]]; then
    echo "  Parent #${PARENT_ISSUE} already set — skipping" >&2
  else
    PARENT_NODE_ID=$(resolve_node_id "${PARENT_ISSUE}")
    graphql "
    mutation {
      addSubIssue(input: {
        issueId: \"${PARENT_NODE_ID}\"
        subIssueId: \"${THIS_NODE_ID}\"
      }) {
        issue { number }
        subIssue { number }
      }
    }" > /dev/null
    echo "  Wired parent: #${ISSUE_NUMBER} → parent #${PARENT_ISSUE}" >&2
  fi
fi

# ── Step 3: Wire blocked-by relationships ─────────────────────────────────────

if [[ ${#BLOCKED_BY[@]} -gt 0 ]]; then
  EXISTING_BLOCKERS=$(graphql "{
    repository(owner:\"${REPO_OWNER}\", name:\"${REPO_NAME}\") {
      issue(number: ${ISSUE_NUMBER}) {
        blockedBy(first: 100) { nodes { number } }
      }
    }
  }" | python3 -c "
import json, sys
nodes = json.load(sys.stdin)['data']['repository']['issue']['blockedBy']['nodes']
print(' '.join(str(n['number']) for n in nodes))
")

  for B in "${BLOCKED_BY[@]}"; do
    if echo "${EXISTING_BLOCKERS}" | grep -qw "${B}"; then
      echo "  blocked-by #${B} already set — skipping" >&2
    else
      B_NODE_ID=$(resolve_node_id "${B}")
      graphql "
      mutation {
        addBlockedBy(input: {
          issueId: \"${THIS_NODE_ID}\"
          blockingIssueId: \"${B_NODE_ID}\"
        }) {
          issue { number }
          blockingIssue { number }
        }
      }" > /dev/null
      echo "  Wired: #${ISSUE_NUMBER} blocked-by #${B}" >&2
    fi
  done
fi

# ── Step 4: Wire blocking relationships ───────────────────────────────────────

if [[ ${#BLOCKS[@]} -gt 0 ]]; then
  for T in "${BLOCKS[@]}"; do
    T_NODE_ID=$(resolve_node_id "${T}")

    EXISTING_BLOCKERS_OF_T=$(graphql "{
      repository(owner:\"${REPO_OWNER}\", name:\"${REPO_NAME}\") {
        issue(number: ${T}) {
          blockedBy(first: 100) { nodes { number } }
        }
      }
    }" | python3 -c "
import json, sys
nodes = json.load(sys.stdin)['data']['repository']['issue']['blockedBy']['nodes']
print(' '.join(str(n['number']) for n in nodes))
")

    if echo "${EXISTING_BLOCKERS_OF_T}" | grep -qw "${ISSUE_NUMBER}"; then
      echo "  #${T} already blocked-by #${ISSUE_NUMBER} — skipping" >&2
    else
      graphql "
      mutation {
        addBlockedBy(input: {
          issueId: \"${T_NODE_ID}\"
          blockingIssueId: \"${THIS_NODE_ID}\"
        }) {
          issue { number }
          blockingIssue { number }
        }
      }" > /dev/null
      echo "  Wired: #${ISSUE_NUMBER} blocks #${T}" >&2
    fi
  done
fi

# ── Step 5: Wire sub-issues ───────────────────────────────────────────────────

if [[ ${#SUB_ISSUES[@]} -gt 0 ]]; then
  EXISTING_SUB=$(graphql "{
    repository(owner:\"${REPO_OWNER}\", name:\"${REPO_NAME}\") {
      issue(number: ${ISSUE_NUMBER}) {
        subIssues(first: 100) { nodes { number } }
      }
    }
  }" | python3 -c "
import json, sys
nodes = json.load(sys.stdin)['data']['repository']['issue']['subIssues']['nodes']
print(' '.join(str(n['number']) for n in nodes))
")

  for C in "${SUB_ISSUES[@]}"; do
    if echo "${EXISTING_SUB}" | grep -qw "${C}"; then
      echo "  sub-issue #${C} already wired — skipping" >&2
    else
      C_NODE_ID=$(resolve_node_id "${C}")
      graphql "
      mutation {
        addSubIssue(input: {
          issueId: \"${THIS_NODE_ID}\"
          subIssueId: \"${C_NODE_ID}\"
        }) {
          issue { number }
          subIssue { number }
        }
      }" > /dev/null
      echo "  Wired sub-issue: #${C} → parent #${ISSUE_NUMBER}" >&2
    fi
  done
fi

# ── Step 6: Clean legacy body-text markers ────────────────────────────────────

WIRED_SOMETHING=$(( ${#BLOCKED_BY[@]} + ${#BLOCKS[@]} + ${#SUB_ISSUES[@]} ))
[[ -n "${PARENT_ISSUE}" ]] && WIRED_SOMETHING=$(( WIRED_SOMETHING + 1 ))

if [[ "${CLEAN_BODY}" -eq 1 || "${WIRED_SOMETHING}" -gt 0 ]]; then
  CURRENT_BODY=$(gh issue view "${ISSUE_NUMBER}" \
    --repo "${REPO}" --json body --jq '.body')

  CLEANED_BODY=$(printf '%s' "${CURRENT_BODY}" | python3 -c "
import sys, re
body = sys.stdin.read()
patterns = [
    r'(?im)^\s*blocked[ -]by:?\s+#\d+[^\n]*\n?',
    r'(?im)^\s*blocks:?\s+#\d+[^\n]*\n?',
    r'(?im)^\s*parent:?\s+(?:issue:?\s*)?#\d+[^\n]*\n?',
    r'(?im)^\s*sub-?issues?:?\s+#\d+[^\n]*\n?',
]
for p in patterns:
    body = re.sub(p, '', body)
print(body.strip())
")

  if [[ "${CLEANED_BODY}" != "${CURRENT_BODY}" ]]; then
    CLEANED_JSON=$(printf '%s' "${CLEANED_BODY}" | json_encode)
    graphql "
    mutation {
      updateIssue(input: {
        id: \"${THIS_NODE_ID}\"
        body: ${CLEANED_JSON}
      }) { issue { number } }
    }" > /dev/null
    echo "  Stripped legacy body-text relationship markers" >&2
  fi
fi

# ── Output issue number for callers to capture ────────────────────────────────

echo "${ISSUE_NUMBER}"
