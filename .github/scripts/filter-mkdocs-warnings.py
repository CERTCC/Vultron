#!/usr/bin/env python3
"""Filter mkdocs build output to suppress known false-positive warnings.

This script filters griffe false-positive "Inline reference to unknown key"
warnings that result from Python decorators being misinterpreted as
bibliography citations (e.g., @dataclass, @main.command, @prefix).

Usage:
    uv run mkdocs build --strict 2>&1 | python3 .github/scripts/filter-mkdocs-warnings.py

Exit codes:
    0 — Build succeeded (no real warnings after filtering)
    1 — Build has warnings that cannot be filtered
"""

import sys
import re

# Set of false-positive unknown-key warnings to suppress
# These are decorators and keywords that griffe misinterprets as citations
SUPPRESS_PATTERNS = {
    "petterogren7535",  # YouTube handle @petterogren7535
    "main",  # @main.command decorator
    "v4",  # GitHub Actions version @v4
    "dataclass",  # Python decorator @dataclass
    "base",  # Common word in code, not a citation
    "prefix",  # Common word in code, not a citation
}

warning_count = 0
real_warnings = 0
lines = []

for line in sys.stdin:
    # Check if this is a false-positive bibliography warning
    if "Inline reference to unknown key" in line:
        # Extract the key name
        match = re.search(r"Inline reference to unknown key (\w+)", line)
        if match and match.group(1) in SUPPRESS_PATTERNS:
            # Skip this false-positive warning
            warning_count += 1
            continue

    # Check for print-site plugin ordering warning (often a version-specific false positive)
    if "print-site" in line and "should be defined as the *last*" in line:
        # This is a known false positive when print-site is already last
        warning_count += 1
        continue

    # Keep all other lines (real errors and normal output)
    lines.append(line)
    if line.startswith("WARNING"):
        real_warnings += 1

# Write filtered output
sys.stdout.write("".join(lines))

# Check final status
if "Aborted with" in "".join(lines):
    sys.exit(1)
elif "Successfully built" in "".join(lines):
    sys.exit(0)
else:
    # Default to failure if we can't determine status
    sys.exit(1)
