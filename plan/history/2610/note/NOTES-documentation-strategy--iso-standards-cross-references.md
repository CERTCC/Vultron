---
source: NOTES-documentation-strategy--iso-standards-cross-references
timestamp: '2026-10-14T14:27:24.447291+00:00'
title: 'documentation-strategy: ISO standards cross-references (future work)'
type: note
---

Archived from `notes/documentation-strategy.md` by #4498: the section was a
reference list plus a future-work item. The crosswalk pages under
`docs/reference/iso_crosswalks/` now map ISO clauses to Protocol Specification
sections (#3625), which delivers the clause-level alignment the item asked
for; the finer message-type-level mapping is carried as a comment on
epic #615 (Documentation: deferred enhancements and crosswalks).

---

## ISO Standards Cross-References

High-level cross-references to relevant ISO standards are documented in
`docs/reference/iso_crosswalks/`:

- `iso_29147_2018.md` — ISO/IEC 29147:2018 (Vulnerability Disclosure)
- `iso_30111_2019.md` — ISO/IEC 30111:2019 (Vulnerability Handling Processes)
- `iso_5895_2022.md` — ISO/IEC 5895:2022 (Multi-Party Coordinated Vulnerability Disclosure)

**Current state**: Cross-references are at a high level, mapping general
protocol concepts to ISO standard sections.

**Future work**: As the ActivityStreams vocabulary implementation matures,
it would be valuable to add more specific cross-references — linking
particular `MessageSemantics` values, handler behaviors, and vocabulary
types to the ISO standard requirements they satisfy. This would help
demonstrate standards alignment and identify any gaps.

**Priority**: Low for the prototype, but useful for eventual standardization
efforts or external communication about the project's standards alignment.
