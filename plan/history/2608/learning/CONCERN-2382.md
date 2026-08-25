---
source: CONCERN-2382
timestamp: '2026-08-21T16:41:00.376427+00:00'
title: 'concern: 98% of MUST requirements have no verification criteria — MS-05-003
  is self-violating'
type: learning
---

2,392 of 2,439 requirements (98%) in `specs/` have no `verification:` field populated. This violates the project's own MS-05-003 meta-requirement ("measurable acceptance criteria MUST be provided where applicable"). There is no documented method to confirm any MUST requirement has been satisfied after implementation.

**Surface symptom:** `verification: null` on 2,392/2,439 requirements across all spec YAML files. Raw YAML check: only 47 requirements have any verification criteria.

**Underlying problem:** The `lint.py` linter does not enforce MS-05-003 for `priority: MUST` requirements, so this gap is invisible and grows unnoticed with every new requirement added. Neither implementers nor reviewers have a testability contract — they know what to build but not how to confirm it is correct. The meta-spec is in self-violating state.

**Evidence:**

- Python analysis of compiled spec corpus (2,439 requirements): `Missing verification: 2439/2439 (100%)` in the rendered export.
- Raw YAML check across `specs/*.yaml`: `Have verification criteria: 47` out of 2,439 requirements.
- `specs/meta-specifications.yaml` MS-05-003: "Requirements MUST be testable; measurable acceptance criteria MUST be provided where applicable."
- `vultron/metadata/specs/lint.py` does not currently check for the presence of `verification:` on MUST requirements.
- Surfaced during NASA system design process requirements validation review (2026-08-19).

**Resolved**: 2026-08-21 — implementation tracked in #2466, #2467.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2465>.
Spec: `specs/meta-specifications.yaml` (MS-10-003, MS-10-005).
Notes: `notes/specs-vs-adrs.md`.
