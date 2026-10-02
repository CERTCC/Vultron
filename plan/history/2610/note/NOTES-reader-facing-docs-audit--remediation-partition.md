---
source: NOTES-reader-facing-docs-audit--remediation-partition
timestamp: '2026-10-02T16:31:55.077002+00:00'
title: Remediation partition
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered + closed — every routed remediation task (#3524, #3526–#3528, #3619–#3628) is closed
**Superseded by:** the remediated pages under docs/; notes/reader-facing-docs-audit.md § Cross-page rulings

---

## Remediation partition

Remediation is cut by page, and each task owns its files exclusively. Nav
edits are never done in parallel: `mkdocs.yml` is held by #3528 and then by the
nav task (#3627), one after the other. A `relocate` verdict is a nav change, so it
belongs to the nav task. No page is moved on disk.

| Task | Owns |
|---|---|
| #3619 (R1) — Background | `topics/background/index.md`, `cvd_success.md`, the new `cvd-coordination-problem.md`, and the two repointed links in `vultron-spec/_introduction.md` and `_protocol-overview.md` |
| #3620 (R2) — Process models and formal protocol | `topics/process_models/**`, `reference/formal_protocol/**` |
| #3621 (R3) — Case lifecycle and protocol explanation | `topics/case_lifecycle/**`, `topics/behavior_logic/index.md` and `use-cases/**`, `protocol_flow.md`, `message_semantics.md`, `activity_vocabulary_design.md`, `actor-knowledge-model.md`, `reference_architecture.md`, missing page 3 |
| #3622 (R4) — Demos, tutorials, and scenarios | `tutorials/*` except the landing page, `howto/demos/**`, `reference/fv-demo-protocol.md`, `topics/scenarios/**` |
| #3623 (R5) — How-to guides, About, namespace | `howto/activitypub/**`, `howto/case_object.md`, `howto/process_implementation.md`, `howto/wire_capability.md`, `about/*`, `ns/index.md` |
| #3624 (R6) — Concept registries | `reference/glossary.md`, `terms.md`, `vultron-taxonomy.md`, `notation.md`, `quick_reference.md` |
| #3625 (R7) — Wire and protocol reference | the rest of `reference/` that is reader-facing, missing pages 4 and 5 |
| #3626 (R8) — Research | `topics/measuring_cvd/**`, `topics/other_uses/**`, `topics/future_work/**`, missing page 7 |
| #3627 (Nav) | `mkdocs.yml`: level order within each group, the 12 reader-facing pages that should sit behind a routing page, and every `relocate` verdict. Blocked by #3528. |
| #3628 (Practitioner pages) | missing pages 1 and 2. Blocked by #3524, whose entry pages route to them. |

The four section landing pages (`topics/`, `reference/`, `tutorials/`,
`howto/index.md`) belong to #3527's generator and are in no remediation task.
