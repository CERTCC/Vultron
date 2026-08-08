---
source: CONCERN-1806
timestamp: '2026-08-07T20:55:19.948587+00:00'
title: 'Spec-to-test traceability gap: ~1% of requirements carry @pytest.mark.spec;
  audit, decorate, and ratchet'
type: learning
---

Only ~15 of ~2,215 spec requirements (well under 1%) carry a `@pytest.mark.spec` marker linking a test to the requirement it verifies. This makes spec→test coverage effectively invisible: we cannot mechanically answer "is requirement XX-NN-NNN verified by any test?" for 99% of the spec registry.

**Surface symptom vs. underlying problem:** This is primarily a **traceability** gap, not (only) a testing gap. The reference implementation has a large, mature test suite; the issue is that the vast majority of those tests are **not decorated** with the `@pytest.mark.spec("XX-NN-NNN")` marker that ties them back to the requirements they exercise. Coverage exists but is not *attributable*.

**Root cause:** SR-05-004 was a SHOULD with no enforcement mechanism, allowing adoption to drift toward near-zero with no signal.

**Resolution:** 2026-08-07 — implementation tracked in #2116, #2117.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2115>.
Spec: `specs/spec-registry.yaml` (SR-05-004 upgraded to MUST for protocol-kind; SR-05-005 added for CI floor).
