#!/usr/bin/env bash
# prepush-delta.sh — locate this branch's pre-push triage artifact and decide
# whether the post-push triage may review only the delta (PAD-07-007/008).
#
# Usage: prepush-delta.sh --path              print the artifact path and exit 0
#        prepush-delta.sh [<base-ref>]        compare (default base: origin/main)
#
# The artifact is `.claude/pr-prepush-<branch, "/" as "-">-triage.json` in the
# worktree root, gitignored by `.claude/pr-*.json`. It records
# `reviewed_base_sha` and `reviewed_head_sha`, the range the pre-push review read.
#
# The delta is the change to the branch's OWN lines: for every file, the `+`/`-`
# lines of `git diff -U0 reviewed_base reviewed_head` are compared with those of
# `git diff -U0 merge-base(base, HEAD) HEAD`. Context lines and hunk headers are
# dropped, so `create-pr`'s cherry-pick onto a newer base adds nothing.
#
# Output (compare mode), one `key=value` per line:
#   artifact=<path>  reviewed_lines=<N>  delta_lines=<M>
#   delta_files=<space-separated paths>  mode=<delta|full>  reason=<text>
# Exit: 0  delta review is enough (mode=delta)
#       3  run the full triage (mode=full): no artifact, unreadable artifact,
#          reviewed head not in the object store, or delta > half the reviewed lines
#       2  usage error, or not on a branch
set -uo pipefail

root="$(git rev-parse --show-toplevel)" || exit 2
branch="$(git branch --show-current)"
[ -n "${branch}" ] || { echo "prepush-delta: not on a branch" >&2; exit 2; }
artifact="${root}/.claude/pr-prepush-${branch//\//-}-triage.json"

if [ "${1:-}" = "--path" ]; then
  echo "${artifact}"
  exit 0
fi
base_ref="${1:-origin/main}"

full() {
  echo "artifact=${artifact}"
  echo "mode=full"
  echo "reason=$1"
  exit 3
}

[ -f "${artifact}" ] || full "no pre-push artifact"
rbase="$(jq -er '.pr_metadata.reviewed_base_sha' "${artifact}" 2>/dev/null)" \
  || full "artifact has no reviewed_base_sha"
rhead="$(jq -er '.pr_metadata.reviewed_head_sha' "${artifact}" 2>/dev/null)" \
  || full "artifact has no reviewed_head_sha"
git cat-file -e "${rhead}^{commit}" 2>/dev/null \
  || full "reviewed head ${rhead} is not in the object store"
git cat-file -e "${rbase}^{commit}" 2>/dev/null \
  || full "reviewed base ${rbase} is not in the object store"
cbase="$(git merge-base "${base_ref}" HEAD)" || exit 2

# Own lines of one file's patch: `+`/`-` lines only, file headers dropped.
own_lines() {
  git diff --no-renames -U0 "$1" "$2" -- "$3" \
    | grep -E '^[+-]' | grep -vE '^(\+\+\+|---) ' || true
}

# Print a captured line list, printing nothing for an empty one.
lines() { [ -z "$1" ] || printf '%s\n' "$1"; }

files="$( { git diff --no-renames --name-only "${rbase}" "${rhead}"
            git diff --no-renames --name-only "${cbase}" HEAD; } | sort -u )"

reviewed=0
delta=0
delta_files=()
while IFS= read -r f; do
  [ -n "${f}" ] || continue
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
done <<< "${files}"

echo "artifact=${artifact}"
echo "reviewed_lines=${reviewed}"
echo "delta_lines=${delta}"
echo "delta_files=${delta_files[*]:-}"
if [ $((delta * 2)) -gt "${reviewed}" ]; then
  echo "mode=full"
  echo "reason=delta (${delta} lines) exceeds half of the reviewed" \
    "${reviewed} lines"
  exit 3
fi
echo "mode=delta"
echo "reason=delta within half of the reviewed lines"
exit 0
