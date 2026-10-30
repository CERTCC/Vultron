---
status: accepted-provisional
date: 2026-10-30
created: 2026-10-30
updated: 2026-10-30
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; issues #5452, #5253; PR #5447;
  specs/code-style.yaml CS-13; specs/sync-ledger-replication.yaml SYNC-16-008
informed: []
stakeholder_type: [project-contributor]
---

# Times Keep Microseconds and Always Serialize Six Fractional Digits

## Context and Problem Statement

Every time this node creates is stored at whole seconds: the clock helper drops microseconds.
The reason was one serialized form per instant.
A time with microseconds serializes with a fractional second and a time without them does not, so two copies of the same instant could hold different strings and compare unequal.
The case ledger hashes those strings, so a different string is a different record.

Whole seconds cost the order of acts.
Two activities that one actor sends within the same second carry equal `published` times.
The divergence-recovery rule had to treat an equal fault and acknowledgement time as a tie (#5253, PR #5447), and a helper exists only to bump a same-second stamp to the next second.

How does this node keep one string per instant without losing the order of acts inside one second?

## Decision Drivers

- One instant must have one serialized form, because the ledger hashes and compares the text.
- Acts that one actor sends in order must carry times in that order where the clock can show it.
- A time carried from a peer keeps the offset it arrived with (CS-13-005), because a changed offset changes the recorded text.
- No backward compatibility is owed to stored or replicated data from before the change.

## Considered Options

1. **Keep whole seconds.** Times stay second-precise; ties inside a second stay ties.
2. **Microseconds, fixed form.** Times keep microseconds, and every serialization writes exactly six fractional digits and an explicit offset, whether or not the microseconds are zero.
3. **Microseconds, shortest form.** Times keep microseconds and serialize as the platform writes them: no fraction when the microseconds are zero, six digits otherwise.

## Decision Outcome

Chosen option: "Microseconds, fixed form", because it meets the one-string-per-instant driver as fully as whole seconds do and keeps the order that whole seconds discard.
Option 1 keeps the ties that #5253 had to work around.
Option 3 restores the problem whole seconds were chosen to solve: a time whose microseconds happen to be zero serializes without a fraction, so one serializer can give two string shapes, and a peer that writes the other shape holds a different string for the same instant.

The decision has three parts:

- **Precision.** A time this node creates keeps its microseconds.
- **One form.** Every time this node serializes, whether it created the time or carries it from a peer, is written as an RFC 3339 date-time with exactly six fractional digits and an explicit offset.
  A time this node creates carries a UTC offset.
  A carried time keeps the offset it arrived with (CS-13-005); only its fraction is written in the fixed form.
- **One place.** One formatting function writes the form, and every serialization path uses it: model JSON dumps, the case ledger's hash input, the genesis hash and the storage encoder.

A peer may still send times at whole seconds.
The fixed form is what this node writes, not what it requires to receive.

### Consequences

- Good: two acts one actor sends inside one second carry ordered times, so a same-second tie is rare rather than routine.
- Good: one instant has one string, whether or not its microseconds are zero.
- Neutral: a rule that compares times a peer claimed must still treat a tie with care, because a peer may write whole seconds.
- Bad: every stored ledger hash and every wire example that pins a whole-second string changes; stores written before the change are reset rather than migrated.

## Validation

- One instant serializes to one string whether or not its microseconds are zero.
- Every datetime field on a model serializes in the fixed form.
- Two clock reads inside one second compare in order.
- A carried time with a non-UTC offset keeps that offset in the fixed form.

## More Information

The current rules live in the CS-13 group of `specs/code-style.yaml`.
They replace CS-13-003, which stored every time at whole seconds.

Generated spec requirements: `code-style.yaml` CS-13-007, CS-13-008.
