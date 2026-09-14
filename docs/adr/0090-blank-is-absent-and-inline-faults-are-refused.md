---
status: accepted
date: 2026-09-14
deciders: Allen D. Householder
consulted: —
informed: —
---

# A Blank Required Field Is Absence, and a Recognised Inline Object That Fails Validation Is Refused

## Context and Problem Statement

`parse_activity` is the message-validity threshold: it reads the raw inbound
body, refuses what is malformed, and hands a typed `as_Activity` to the rest of
the pipeline. Two of its decisions were being made on the wrong question, and
the second of them failed silently.

**The field guards asked about the key, not the value.** Both required-field
guards were spelled `if body.get(field) is None`, which answers "was the key
absent?" The requirements they enforce are about the *value*: CLP-15-006 refuses
an inbound activity that "carries no `published`", and MV-01-001 requires a
recognisable `type`. A sender who transmits `""` has supplied the key and
nothing else, so the guard passed and the value went on to `model_validate`,
which reported it as a *schema* fault. The consequences differed by field:

- `published: ""` still produced a 422, but with a Pydantic isoformat dump in
  place of the CLP-15-006 explanation the sender needed.
- `type: ""` produced `UnknownTypeError` and therefore a **422**, while an
  omitted `type` produces `MissingTypeError` and a **400** — two spellings of
  the same omission drawing two different status codes.

**A nested object that failed validation was silently downgraded.**
`_expand_inline_value` types nested dicts so pattern matching can see structures
like `Accept(Invite(...))`. It wrapped that validation in
`except Exception: return expanded`, handing the parent the raw dict instead.
The parent then accepted the dict as a bare `as_Link`, so the activity parsed
*successfully*, extracted as `UNKNOWN`, lost the case id, and drew a 202 for a
message the receiver never understood. No log line, no error.

Instrumenting that fallback and running the whole suite showed it fired 52
times, and every single occurrence was **one** cause: `find_in_vocabulary` falls
back to `CORE_TYPE_MAP` (ARCH-12-003), and `OrderedCollection` is registered
*only* there. An inline actor's `inbox` therefore expanded to a **core**
`CoreActorCollection`, which `as_VultronOrganization.inbox` rejects — degrading
the entire actor to an `as_Link`. The fallback was not protecting a legitimate
case; it was concealing a wire/core layering fault (ARCH-22-001) that erased
actor subtypes on every inbound activity carrying an inline actor.

Source: ISSUE-3217.

## Decision Drivers

- CLP-15-006 and MV-01-001 are stated about values, so the guards must read
  values. CS-08-001 already fixes the reading: "if present, then non-empty".
- One omission must draw one status code, whichever way the sender spells it.
- Silent degradation is the worst available failure. A 422 tells the sender what
  to fix; a 202 for a misrouted message tells nobody anything.
- ADR-0032: validate at the edge rather than compensating downstream.
- Nested expansion inside a wire tree is wire-to-wire (ARCH-22-001). A core
  instance in a wire tree cannot satisfy the wire parent's field type, so it is
  a layering fault, not an input problem.

## Considered Options

1. Falsy check on the guards; leave the inline fallback alone.
2. Blank-aware guards; leave the inline fallback alone.
3. Blank-aware guards; resolve inline types to wire classes only, and refuse a
   recognised inline object that fails validation.
4. Blank-aware guards; refuse malformed inline objects while keeping the core
   fallback in type resolution.

## Decision Outcome

Chosen option: **3**.

Two rules, applied wherever the parser reads an inbound value:

**A required field that is present but blank is absent.** Absent, `null`, and
blank (including whitespace-only) all raise the same "missing field" error.
Blankness is decided by `not value.strip()`, matching the project's canonical
predicate in `core.models.base._non_empty`. A non-blank value that will not
parse stays a *schema* fault — blank means "not provided", and reporting corrupt
data as missing data tells the sender to supply a field they already sent.

**A recognised inline object that fails its own class's validation is refused.**
Once `type` has resolved to a wire vocabulary class, failing that class's
validation is a message fault and belongs in the 422. The parser no longer
substitutes the raw dict.

Refusing is only safe because the same change removes the one thing the
fallback was absorbing: `_inline_vocab_class` now returns a class only if it is
an `as_Base` subclass, so the `CORE_TYPE_MAP` fallback cannot inject a core
instance into a wire tree. An unregistered or non-wire type still resolves to
`None` and the dict is left for the parent to validate — the same outcome the
`except` produced, now reached by construction rather than by catching an
exception.

`payloadSnapshot` is unaffected: `_OPAQUE_PAYLOAD_KEYS` excludes it from
expansion, so a snapshot's contents are never validated here (SYNC-13-004).

### Consequences

- Good, because a blank `type` and an omitted `type` now both answer 400, and a
  blank `published` gets the CLP-15-006 explanation instead of a Pydantic dump.
- Good, because an inline actor keeps its subtype. It was being flattened to
  `as_Link` in production with no empty string involved.
- Good, because a corrupt inner object is now reported rather than accepted and
  misrouted.
- Bad, because a sender whose inline object is malformed in a way the receiver
  previously tolerated now gets a 422 instead of a 202. That tolerance was
  silent misrouting, so the exchange is deliberate: a visible rejection in place
  of an invisible wrong answer.
- Neutral on `published` status codes: both spellings already returned 422; only
  the diagnosis improves.

## Validation

`test/wire/as2/test_parser.py` covers the blank spellings of both fields, the
non-blank-garbage boundary, subtype survival across a blank nested timestamp,
refusal of a malformed nested object, and inline-actor subtype preservation with
core-only collection types. `test/wire/as2/vocab/base/test_base_timestamps.py`
covers the shared timestamp validator across all four fields.
`test/adapters/.../actors/test_inbox.py` pins blank `type` to HTTP 400. The full
suite (9867 tests) passes unchanged, which is the evidence that refusing
malformed inline objects broke nothing the fallback was protecting.

## Pros and Cons of the Options

### 1. Falsy check; leave the fallback

The one-line fix proposed in the issue. Rejected on both halves: `if not
body.get("published")` still admits `"   "`, and it also swallows `0` and `[]`,
which are malformed rather than omitted. It leaves the silent-downgrade path
untouched.

### 2. Blank-aware guards; leave the fallback

Fixes the reported symptom and the `type` status-code split. Rejected because
it leaves the most severe behaviour in place — an activity that parses clean,
extracts as `UNKNOWN`, and is answered 202 — while the context that found it is
still loaded.

### 3. Blank-aware guards, wire-only resolution, refuse inline faults (chosen)

Fixes the reported defect, the sibling status-code split, the silent
nested-object downgrade, and the actor-flattening layering fault, from one
consistent premise. Costs a behaviour change on malformed inline objects, which
the suite shows nothing depended on.

### 4. Refuse inline faults, keep the core fallback in resolution

Rejected: it would turn all 52 measured `CoreActorCollection` mismatches into
hard rejections, breaking every inbound activity with an inline actor. The
layering fault has to be fixed *first* for refusal to be safe — which is why
these two changes ship together rather than separately.

## More Information

- Specs: MV-03-002, MV-04-003; CS-08-001, CS-08-002; CLP-15-006; MV-01-001;
  ARCH-22-001, ARCH-12-003.
- Related: ADR-0032 (validate at the edge), ADR-0082 (wire/core boundary),
  ADR-0086 (report every violation; emit/receive dispositions).
- Issues: #3217 (the reported blank-`published` defect), #3232 (the inline-object
  downgrade and the wire/core type-resolution fault behind it).
