---
title: "A spec rationale that narrates its own amendment goes on endorsing the superseded arrangement — and the example it picked to illustrate the point becomes a licence for the defect"
type: learning
timestamp: "2026-09-23T17:30:00Z"
source: ISSUE-2982
signal: spec-contradiction
---

Issue #2982 reported that `WIRE_TYPE_MAP` carried six keys that are not wire
`type` values — five `as_Vultron*` actor classes registered under their class
names alongside their real `type` values, plus `as_VulnerabilityCaseStub` under a
key no payload ever carries. The fix is small. What is worth recording is **why
the project held the defect as correct for months while four separate documents
said otherwise.**

## Two live statements, in direct contradiction

Asserting the type-value key form: `notes/vocabulary-registry.md`'s key table,
the `find_in_vocabulary` docstring ("`WIRE_TYPE_MAP` (keyed by wire `type_`
value)"), the `As2WireRenderAdapter` module docstring, and comments in three test
files.

Asserting the opposite: `specs/vocabulary-model.yaml` VM-01-004's **rationale**,
which read

> This requirement previously stated that the key *is* the AS2 `type` value.
> That was only accidentally true, and already false for the five actor types:
> `as_VultronPerson` auto-registers under `VultronPerson` … and is *also*
> explicitly assigned to the key `Person` …

and its **verification**, which required a test asserting `{"type": "Person"}`
resolves to `as_VultronPerson` "even though its derived key is `VultronPerson`".

The spec won, because a spec item is the artifact agents treat as authoritative.

## The mechanism

VM-01-004 was amended when there was **one** registry, and the amendment was
correct *then*: the key was class-name-derived and the wire value was a separate
concern. Its rationale explained the change by narrating what the requirement
used to say, and reached for the actor dual-key as the concrete illustration.

The registry was then split in two — `VOCABULARY` on class names, `WIRE_TYPE_MAP`
on `type` values. That split made VM-01-004's *statement* still true (it scopes
to `VOCABULARY`) while making its illustrative example describe a **defect**. The
prose had no way to know: it was written to justify an edit, not to describe an
invariant, so nothing about it decayed visibly when the world moved.

Three properties made it durable:

- **A rationale is read as belief, not as changelog.** Nobody reads
  "previously stated" and infers "this sentence may now be stale"; they infer
  "the project considered this and decided".
- **A concrete example outlives the general claim it was serving.** The general
  claim ("key ≠ wire value") survived the split intact. The example
  (`VultronPerson` *and* `Person`, both fine) did not, and the example is the
  part an agent pattern-matches against the code in front of them.
- **The verification clause described a test that does not exist.** So nothing
  ever executed the claim and found it had drifted — and *also* nothing enforced
  the real invariant, which is how six keys accumulated. `WIRE_TYPE_MAP` had no
  requirement of its own at all.

## Why this is not just "an unenforced MUST"

ISSUE-3480 recorded that an unenforced MUST anti-advertises: at 50% adoption the
corpus reads as "no rule here". This is the inverse and worse. Here there was no
requirement to under-enforce — instead a *neighbouring* requirement's supporting
prose positively asserted the defect as expected. A missing rule leaves you
searching; a stale rationale stops you searching.

## How to apply

- When you change a spec `statement:`, rewrite its `rationale:` and
  `verification:` to describe the current world. Delete any clause that only
  parses against the superseded version — **especially a worked example chosen to
  illustrate the old framing**. Now recorded as a rule in
  `notes/spec-authoring-rules.md` § "A Spec States Current Understanding".
- When a registry, index, or table is **split**, audit every spec item, note and
  docstring that named the pre-split thing. One statement scoped cleanly to one
  half by luck; its rationale did not, and that asymmetry is invisible from the
  statement alone.
- When a spec entry's `verification:` names a test, check the test exists before
  trusting the claim. A verification clause is a *claim about the suite*, and an
  unbacked one reads exactly like a backed one.

## Second witness wanted

The general claim — *supporting prose in a spec entry decays independently of its
statement, and worked examples decay fastest* — rests on this one instance. The
adjacent evidence is suggestive: `notes/wire-core-boundary.md`,
`notes/core-wire-rendering-port.md` and `notes/vocabulary-registry.md` all carry
"superseded by ADR-0099" markers on their remedies while their diagnoses stand,
which is the same statement-versus-supporting-prose seam surviving a change. If a
second session finds a defect licensed by a stale `rationale:` or `verification:`
clause, this is corroborated and belongs in `specs/meta-specifications.yaml` as
an authoring MUST rather than a notes rule.
