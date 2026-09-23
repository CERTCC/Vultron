#!/bin/bash
# Wrapper to suppress false-positive mkdocs warnings
#
# mkdocs build --strict reports false-positive "Inline reference to unknown
# key" warnings when griffe's docstring parser encounters Python decorators
# (@dataclass, @main.command, etc) and misinterprets them as bibliography
# citations.
#
# This wrapper counts these false positives and exits with code 0 if only
# false-positive warnings are present.
#
# It suppresses ONLY the classified false positives. Any other non-zero exit
# from mkdocs -- a config error, a plugin traceback, ERROR-level output -- is
# propagated, because such a failure emits no "WARNING -" lines and would
# otherwise be counted as zero real warnings and silently pass the gate.

set -e

# Create temp file for output
TEMP_OUTPUT=$(mktemp)
trap "rm -f '$TEMP_OUTPUT'" EXIT

# Run mkdocs build, capturing output AND its exit status. Do not pipe here: a
# pipeline exits with its last stage's status, so `| tee "$TEMP_OUTPUT"` would
# report 0 for a hard mkdocs failure. See
# .agents/skills/run-tests/SKILL.md § Constraints.
set +e
uv run mkdocs build --strict > "$TEMP_OUTPUT" 2>&1
MKDOCS_RC=$?
set -e
cat "$TEMP_OUTPUT"

# Count all warnings (lines starting with "WARNING -")
#
# Note: `grep -c` already prints "0" when it finds no matches, and *also* exits
# non-zero. An `|| echo 0` fallback therefore appends a second "0", so the
# substitution captures "0\n0" and every downstream $(( )) dies with
# "syntax error in expression". Use `|| true` to swallow the exit status
# without adding output, and default the value in case grep prints nothing.
TOTAL=$(grep -c "^WARNING -" "$TEMP_OUTPUT" || true)

# Count false-positive warnings (known decorator/keyword names)
FALSE=$(grep "^WARNING -  Inline reference to unknown key" "$TEMP_OUTPUT" | grep -cE "(petterogren7535|main|v4|dataclass|prefix|base|context|pytest)" || true)

# Count print-site warnings (version-specific false positive)
PRINT=$(grep -c "^WARNING -  \[mkdocs-print-site\]" "$TEMP_OUTPUT" || true)

# Count hard errors. These are never false positives.
ERRORS=$(grep -c "^ERROR -" "$TEMP_OUTPUT" || true)

TOTAL=${TOTAL:-0}
FALSE=${FALSE:-0}
PRINT=${PRINT:-0}
ERRORS=${ERRORS:-0}

# Total false positives
FALSE=$((FALSE + PRINT))

# Calculate real warnings
REAL=$((TOTAL - FALSE))

# Report status
if [ "$REAL" -gt 0 ]; then
    echo ""
    echo "✗ Documentation build failed with $REAL real warning(s)"
    exit 1
fi

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "✗ Documentation build failed with $ERRORS error(s)"
    exit 1
fi

# No real warnings and no errors. If mkdocs still exited non-zero, it failed for
# a reason this wrapper cannot classify, and there is nothing to suppress --
# propagate rather than passing the gate on an unexplained failure.
if [ "$MKDOCS_RC" -ne 0 ] && [ "$FALSE" -eq 0 ]; then
    echo ""
    echo "✗ mkdocs build --strict exited $MKDOCS_RC with no classifiable warnings"
    echo "  (see output above — likely a config error or a plugin failure)"
    exit "$MKDOCS_RC"
fi

if [ "$FALSE" -gt 0 ]; then
    echo ""
    echo "✓ Successfully built docs! (Suppressed $FALSE false-positive warnings)"
fi
exit 0
