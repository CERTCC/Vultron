---
title: "A retired-symbol sweep is not a substitution: SEMANTICS_ACTIVITY_PATTERNS → SEMANTIC_REGISTRY changed the data shape"
type: learning
timestamp: "2026-09-02T15:00:00Z"
source: ISSUE-3022
signal: spec-ambiguity
---

Issue #3022's AC-1 read "All 33 occurrences are replaced with
`SEMANTIC_REGISTRY`". Executed literally, that would have left three
requirements asserting something false, because the two symbols do not name the
same kind of object:

- `SEMANTICS_ACTIVITY_PATTERNS` was a `dict[MessageSemantics, ActivityPattern]`.
- `SEMANTIC_REGISTRY` is an ordered `list[SemanticEntry]`, and every
  `MessageSemantics` value has an entry — including `UNKNOWN` and
  `UNKNOWN_UNRESOLVABLE_OBJECT`, whose entries carry `pattern=None`.

So the three statements phrased in dict terms had to be re-derived, not renamed:

| Spec | Said | Why a rename alone is wrong |
|---|---|---|
| VAM-09-002 | `UNKNOWN` MUST NOT have an **entry** | It *does* have one; `lookup_entry()` needs it to resolve the fallback event class and use case. What it must not have is a `pattern`. |
| VAM-01-001 | every value except `UNKNOWN` has exactly one entry | Both sentinels are excluded, not just `UNKNOWN`, and the discriminator is a non-`None` `pattern`. |
| SE-03-001 | every value "appears as a **key**" | There are no keys. |

**How to apply**: when auditing a corpus for a retired symbol, first ask whether
the replacement has the same shape. If the old name was a mapping and the new
one is a sequence (or vice versa), every statement phrased in terms of *keys*,
*entries*, or *containment* is a candidate for a semantic rewrite, and a
find-and-replace will silently convert a stale requirement into a wrong one — a
strictly worse outcome, because a wrong MUST reads as authoritative.

Corollary for issue authors: an AC that prescribes a mechanical substitution
carries an unstated premise that the substitution is meaning-preserving. State
the intent ("every reference names the live registry accurately") rather than
the mechanism.

Related: [[20260901-2906-reported-cause-was-wrong]] — same family, a
correctly-observed symptom paired with a premise that does not survive contact
with the spec.

---

**Promoted**: 2026-09-03 — captured in `notes/spec-authoring-rules.md` ("A Retired-Symbol Sweep Is Not a Substitution — Check the Shape First"). Docs PR: <https://github.com/CERTCC/Vultron/pull/3147>.
