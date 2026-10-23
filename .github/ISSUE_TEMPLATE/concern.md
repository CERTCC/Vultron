---
name: "Concern"
about: "Flag a technical risk, debt item, security gap, or fragile area"
title: "[Concern] "
labels: concern
---

## Summary

<!-- One or two sentences describing the concern. -->

## Surface Symptom vs. Underlying Problem

<!--
State two things: (1) the naive, symptom-level reading someone would stop at,
and (2) the deeper problem underneath it that this concern is really about.
Naming both turns the concern into a worked example of the judgment involved —
it shows the jump from the obvious reading to the real one, which is exactly
what makes concerns useful to learn from later.

If the deeper problem also implies parts of the current design that are
*already correct and should not be touched*, say so — knowing what to leave
alone is as valuable as knowing what to change.

Omit only if there genuinely is no gap between the surface reading and the
underlying problem.
-->

## Category

<!-- Check the one that best fits. -->

- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [ ] Other

## Severity

<!-- high / medium / low -->

## Evidence

<!-- Files, modules, or lines where this concern is visible. -->

- `<!-- path/to/file.py -->`

## Impact if Ignored

<!-- What breaks, degrades, or becomes harder if this is not addressed? -->

## Suggested Action

<!-- Recommended fix, mitigation, or next investigation step. -->
