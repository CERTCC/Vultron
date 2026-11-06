#!/usr/bin/env bash
# verify-merge-gate.sh — pr-verify Phase 2: the live merge-state gate
# (PAD-18-005). Re-checks merge state live and maps it onto pr-verify's flags.
#
# Usage: verify-merge-gate.sh <pr-number> [--check-markers]
#   --check-markers  also grep the worktree for surviving conflict markers;
#                    pass it when execute.merge_state.conflicts_resolved is
#                    non-empty (Phase 2 step 1)
#
# Flags, from one merge-state.sh call:
#   exit 1 (CONFLICTING), status DIRTY, or a marker hit -> MERGE-CONFLICT
#   exit 2 (UNKNOWN after polling, or a gh error)       -> MERGE-STATE-UNKNOWN
#   status BEHIND                                       -> BRANCH-BEHIND
#   status DRAFT                                        -> PR-IS-DRAFT
#   status BLOCKED, `CI gate` not green                 -> CI-GATE-NOT-GREEN
#   status BLOCKED, `CI gate` green                     -> note only, no flag
# BLOCKED splits on the `CI gate` because only one of its causes is a wall.
# Ruleset `main-3 Require CI gate` lists no bypass actor, so a gate that is red,
# pending or absent refuses the merge for every account (#5945); the repository's
# other `main` rules let the admin role bypass, so a BLOCKED whose gate is green
# is the survivable kind and stays a note, as it was before the ruleset existed.
# The verdict is the strongest effect on pr-verify's overall verdict:
#   MERGE-CONFLICT                     -> conflicts-found
#   else MERGE-STATE-UNKNOWN           -> pending-merge-check
#   else BRANCH-BEHIND, PR-IS-DRAFT
#        or CI-GATE-NOT-GREEN          -> blocks-ready
#   else                               -> clear
#
# Output, one `key=value` per line:
#   verdict=<conflicts-found|pending-merge-check|blocks-ready|clear>
#   flag=<FLAG>  one per flag raised
#   mergeable=  merge_state_status=  merge_state_exit=  base_ref=
#   needs_rebase=<true|false|unknown>  (PR-IS-DRAFT only; unknown on a gh error)
#   ci_gate=<conclusion|PENDING|absent|unknown>  (status BLOCKED only; `unknown`
#                               on a gh error, which raises the flag rather than
#                               letting a merge gate clear on missing evidence)
#   note=blocked                (status BLOCKED with a green `CI gate`)
#   conflict=<merge-tree CONFLICT line>  evidence, MERGE-CONFLICT only
#   conflict_evidence=unavailable  MERGE-CONFLICT with no conflict= or marker=
#                               line (no base ref, a failed fetch, or a trial
#                               merge that names no CONFLICT)
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

# BLOCKED's non-bypassable cause: the `CI gate` required by `main-3` (#5945).
# Read the newest `CI gate` run on the head commit, which is the one GitHub's
# required-check evaluation reads and the one the gate itself judges by: a
# cancelled or superseded earlier run sits beside it in the rollup. Match on
# `.name` alone, never a status `.context`, because the rule pins the check to
# `integration_id` 15368, so only a GitHub Actions check run can satisfy it.
ci_gate=""
if [ "${status}" = BLOCKED ]; then
  if ! ci_gate="$(gh pr view "${pr}" --json statusCheckRollup --jq '
        [ .statusCheckRollup[]? | select(.name == "CI gate") ]
        | sort_by(.startedAt // "") | last
        | if . == null then "absent"
          elif (.status // "") != "COMPLETED" then "PENDING"
          else (.conclusion // "PENDING") end' 2>/dev/null)" || [ -z "${ci_gate}" ]; then
    ci_gate=unknown
  fi
  [ "${ci_gate}" = SUCCESS ] || flags+=(CI-GATE-NOT-GREEN)
fi

has() { local f; for f in ${flags[@]+"${flags[@]}"}; do [ "${f}" = "$1" ] && return 0; done; return 1; }

if has MERGE-CONFLICT; then verdict=conflicts-found
elif has MERGE-STATE-UNKNOWN; then verdict=pending-merge-check
elif has BRANCH-BEHIND || has PR-IS-DRAFT || has CI-GATE-NOT-GREEN; then verdict=blocks-ready
else verdict=clear
fi

echo "verdict=${verdict}"
for f in ${flags[@]+"${flags[@]}"}; do echo "flag=${f}"; done
echo "mergeable=${mergeable}"
echo "merge_state_status=${status}"
echo "merge_state_exit=${ms}"
echo "base_ref=${base}"
if has PR-IS-DRAFT; then
  if ! labels="$(gh pr view "${pr}" --json labels --jq '[.labels[].name] | join(",")' 2>/dev/null)"; then
    echo "needs_rebase=unknown"
  else
    case ",${labels}," in *,needs-rebase,*) echo "needs_rebase=true" ;; *) echo "needs_rebase=false" ;; esac
  fi
fi
if [ "${status}" = BLOCKED ]; then
  echo "ci_gate=${ci_gate}"
  # The note marks the survivable BLOCKED only; the other kind has its own flag.
  has CI-GATE-NOT-GREEN || echo "note=blocked"
fi
if has MERGE-CONFLICT; then
  conflicts=""
  if [ -n "${base}" ] && git fetch -q origin "${base}" 2>/dev/null; then
    conflicts="$(git merge-tree --write-tree HEAD "origin/${base}" 2>&1 | grep -i '^CONFLICT')"
  fi
  [ -z "${conflicts}" ] || printf '%s\n' "${conflicts}" | sed 's/^/conflict=/'
  # A conflict with no line to show for it says so, never stays silent.
  [ -n "${conflicts}" ] || [ -n "${marker_hits}" ] || echo "conflict_evidence=unavailable"
fi
[ -z "${marker_hits}" ] || printf '%s\n' "${marker_hits}" | sed 's/^/marker=/'
exit 0
