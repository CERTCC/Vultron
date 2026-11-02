#!/usr/bin/env bash
# sync-decision.sh — decide whether pr-execute merges the base into a pushed PR
# (pr-execute Phase 5 Step 2, PAD-18-004, PAD-18-014, ADR-0138).
#
# Usage: sync-decision.sh <pr-number> <base-ref>
#          fetch origin/<base-ref>, then run merge-state.sh, a trial
#          `git merge-tree`, and `targeted-tests --overlap`, and decide
#        sync-decision.sh --decide <merge-state-exit> <merge-state-status> \
#                                  <merge-tree-exit> <overlap-exit>
#          decide from inputs already collected
#
# Rules, first match wins (DIRTY counts as CONFLICTING whatever the exit):
#   merge-tree exit not 0/1, or overlap exit 2  -> setup-error
#   merge-state exit 1, or status DIRTY         -> merge          (conflicting)
#   merge-tree exit 1                           -> merge          (conflicting)
#   merge-state exit 0, BEHIND, merge-tree 0    -> update-on-github (behind)
#   merge-state exit 0 or 2, overlap exit 1     -> no-merge       (deferred)
#   merge-state exit 0 or 2                     -> no-merge       (none)
#
# Output, one `key=value` per line:
#   verdict=<setup-error|merge|update-on-github|no-merge>
#   merge_reason=<conflicting|behind|deferred|none>  (not on setup-error)
#   reason=<text>                                    (setup-error only)
#   merge_state_exit=  merge_state_status=  merge_tree_exit=  overlap_exit=
#   conflict_path=<path>  one per file merge-tree reports conflicted
#   overlap_path=<path>   one per path both sides changed
# Exit: 0 a decision was made; 2 setup-error or usage error.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { echo "usage: $0 <pr-number> <base-ref> | --decide MS STATUS MT OV" >&2; exit 2; }

# decide MS STATUS MT OV — print verdict and merge_reason; return 2 on setup error.
decide() {
  local ms="$1" status="$2" mt="$3" ov="$4"
  if [ "${mt}" != 0 ] && [ "${mt}" != 1 ] || [ "${ov}" = 2 ]; then
    echo "verdict=setup-error"
    echo "reason=merge-tree exit ${mt}, overlap exit ${ov}: unknown base ref?"
    return 2
  fi
  if [ "${ms}" = 1 ] || [ "${status}" = DIRTY ] || [ "${mt}" = 1 ]; then
    echo "verdict=merge"; echo "merge_reason=conflicting"
  elif [ "${ms}" = 0 ] && [ "${status}" = BEHIND ]; then
    echo "verdict=update-on-github"; echo "merge_reason=behind"
  elif [ "${ov}" = 1 ]; then
    echo "verdict=no-merge"; echo "merge_reason=deferred"
  else
    echo "verdict=no-merge"; echo "merge_reason=none"
  fi
}

inputs() {
  echo "merge_state_exit=$1"
  echo "merge_state_status=$2"
  echo "merge_tree_exit=$3"
  echo "overlap_exit=$4"
}

if [ "${1:-}" = "--decide" ]; then
  [ "$#" -eq 5 ] || usage
  for n in "$2" "$4" "$5"; do
    [[ "${n}" =~ ^[0-9]+$ ]] || usage
  done
  case "$2" in 0|1|2) ;; *) usage ;; esac
  decide "$2" "$3" "$4" "$5"; rc=$?
  inputs "$2" "$3" "$4" "$5"
  exit "${rc}"
fi

[ "$#" -eq 2 ] || usage
pr="$1"
base="$2"
command -v jq >/dev/null || { echo "sync-decision: jq not found" >&2; exit 2; }

if ! git fetch -q origin "${base}"; then
  echo "verdict=setup-error"
  echo "reason=git fetch origin ${base} failed"
  exit 2
fi

state_json="$(bash "${here}/merge-state.sh" "${pr}")"; ms=$?
status="$(printf '%s' "${state_json}" | jq -r '.merge_state_status // "UNKNOWN"' 2>/dev/null)"
status="${status:-UNKNOWN}"

tree_out="$(git merge-tree --write-tree --name-only HEAD "origin/${base}" 2>&1)"; mt=$?
overlap_out="$(PYTHONPATH= uv run targeted-tests --base "origin/${base}" --overlap 2>/dev/null)"; ov=$?

decide "${ms}" "${status}" "${mt}" "${ov}"; rc=$?
inputs "${ms}" "${status}" "${mt}" "${ov}"
# merge-tree --name-only: the tree id, then one conflicted path per line up
# to the first blank line, then the merge messages.
if [ "${mt}" = 1 ]; then
  printf '%s\n' "${tree_out}" | awk 'NR == 1 { next } /^$/ { exit } { print "conflict_path=" $0 }'
fi
if [ "${ov}" = 1 ]; then
  printf '%s\n' "${overlap_out}" | awk 'NF { print "overlap_path=" $0 }'
fi
exit "${rc}"
