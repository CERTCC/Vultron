#!/usr/bin/env bash
# GraphQL and jq use `$var` syntax inside single quotes on purpose.
# shellcheck disable=SC2016
# sync-epic-schedules.sh — raise an Epic's open descendants to the Epic's
# Schedule tier on Project #24.
#
# New issues default to Someday even when they are filed under a scheduled
# Epic, so a Now-tier Epic's children can quietly sit in Triage. This finds
# every open descendant (sub-issues, recursively) ranked below its Epic and
# raises it to the Epic's tier.
#
# Rules:
#   - Raise only, never lower: a child ranked above its Epic was prioritized
#     deliberately and is reported, not touched.
#   - Only the un-prioritized states are raised: Someday, on-board with no
#     Schedule (UNSET), and off-board (added to the board). Later is a
#     deliberate deferral and any other value (e.g. Completed) is not a tier:
#     both are reported, not touched.
#   - A descendant's own tier, after raising, is the tier its children follow.
#   - A closed descendant is skipped with its whole subtree.
#   - An Epic nested under another Epic being synced is walked once, as a
#     descendant of the outermost one.
#
# Usage:
#   sync-epic-schedules.sh [--apply] [--tiers "Focus Now Next"] [<EPIC>...]
#     With no EPIC numbers, syncs every open Epic in the given tiers.
#     --tiers only selects Epics; it is ignored when EPIC numbers are given.
#     Without --apply it is a dry run: it prints the plan and changes nothing.
#
# Output: one line per descendant that differs from its Epic:
#   RAISE|SKIP-ABOVE|SKIP-LATER|SKIP-OTHER  #<epic>(<tier>) > #<issue> <from> -> <to>  <title>
set -euo pipefail

SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY=0
TIERS="Focus Now Next"
TIERS_GIVEN=0
EPICS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --tiers) TIERS="${2:?--tiers needs a value}"; TIERS_GIVEN=1; shift ;;
    -h|--help) sed -n '4,31p' "$0"; exit 0 ;;
    -*) echo "❌ Unknown option: $1 (see --help)" >&2; exit 1 ;;
    *)
      if ! [[ "$1" =~ ^[0-9]+$ ]]; then
        echo "❌ Not an issue number: $1" >&2; exit 1
      fi
      EPICS+=("$1") ;;
  esac
  shift
done

for t in $TIERS; do
  case "$t" in
    Focus|Now|Next|Later) ;;
    *) echo "❌ Unknown tier in --tiers: $t (use Focus Now Next Later)" >&2
       exit 1 ;;
  esac
done
if [ "$TIERS_GIVEN" = 1 ] && [ ${#EPICS[@]} -gt 0 ]; then
  echo "⚠ --tiers is ignored when Epic numbers are given" >&2
fi

rank() {
  case "$1" in
    Focus) echo 0 ;; Now) echo 1 ;; Next) echo 2 ;; Later) echo 3 ;;
    *) echo 4 ;;
  esac
}

# Schedule of an issue's projectItems on Project #24: its value, UNSET, or
# OFF-BOARD. Shared jq filter; the input is a projectItems.nodes array.
TIER_JQ='([.[] | select(.project.number == 24)] as $i
  | if ($i | length) == 0 then "OFF-BOARD"
    else ($i[0].fieldValueByName.name // "UNSET") end)'
PROJECT_ITEMS='projectItems(first:20) { nodes { project { number }
  fieldValueByName(name:"Schedule") {
    ... on ProjectV2ItemFieldSingleSelectValue { name } } } }'

# Emit "<number>\t<state>\t<tier>\t<childCount>\t<title>" per child.
children() {
  gh api graphql --paginate -f query='query($endCursor:String){
    repository(owner:"CERTCC", name:"Vultron") { issue(number:'"$1"') {
      subIssues(first:100, after:$endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes { number title state subIssues(first:1) { totalCount }
          '"$PROJECT_ITEMS"' }
      } } } }' --jq '.data.repository.issue.subIssues.nodes[]
      | [.number, .state, (.projectItems.nodes | '"$TIER_JQ"'),
         .subIssues.totalCount, .title[0:70]] | @tsv'
}

# Emit "<state>\t<issueType|NONE>\t<tier>\t<ancestor numbers, space-separated>"
# for one issue (ancestors up to four levels up).
describe() {
  gh api graphql -f query='{ repository(owner:"CERTCC", name:"Vultron") {
    issue(number:'"$1"') { state issueType { name }
      parent { number parent { number parent { number parent { number } } } }
      '"$PROJECT_ITEMS"' } } }' \
    --jq '.data.repository.issue
      | [.state, (.issueType.name // "NONE"),
         (.projectItems.nodes | '"$TIER_JQ"'),
         ([.parent | recurse(.parent; . != null) | select(. != null) | .number]
          | map(tostring)
          | join(" "))] | @tsv'
}

RAISED=0
# walk <root-epic> <parent> <tier the parent's children should reach>
walk() {
  local root="$1" parent="$2" want="$3" rows n state tier kids title next
  # Fetch before looping: a failure inside `< <(...)` would escape set -e and
  # make the subtree look empty.
  rows=$(children "$parent")
  [ -n "$rows" ] || return 0
  while IFS=$'\t' read -r n state tier kids title; do
    [ "$state" = OPEN ] || continue
    next="$tier"
    case "$tier" in
      Focus|Now|Next|Later)
        if [ "$(rank "$tier")" -lt "$(rank "$want")" ]; then
          echo "SKIP-ABOVE  #$root($want) > #$n $tier -> $tier  $title"
        elif [ "$(rank "$tier")" -gt "$(rank "$want")" ]; then
          echo "SKIP-LATER  #$root($want) > #$n $tier -> $tier  $title"
        fi ;;
      Someday|UNSET|OFF-BOARD)
        echo "RAISE       #$root($want) > #$n $tier -> $want  $title"
        if [ "$APPLY" = 1 ]; then
          bash "$SHARED/add-to-project.sh" "$n" "$want" >/dev/null </dev/null
        fi
        RAISED=$((RAISED + 1))
        next="$want" ;;
      *)
        echo "SKIP-OTHER  #$root($want) > #$n $tier -> $tier  $title"
        next="$want" ;;
    esac
    if [ "$kids" -gt 0 ]; then walk "$root" "$n" "$next"; fi
  done <<<"$rows"
}

if [ ${#EPICS[@]} -eq 0 ]; then
  PROJECT_ID=$(bash "$SHARED/board-id.sh" project)
  rows=$(gh api graphql --paginate -f query='query($endCursor:String){
    node(id:"'"$PROJECT_ID"'") { ... on ProjectV2 {
      items(first:100, after:$endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes { fieldValueByName(name:"Schedule") {
                  ... on ProjectV2ItemFieldSingleSelectValue { name } }
                content { ... on Issue { number state issueType { name } } } }
      } } } }' --jq '.data.node.items.nodes[]
      | select(.content.issueType.name == "Epic" and .content.state == "OPEN")
      | "\(.content.number) \(.fieldValueByName.name)"')
  while read -r n t; do
    case " $TIERS " in *" $t "*) EPICS+=("$n") ;; esac
  done <<<"$rows"
fi

# Pass 1: keep the open, scheduled Epics; remember each one's tier and
# ancestors.
declare -A TIER_OF ANCESTORS_OF
ROOTS=()
for epic in "${EPICS[@]}"; do
  info=$(describe "$epic")
  IFS=$'\t' read -r state type t ancestors <<<"$info"
  if [ "$state" != OPEN ] || [ "$type" != Epic ]; then
    echo "skip #$epic: not an open Epic ($state, $type)" >&2; continue
  fi
  case "$t" in
    Focus|Now|Next|Later) ;;
    *) echo "skip #$epic: Epic is $t, nothing to inherit" >&2; continue ;;
  esac
  TIER_OF[$epic]="$t"
  ANCESTORS_OF[$epic]="$ancestors"
  ROOTS+=("$epic")
done

# Pass 2: an Epic nested under another root is reached from that root's walk;
# walking it again would double-count it and plan against a stale tier.
for epic in "${ROOTS[@]}"; do
  covered=""
  for a in ${ANCESTORS_OF[$epic]}; do
    [ -n "${TIER_OF[$a]:-}" ] && covered="$a"
  done
  if [ -n "$covered" ]; then
    echo "skip #$epic: walked as a descendant of #$covered" >&2; continue
  fi
  walk "$epic" "$epic" "${TIER_OF[$epic]}"
done

if [ "$APPLY" = 1 ]; then
  echo "Raised $RAISED descendant(s)." >&2
else
  echo "Dry run: $RAISED descendant(s) would be raised. Re-run with --apply." >&2
fi
