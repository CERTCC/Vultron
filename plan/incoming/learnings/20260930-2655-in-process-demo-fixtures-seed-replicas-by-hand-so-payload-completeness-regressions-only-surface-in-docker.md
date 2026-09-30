---
title: "In-process demo fixtures seed every replica by hand, so a payload-completeness regression stays invisible until the Docker demos run the real bootstrap"
type: learning
timestamp: "2026-09-30T17:10:00Z"
source: ISSUE-2655
signal: theme-candidate
---

PR #3923 replaced the outbox's re-read-and-normalise delivery with a sealed
body relayed byte for byte. Locally everything was green: 11,760 unit tests, 1,300
integration tests including the three-node in-process topologies in
`test/demo/test_remote_case_actor_invite.py` and the new
`test/demo/test_sealed_body_wire.py`, and a three-scenario demo pass a review
sub-agent ran. The PR's Docker demo CI then failed three times in a row, each
time on a different latent bug the faithful body exposed:

- `invite_actor_to_case` handed an inline `EmbargoEvent` to `dl.read()` — a
  case seeded from a sealed `Announce` carries its embargo inline;
- `find_case_by_report_id` matched inline reports on `id_` while stored rows
  are re-keyed to `id`;
- the sealed `Announce`/`Create(VulnerabilityCase)` carried participants as
  bare ids, because the removed delivery-time `dl.hydrate()` had been the only
  thing expanding them (CBT-01-007, CP-09-004).

None of these can show in the in-process suites as written, and the reason is
structural rather than a missing assertion. The in-process topologies seed the
case, its participants, and its embargo directly into *every* node's store
(`_seed_case(owner_dl, …)`, `_seed_case(ca_dl, …)`) and then exercise one
protocol step on top. A receiver that already holds the case, the participants
and the embargo never depends on what the wire carried, so a body that omits
them (or carries them in a shape the receiver's store cannot index) is
indistinguishable from a complete one. Only the Docker demos, where the vendor
learns of the case solely through the bootstrap `Create`/`Announce`, exercise
the completeness contract the outbox change moved from the handler into the
factory.

The recognisable trigger: unit and in-process integration are green, the
Docker demo fails with a "missing object" symptom on the *receiving* side
(`no VulnerabilityCase for report`, `Invalid RM transition START → …`,
`no routable recipients`), and the change touched what an outbound payload
carries. In that situation the in-process pass is not evidence about payload
completeness. Two remedies seem worth weighing rather than asserting from one
instance: an in-process topology whose participant node starts *empty* and is
bootstrapped only by delivered activities (the harness in `test/demo/conftest.py`
supports it — `test_pcr_bootstrap.py` does this for a two-node Announce), and a
ratchet on the sealed body itself, which #3923 added for the trigger port
(`test/adapters/driven/trigger_activity_adapter/test_sealed_body_audit.py`) but
which does not cover the receive-side projections that consume the payload.
