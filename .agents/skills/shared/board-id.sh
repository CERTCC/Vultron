#!/usr/bin/env bash
# board-id.sh — resolve GitHub board constants (node IDs, field/option IDs,
# issue-type IDs) by human-readable name, backed by a TTL cache.
#
# These IDs are server-generated and MUTABLE — editing a ProjectV2 single-select
# field's options rotates every option ID. Hardcoding them anywhere drifts
# stale. This script derives them from the live board and caches the result, so
# no skill ever needs to name a raw ID.
#
# Bootstrap inputs (stable, human-meaningful — the only hardcoded values):
#   owner=CERTCC  repo=Vultron  project number=24
#
# Usage:
#   board-id.sh repo                     # repo node ID
#   board-id.sh project                  # Project #24 node ID
#   board-id.sh schedule-field           # Schedule field ID
#   board-id.sh schedule <Name>          # Schedule option ID (Now|Next|Later|Someday|Focus|Completed)
#   board-id.sh issue-type <Name>        # issue-type ID (Task|Bug|Feature|Idea|Epic|Concern)
#   board-id.sh --refresh [<args...>]    # force re-fetch, then resolve (args optional)
#   board-id.sh --dump                   # print the whole cache as JSON
#
# Exit codes: 0 ok; 1 usage/resolution error; 2 network/API error.
set -euo pipefail

OWNER="CERTCC"
REPO="Vultron"
PROJECT_NUMBER=24
TTL_SECONDS=${BOARD_ID_TTL:-86400}   # 24h; override with BOARD_ID_TTL env

CACHE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/board-ids.json"

# --- cache freshness ---------------------------------------------------------
cache_fresh() {
  [ -f "$CACHE" ] || return 1
  local fetched now age
  fetched=$(jq -r '.fetched_at_epoch // 0' "$CACHE" 2>/dev/null || echo 0)
  now=$(date +%s)
  age=$(( now - fetched ))
  [ "$age" -ge 0 ] && [ "$age" -lt "$TTL_SECONDS" ]
}

# --- fetch + rewrite cache ---------------------------------------------------
refresh_cache() {
  local now data
  now=$(date +%s)

  # One query for everything derivable from owner/name/project-number.
  data=$(gh api graphql -f query='
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) {
        id
        issueTypes(first:50) { nodes { id name } }
      }
      organization(login:$owner) {
        projectV2(number:$number) {
          id
          field(name:"Schedule") {
            ... on ProjectV2SingleSelectField { id options { id name } }
          }
        }
      }
    }' \
    -f owner="$OWNER" -f repo="$REPO" -F number="$PROJECT_NUMBER" 2>/dev/null) || {
      echo "❌ board-id: GraphQL query failed (auth/network?)." >&2
      return 2
    }

  # Reshape into a flat lookup cache. Fail loudly if the board shape is empty.
  echo "$data" | jq --argjson now "$now" '
    {
      fetched_at_epoch: $now,
      repo:            .data.repository.id,
      project:         .data.organization.projectV2.id,
      "schedule-field": .data.organization.projectV2.field.id,
      schedule:        (.data.organization.projectV2.field.options
                          | map({(.name): .id}) | add // {}),
      "issue-type":    (.data.repository.issueTypes.nodes
                          | map({(.name): .id}) | add // {})
    }
    | if (.repo == null or .project == null or .schedule == {} or ."issue-type" == {})
      then error("board-id: live board returned empty/unexpected shape")
      else . end
  ' > "$CACHE.tmp" || {
      echo "❌ board-id: could not parse board response." >&2
      rm -f "$CACHE.tmp"
      return 2
    }
  mv "$CACHE.tmp" "$CACHE"
}

# Refresh, but tolerate failure when a usable cache already exists: a stale
# cache beats a hard exit (e.g. offline, or the committed cache aged past its
# TTL). Only a missing-and-unfetchable cache is fatal.
ensure_cache() {
  if refresh_cache; then
    return 0
  fi
  if [ -f "$CACHE" ]; then
    echo "⚠️  board-id: refresh failed; using existing (possibly stale) cache." >&2
    return 0
  fi
  return 2
}

# --- resolution --------------------------------------------------------------
resolve() {
  local category="${1:-}" name="${2:-}"
  case "$category" in
    repo|project|schedule-field)
      # No -e: a miss prints empty and still exits 0, so the caller can tell a
      # valid-but-absent name (empty output) apart from a usage error (below).
      jq -r --arg k "$category" '.[$k] // empty' "$CACHE"
      ;;
    schedule|issue-type)
      [ -n "$name" ] || { echo "❌ board-id: '$category' needs a name argument." >&2; return 1; }
      jq -r --arg c "$category" --arg n "$name" '.[$c][$n] // empty' "$CACHE"
      ;;
    *)
      echo "❌ board-id: unknown category '$category'." >&2
      echo "   Categories: repo | project | schedule-field | schedule <Name> | issue-type <Name>" >&2
      return 1
      ;;
  esac
}

# --- main --------------------------------------------------------------------
FORCE=0
if [ "${1:-}" = "--refresh" ]; then FORCE=1; shift; fi

if [ "${1:-}" = "--dump" ]; then
  { [ "$FORCE" = 1 ] || ! cache_fresh; } && ensure_cache
  cat "$CACHE"; exit 0
fi

# Bare `--refresh` with no category: refresh-only, then exit (args are optional).
if [ "$FORCE" = 1 ] && [ -z "${1:-}" ]; then
  ensure_cache && echo "board-id: cache refreshed." >&2
  exit 0
fi

if [ "$FORCE" = 1 ] || ! cache_fresh; then
  ensure_cache
fi

# A cache miss on a valid-looking name may mean the board changed since last
# fetch — refresh once and retry before giving up.
if ! val=$(resolve "$@"); then
  exit 1
fi
if [ -z "$val" ]; then
  ensure_cache
  val=$(resolve "$@") || exit 1
  if [ -z "$val" ]; then
    echo "❌ board-id: no match for '$*' even after refresh." >&2
    exit 1
  fi
fi
printf '%s\n' "$val"
