#!/usr/bin/env bash
# verify-merge-gate.sh — pr-verify Phase 2: the live merge-state gate
# (PAD-18-005). Re-checks merge state live and maps it onto pr-verify's flags.
#
# Usage: verify-merge-gate.sh <pr-number> [--check-markers]
#   --check-markers  also grep the worktree for surviving conflict markers;
#                    pass it when execute.merge_state.conflicts_resolved is
#                    non-empty (Phase 2 step 5)
#
# Flags, from one merge-state.sh call:
#   exit 1 (CONFLICTING), status DIRTY, or a marker hit -> MERGE-CONFLICT
#   exit 2 (UNKNOWN after polling, or a gh error)       -> MERGE-STATE-UNKNOWN
#   status BEHIND                                       -> BRANCH-BEHIND
#   status DRAFT                                        -> PR-IS-DRAFT
#   status BLOCKED                                      -> note only, no flag
# The verdict is the strongest effect on pr-verify's overall verdict:
#   MERGE-CONFLICT                     -> conflicts-found
#   else MERGE-STATE-UNKNOWN           -> pending-merge-check
#   else BRANCH-BEHIND or PR-IS-DRAFT  -> blocks-ready
#   else                               -> clear
#
# Output, one `key=value` per line:
#   verdict=<conflicts-found|pending-merge-check|blocks-ready|clear>
#   flag=<FLAG>  one per flag raised
#   mergeable=  merge_state_status=  merge_state_exit=  base_ref=
#   needs_rebase=<true|false>   (PR-IS-DRAFT only)
#   note=blocked                (status BLOCKED)
#   conflict=<merge-tree CONFLICT line>  evidence, MERGE-CONFLICT only
#   marker=<file:line>          --check-markers hits
# Exit: 0 a verdict was printed; 2 usage error or jq missing.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || { echo "usage: $0 <pr-number> [--check-markers]" >&2; exit 2; }
pr="$1"
markers=false
if [ "$#" -eq 2 ]; then
  [ "$2" = "--check-markers" ] || { echo "usage: $0 <pr-number> [--check-markers]" >&2; exit 2; }
  markers=true
fi
command -v jq >/dev/null || { echo "verify-merge-gate: jq not found" >&2; exit 2; }

json="$(bash "${here}/merge-state.sh" "${pr}")"; ms=$?
field() { printf '%s' "${json}" | jq -r "$1" 2>/dev/null; }
mergeable="$(field '.mergeable // "UNKNOWN"')"
status="$(field '.merge_state_status // "UNKNOWN"')"
base="$(field '.base_ref // empty')"

flags=()
marker_hits=""
if [ "${markers}" = true ]; then
  # Only the <<<<<<< and >>>>>>> markers, each followed by a space: a bare
  # ======= row is a valid setext heading underline in markdown.
  marker_hits="$(git grep -nE '^(<<<<<<<|>>>>>>>) ' -- . 2>/dev/null | cut -d: -f1,2)"
fi
if [ "${ms}" = 1 ] || [ "${status}" = DIRTY ] || [ -n "${marker_hits}" ]; then
  flags+=(MERGE-CONFLICT)
fi
[ "${ms}" = 2 ] && flags+=(MERGE-STATE-UNKNOWN)
[ "${status}" = BEHIND ] && flags+=(BRANCH-BEHIND)
[ "${status}" = DRAFT ] && flags+=(PR-IS-DRAFT)

has() { local f; for f in ${flags[@]+"${flags[@]}"}; do [ "${f}" = "$1" ] && return 0; done; return 1; }

if has MERGE-CONFLICT; then verdict=conflicts-found
elif has MERGE-STATE-UNKNOWN; then verdict=pending-merge-check
elif has BRANCH-BEHIND || has PR-IS-DRAFT; then verdict=blocks-ready
else verdict=clear
fi

echo "verdict=${verdict}"
for f in ${flags[@]+"${flags[@]}"}; do echo "flag=${f}"; done
echo "mergeable=${mergeable}"
echo "merge_state_status=${status}"
echo "merge_state_exit=${ms}"
echo "base_ref=${base}"
if has PR-IS-DRAFT; then
  labels="$(gh pr view "${pr}" --json labels --jq '[.labels[].name] | join(",")' 2>/dev/null)"
  case ",${labels}," in *,needs-rebase,*) echo "needs_rebase=true" ;; *) echo "needs_rebase=false" ;; esac
fi
[ "${status}" = BLOCKED ] && echo "note=blocked"
if has MERGE-CONFLICT && [ -n "${base}" ] && git fetch -q origin "${base}" 2>/dev/null; then
  git merge-tree --write-tree HEAD "origin/${base}" 2>&1 | grep -i '^CONFLICT' | sed 's/^/conflict=/'
fi
[ -z "${marker_hits}" ] || printf '%s\n' "${marker_hits}" | sed 's/^/marker=/'
exit 0
