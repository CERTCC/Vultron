---
source: NOTES-rfc-review-rubric--changelog
timestamp: '2026-10-14T14:26:52.926292+00:00'
title: 'rfc-review-rubric: changelog and retired-item note'
type: note
---

Archived from `notes/rfc-review-rubric.md` by #4498: the rubric's changelog and
its "retired item" story are project history, not review guidance (NF-08). The
covering mechanisms stay in the rubric's "Mechanized" table; the round-2 finding
classes were folded into the rubric's numbered sections as rules.

---

Retired item, kept per this rubric's own rule: this document was outside
`lint-docs`' target set until #3318, because the linter read the `_` nav-exclusion
prefix as "not a page" and dropped every fragment. An American-spelling
regression reached `main` through that gap during the PR #3265 review round. The
two rows above are the covering mechanism; the `[M]` items in "Structural
Completeness" and "Terminology Consistency" are mechanical for this document
again.

---

## Changelog

| Date | Change | Source |
|------|--------|--------|
| 2026-09-16 | Initial rubric created from review of PR #3265 | Review of draft RFC commit d4572cee7 |
| 2026-09-16 | Added §8 Readability and Concept Flow, §9 Content Modularity, §10 Concept Lifecycle Coverage; extended §2 (Observer dual-use, track/drive definition), §4 (OQ fragment consistency), §5 (nav-note accuracy) — 24 additional gap items from top-to-bottom sequential audit of assembled spec | PR #3265 review comment |
| 2026-09-16 | Added §11 Round-2 Finding Classes (9 items) and two Mechanized entries; noted that `lint-docs` skips this document's fragments. Corrected §10: "Bug Bounty Operator" is not a role anywhere in the glossary, specs, notes or code — only the *Bug Bounty Platform* named configuration exists | Second review round of PR #3265 |
| 2026-09-28 | Retired the "`lint-docs` does not cover this document" warning: fragments are linted as source, page-scoped rules go to the assembled `index.md`, and `codespell` is the SG-37 floor. Two Mechanized rows added; the `[M]`-treated-as-`[J]` instruction removed | #3318 |
| 2026-10-01 | The specification is a section of pages: added page-map, tip and landing-page checks to Structural Completeness; Cross-Reference Integrity requires links to the owning page and citations with number and name; mechanized lint row evaluates page-scoped rules on every assembling page; corrected stale section numbers (the shorthand table is §5.7 Shorthand to Wire Form Mapping; the four-dimensions note is §3.3 Tracking Dimensions; the named-configurations preview belongs in §3.2 What a Deployment Looks Like; the case histories are annexes) | #4060 |
