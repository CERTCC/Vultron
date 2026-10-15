#!/usr/bin/env bash
# prepush-delta.sh — locate a branch's pre-push triage artifact and decide
# whether the post-push triage may review only the delta (PAD-07-007/008).
#
# Usage: prepush-delta.sh --path [<branch>]   print the artifact path, exit 0
#                                             (default branch: the current one)
#        prepush-delta.sh [<base-ref>]        compare (default base: origin/main)
#
# The artifact is `.claude/pr-prepush-<branch>-triage.json` in the worktree
# root, with the branch name percent-encoded (`%` as `%25`, `/` as `%2F`) so no
# two branches share a file. `.claude/pr-*.json` gitignores it. It records
# `reviewed_base_sha` and `reviewed_head_sha`, the range the pre-push review
# read, and `head_ref`, the branch it reviewed.
#
# The delta is the change to the branch's OWN lines: for every file, the
# added and removed lines of `git diff -U0 reviewed_base reviewed_head` are
# compared with those of `git diff -U0 merge-base(base, HEAD) HEAD`. Context
# lines and hunk headers are dropped, so `create-pr`'s cherry-pick onto a newer
# base adds nothing. A binary or mode-only change counts as one line.
#
# Output (compare mode), one `key=value` per line:
#   artifact=<path>  reviewed_lines=<N>  delta_lines=<M>
#   delta_files=<space-separated paths>  mode=<delta|full>  reason=<text>
# Exit: 0  delta review is enough (mode=delta)
#       3  run the full triage (mode=full): any cause PAD-07-008 lists —
#          no artifact, artifact not valid JSON, missing reviewed SHAs, artifact
#          for another branch, a reviewed commit not in the object store, an
#          empty reviewed diff, or a delta over half the reviewed lines
#       2  usage error, not on a branch, jq missing, or no merge base
set -uo pipefail

root="$(git rev-parse --show-toplevel)" || exit 2
cd "${root}" || exit 2

artifact_for() {
  local name="${1//%/%25}"
  echo "${root}/.claude/pr-prepush-${name//\//%2F}-triage.json"
}

if [ "${1:-}" = "--path" ]; then
  branch="${2:-$(git branch --show-current)}"
  [ -n "${branch}" ] || { echo "prepush-delta: not on a branch" >&2; exit 2; }
  artifact_for "${branch}"
  exit 0
fi
base_ref="${1:-origin/main}"
branch="$(git branch --show-current)"
[ -n "${branch}" ] || { echo "prepush-delta: not on a branch" >&2; exit 2; }
command -v jq >/dev/null || { echo "prepush-delta: jq not found" >&2; exit 2; }
artifact="$(artifact_for "${branch}")"

full() {
  echo "artifact=${artifact}"
  echo "mode=full"
  echo "reason=$1"
  exit 3
}

[ -f "${artifact}" ] || full "no pre-push artifact"
jq -e . "${artifact}" >/dev/null 2>&1 || full "artifact is not valid JSON"
rbase="$(jq -er '.pr_metadata.reviewed_base_sha' "${artifact}")" \
  || full "artifact has no reviewed_base_sha"
rhead="$(jq -er '.pr_metadata.reviewed_head_sha' "${artifact}")" \
  || full "artifact has no reviewed_head_sha"
rref="$(jq -r '.pr_metadata.head_ref // empty' "${artifact}")"
[ -z "${rref}" ] || [ "${rref}" = "${branch}" ] \
  || full "artifact reviewed branch ${rref}, not ${branch}"
git cat-file -e "${rhead}^{commit}" 2>/dev/null \
  || full "reviewed head ${rhead} is not in the object store"
git cat-file -e "${rbase}^{commit}" 2>/dev/null \
  || full "reviewed base ${rbase} is not in the object store"
cbase="$(git merge-base "${base_ref}" HEAD)" \
  || { echo "prepush-delta: no merge base with ${base_ref}" >&2; exit 2; }

# Own lines of one file's patch. Everything after the first hunk header is
# content; before it, only a binary marker (as its blob ids) or a mode change
# is kept, so the `---`/`+++` file headers never mix with content lines.
own_lines() {
  git -c core.quotePath=false diff --no-renames --full-index -U0 \
    "$1" "$2" -- "$3" | awk '
      /^@@/ { hunk = 1; next }
      hunk && /^[+-]/ { print; next }
      !hunk && /^index / { blobs = $0; next }
      !hunk && /^Binary files / { print blobs; next }
      !hunk && /^(old|new) mode / { print }'
}

# Print a captured line list, printing nothing for an empty one.
lines() { [ -z "$1" ] || printf '%s\n' "$1"; }

reviewed=0
delta=0
delta_files=()
while IFS= read -r -d '' f; do
  old="$(own_lines "${rbase}" "${rhead}" "${f}")"
  new="$(own_lines "${cbase}" HEAD "${f}")"
  n_old="$(lines "${old}" | wc -l)"
  reviewed=$((reviewed + n_old))
  if [ "${old}" != "${new}" ]; then
    changed="$(diff <(lines "${old}") <(lines "${new}") \
      | grep -cE '^[<>]' || true)"
    delta=$((delta + changed))
    delta_files+=("${f}")
  fi
done < <( { git diff -z --no-renames --name-only "${rbase}" "${rhead}"
            git diff -z --no-renames --name-only "${cbase}" HEAD; } | sort -zu )

echo "artifact=${artifact}"
echo "reviewed_lines=${reviewed}"
echo "delta_lines=${delta}"
echo "delta_files=${delta_files[*]:-}"
if [ "${reviewed}" -eq 0 ]; then
  echo "mode=full"
  echo "reason=the reviewed diff is empty"
  exit 3
fi
if [ $((delta * 2)) -gt "${reviewed}" ]; then
  echo "mode=full"
  echo "reason=delta (${delta} lines) exceeds half of the reviewed" \
    "${reviewed} lines"
  exit 3
fi
echo "mode=delta"
echo "reason=delta within half of the reviewed lines"
exit 0
