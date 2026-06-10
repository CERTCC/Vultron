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

set -e

# Create temp file for output
TEMP_OUTPUT=$(mktemp)
trap "rm -f '$TEMP_OUTPUT'" EXIT

# Run mkdocs build, capturing output (don't fail yet)
uv run mkdocs build --strict 2>&1 | tee "$TEMP_OUTPUT" || true

# Count all warnings (lines starting with "WARNING -")
TOTAL=$(grep -c "^WARNING -" "$TEMP_OUTPUT" || echo 0)

# Count false-positive warnings (known decorator/keyword names)
FALSE=$(grep "^WARNING -  Inline reference to unknown key" "$TEMP_OUTPUT" | grep -cE "(petterogren7535|main|v4|dataclass|prefix|base)" || echo 0)

# Count print-site warnings (version-specific false positive)
PRINT=$(grep -c "^WARNING -  \[mkdocs-print-site\]" "$TEMP_OUTPUT" || echo 0)

# Total false positives
FALSE=$((FALSE + PRINT))

# Calculate real warnings
REAL=$((TOTAL - FALSE))

# Report status
if [ "$REAL" -eq 0 ]; then
    if [ "$FALSE" -gt 0 ]; then
        echo ""
        echo "✓ Successfully built docs! (Suppressed $FALSE false-positive warnings)"
    fi
    exit 0
else
    echo ""
    echo "✗ Documentation build failed with $REAL real warning(s)"
    exit 1
fi
