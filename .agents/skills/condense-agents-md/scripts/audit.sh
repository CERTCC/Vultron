#!/usr/bin/env bash
# audit.sh — Show section sizes for an AGENTS.md file
# Usage: bash audit.sh [path/to/AGENTS.md]
#
# Prints each heading (## or ###), its line span, and a running total.
# Highlights sections over a configurable per-section warning threshold.

TARGET_FILE="${1:-AGENTS.md}"
TARGET_TOTAL=400
WARN_SECTION=40   # warn when a single section exceeds this many lines

if [[ ! -f "$TARGET_FILE" ]]; then
  echo "ERROR: '$TARGET_FILE' not found" >&2
  exit 1
fi

awk -v target="$TARGET_TOTAL" -v warn="$WARN_SECTION" '
BEGIN {
  section = "(preamble)"
  start = 1
  total = 0
  count = 0
}

/^## / || /^### / {
  lines = NR - start
  total += lines
  flag = (lines > warn) ? " ⚠" : ""
  printf "  %4d lines  %s%s\n", lines, section, flag
  section = $0
  start = NR
  count++
}

END {
  lines = NR - start + 1
  total += lines
  flag = (lines > warn) ? " ⚠" : ""
  printf "  %4d lines  %s%s\n", lines, section, flag
  printf "\n"
  printf "Total: %d lines  (target ≤ %d, excess: %d)\n", total, target, (total > target ? total - target : 0)
}
' "$TARGET_FILE"
