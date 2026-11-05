---
title: "A seeded generator is deterministic but not insertion-stable, so its currency check can be green while every regeneration still rewrites the whole corpus"
type: learning
timestamp: "2026-11-05T02:20:00Z"
source: ISSUE-5776
signal: theme-candidate
---

**Trigger.** You are making a generator of committed artifacts reproducible —
example payloads, fixtures, recordings, snapshots, schema dumps — so that a
check can compare the committed files with a fresh generation. The obvious
move is to seed the random source once per run.

**Claim.** A seed buys determinism and not minimality. Under one seeded
sequence every draw depends on how many draws came before it, so inserting or
removing an artifact shifts every value drawn after it, and a regeneration
rewrites files whose content nobody changed. The currency check passes either
way, because it only asks whether the committed tree equals *a* fresh
generation — so the defect survives the gate that was built to catch it, and
shows up instead as a reviewer being asked to read 88 changed files to approve
a change to 18. What buys minimality is deriving each value from the artifact's
own name rather than from its position: `uuid5(namespace, f"{artifact}/{n}")`
instead of `Random(seed).getrandbits(128)`.

**Evidence.** #5776. The vocab example generator drew `uuid4` ids, a
`random.randint` case number and wall-clock stamps, so a regeneration rewrote
all 92 committed examples; in PR #5773 the author restored the regeneration
and hand-edited 18 files instead. The repository already held a seeded
generator for the same class of problem —
`vultron/demo/determinism.py`'s `SeededUuid4`, one `random.Random(seed)`
sequence for a whole scenario recording — and reusing it would have passed
every test written for the fix. The replacement derives each id from the
example's own name and the draw's position *within that example*, which is
why `test_another_scope_entered_first_moves_nothing` can exist: it fails for a
shared seeded counter and passes for a scope-keyed derivation, and no
committed-equals-generated comparison can tell the two apart.

**What would confirm it.** A second artifact family where a seeded generator
was adopted and a later insertion produced a diff far larger than the change:
a fixture corpus, a recorded transcript set, or a generated client. The claim
is about seeded sequences generally; so far the only witness is one id source
for one docs corpus. A counter-witness would be an artifact family whose
generation order is itself part of the contract, where position-dependence is
correct.

**How to apply.** When a generator's output is committed and reviewed, state
the property you need before choosing the mechanism: *deterministic* (two runs
agree) or *insertion-stable* (a change to one artifact changes one file). A
seed gives the first only. Write a test for the second directly — generate
artifact A, generate B, generate A again, assert A is unchanged — because the
committed-equals-generated check cannot see it. Related: the same gap in the
other direction is `notes/testing-pitfalls.md` § assertion-quality traps, where
pinning a value makes a comparison unfallible.
