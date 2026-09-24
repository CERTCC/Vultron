#!/usr/bin/env bash
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
#   - Later is a deliberate deferral, not the Someday default: reported, not
#     touched.
#   - Someday and off-board descendants are raised (off-board ones are added).
#   - A descendant's own tier, after raising, is the tier its children follow.
#
# Usage:
#   sync-epic-schedules.sh [--apply] [--tiers "Focus Now Next"] [<EPIC>...]
#     With no EPIC numbers, syncs every open Epic in the given tiers.
#     Without --apply it is a dry run: it prints the plan and changes nothing.
#
# Output: one line per descendant that differs from its Epic:
#   RAISE|SKIP-ABOVE|SKIP-LATER  #<epic>(<tier>) > #<issue> <from> -> <to>  <title>
set -euo pipefail

SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY=0
TIERS="Focus Now Next"
EPICS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --tiers) TIERS="${2:?--tiers needs a value}"; shift ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) EPICS+=("$1") ;;
  esac
  shift
done

rank() {
  case "$1" in
    Focus) echo 0 ;; Now) echo 1 ;; Next) echo 2 ;; Later) echo 3 ;;
    Someday) echo 4 ;; *) echo 5 ;;
  esac
}

# Emit "<number>\t<state>\t<tier|OFF-BOARD>\t<childCount>\t<title>" per child.
children() {
  gh api graphql --paginate -f query='query($endCursor:String){
    repository(owner:"CERTCC", name:"Vultron") { issue(number:'"$1"') {
      subIssues(first:100, after:$endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes { number title state subIssues(first:1) { totalCount }
          projectItems(first:5) { nodes { project { number }
            fieldValueByName(name:"Schedule") {
              ... on ProjectV2ItemFieldSingleSelectValue { name } } } } }
      } } } }' --jq '.data.repository.issue.subIssues.nodes[]
      | [.number, .state,
         ([.projectItems.nodes[] | select(.project.number == 24)
           | .fieldValueByName.name][0] // "OFF-BOARD"),
         .subIssues.totalCount, .title[0:70]] | @tsv'
}

# Tier of one issue on Project #24, or OFF-BOARD.
tier_of() {
  gh api graphql -f query='{ repository(owner:"CERTCC", name:"Vultron") {
    issue(number:'"$1"') { projectItems(first:5) { nodes { project { number }
      fieldValueByName(name:"Schedule") {
        ... on ProjectV2ItemFieldSingleSelectValue { name } } } } } } }' \
    --jq '[.data.repository.issue.projectItems.nodes[]
           | select(.project.number == 24) | .fieldValueByName.name][0]
          // "OFF-BOARD"'
}

RAISED=0
# walk <root-epic> <parent> <tier the parent's children should reach>
walk() {
  local root="$1" parent="$2" want="$3" n state tier kids title next
  while IFS=$'\t' read -r n state tier kids title; do
    [ "$state" = OPEN ] || continue
    next="$tier"
    if [ "$(rank "$tier")" -gt "$(rank "$want")" ]; then
      if [ "$tier" = Later ]; then
        echo "SKIP-LATER  #$root($want) > #$n $tier -> $tier  $title"
      else
        echo "RAISE       #$root($want) > #$n $tier -> $want  $title"
        if [ "$APPLY" = 1 ]; then
          bash "$SHARED/add-to-project.sh" "$n" "$want" >/dev/null
        fi
        RAISED=$((RAISED + 1))
        next="$want"
      fi
    elif [ "$(rank "$tier")" -lt "$(rank "$want")" ]; then
      echo "SKIP-ABOVE  #$root($want) > #$n $tier -> $tier  $title"
    fi
    if [ "$kids" -gt 0 ]; then walk "$root" "$n" "$next"; fi
  done < <(children "$parent")
}

if [ ${#EPICS[@]} -eq 0 ]; then
  PROJECT_ID=$(bash "$SHARED/board-id.sh" project)
  mapfile -t EPICS < <(gh api graphql --paginate -f query='query($endCursor:String){
    node(id:"'"$PROJECT_ID"'") { ... on ProjectV2 {
      items(first:100, after:$endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes { fieldValueByName(name:"Schedule") {
                  ... on ProjectV2ItemFieldSingleSelectValue { name } }
                content { ... on Issue { number state issueType { name } } } }
      } } } }' --jq '.data.node.items.nodes[]
      | select(.content.issueType.name == "Epic" and .content.state == "OPEN")
      | "\(.content.number) \(.fieldValueByName.name)"' \
    | while read -r n t; do
        case " $TIERS " in *" $t "*) echo "$n" ;; esac
      done)
fi

for epic in "${EPICS[@]}"; do
  t=$(tier_of "$epic")
  case "$t" in
    Focus|Now|Next|Later) walk "$epic" "$epic" "$t" ;;
    *) echo "skip #$epic: Epic is $t, nothing to inherit" >&2 ;;
  esac
done

if [ "$APPLY" = 1 ]; then
  echo "Raised $RAISED descendant(s)." >&2
else
  echo "Dry run: $RAISED descendant(s) would be raised. Re-run with --apply." >&2
fi
