---
title: "In-process demo fixtures seed every replica by hand, so a payload-completeness regression stays invisible until the Docker demos run the real bootstrap"
type: learning
timestamp: "2026-09-30T17:10:00Z"
source: ISSUE-2655
signal: theme-candidate
---

**Trigger.** Unit and in-process integration suites are green, but the Docker
demo fails with a "missing object" symptom on the *receiving* side (`no
VulnerabilityCase for report`, `Invalid RM transition START → …`, `no routable
recipients`), and the change touched what an outbound payload carries.

**Claim.** In that situation the in-process pass is not evidence about payload
completeness. The in-process topologies seed the case, its participants, and its
embargo into *every* node's store (`_seed_case(owner_dl, …)`,
`_seed_case(ca_dl, …)`) before exercising one protocol step. A receiver that
already holds everything never depends on what the wire carried, so a body that
omits objects, or carries them in a shape the receiver cannot index, looks the
same as a complete one. Only the Docker demos bootstrap a participant solely
from delivered `Create`/`Announce` activities.

**Evidence.** PR #3923 (sealed outbox bodies) was green on about 13,000 tests
and failed Docker demo CI three times, each on a different latent receive-side
bug the faithful body exposed: an inline `EmbargoEvent` handed to `dl.read()`,
`find_case_by_report_id` matching on `id_` against rows keyed `id`, and
participants sent as bare ids once delivery-time `dl.hydrate()` was removed
(CBT-01-007, CP-09-004).

**How to apply.** When the change touches payload contents, reproduce with a
topology whose participant node starts *empty* and is bootstrapped only by
delivered activities. `test/demo/conftest.py` supports this;
`test_pcr_bootstrap.py` does it for a two-node Announce. Don't count a seeded
topology as coverage. The sealed-body ratchet
(`test/adapters/driven/trigger_activity_adapter/test_sealed_body_audit.py`)
covers the trigger port, not the receive-side projections that consume it.

**What would confirm it.** A second payload-shape change that passes in-process
and fails only in the Docker demos.
