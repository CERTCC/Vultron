#!/usr/bin/env bash
# csaf-draft-watch-issue.sh — open the one CSAF draft-watch issue, unless open.
#
# Usage: csaf-draft-watch-issue.sh <owner/repo> <body-file>
#
# The CSAF Draft Watch workflow calls this when `csaf-draft-watch` reports
# that upstream changed what the CSAF models depend on (CSAF-05-005). The
# issue's marker is the `csaf-draft-watch` label. While an issue carrying it
# is open, this script creates, edits and comments on nothing (CSAF-05-006):
# one open issue already says the pin is behind.
#
# It only repairs that open issue when an earlier run stopped before typing
# or theming it (CISEC-05-018, PAD-02-026). Both helpers leave a typed,
# themed issue alone, so on a complete issue this script only reads.
#
# The issue gets the Task type, a `theme:` label and a `Theme:` line, and no
# parent (PAD-02-027). Needs GH_TOKEN with issues:write.

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <owner/repo> <body-file>" >&2
  exit 2
fi
repo="$1"
body_file="$2"

label=csaf-draft-watch
title="The CSAF 2.1 draft has changed past the pinned revision"
theme=theme:standards-engagement
outcome="maintainers learn, once and with the affected fields named, when the CSAF 2.1 draft moves past Vultron's pinned revision."
scripts=$(dirname "${BASH_SOURCE[0]}")

# shellcheck source=.github/scripts/retry.sh
source "$scripts/retry.sh"

# The list-issues endpoint, not the lagging search index behind
# `gh issue list --label`, which once missed an open tracker and let a
# duplicate be filed (#5105). A command substitution, so an API error fails
# the step instead of reading as "none open" (CISEC-05-011).
open_issues=$(retry gh api --paginate \
  "repos/$repo/issues?labels=$label&state=open&sort=created&direction=asc&per_page=100" \
  --jq '.[] | select(.pull_request == null) | .number')
existing=${open_issues%%$'\n'*}  # the oldest

if [ -n "$existing" ]; then
  echo "Issue #$existing is open; the pin is already reported as behind."
  bash "$scripts/ensure-issue-type.sh" "$repo" "$existing" Task
  bash "$scripts/ensure-issue-triage.sh" "$repo" "$existing" "$theme" "$outcome"
  exit 0
fi

# --force upserts the label, so a retry lands in the same state.
retry gh label create "$label" --repo "$repo" --force \
  --description "Bot-managed: the CSAF 2.1 draft moved past the pinned revision" \
  --color "1D76DB"
# Not retried: a retry after a create that reached GitHub would file a second
# issue, the duplicate this script exists to prevent.
url=$(gh issue create --repo "$repo" --title "$title" \
  --body-file "$body_file" --label "$label")
echo "Filed $url"
bash "$scripts/ensure-issue-type.sh" "$repo" "${url##*/}" Task
bash "$scripts/ensure-issue-triage.sh" "$repo" "${url##*/}" "$theme" "$outcome"
