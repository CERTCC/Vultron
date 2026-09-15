---
title: "Before deciding a permissive fallback is load-bearing, instrument it and count what it actually absorbs"
type: learning
timestamp: "2026-09-14T20:40:00Z"
source: ISSUE-3217
signal: theme-candidate
---

`vultron/wire/as2/parser.py` wrapped nested inline validation in
`except Exception: return expanded`. Reading the code, the fallback looked like a
deliberate compatibility shim: nested AS2 objects legitimately arrive as bare ID
strings or partial stubs, so tolerating a validation failure and handing the
parent the raw dict is a plausible design. Its introducing commit
(`62cdc48ea`, "Fix invite response parsing and reply links") carried no comment
explaining what it protected. Removing it therefore looked like an ADR-level
call with repo-wide blast radius, and that is how it was first scoped.

Instrumenting the `except` to log `(class, keys, error)` and running the full
suite settled it in one pass. It fired **52 times**, and every occurrence was a
single cause:

```text
as_VultronOrganization | inbox | Input should be a valid dictionary or instance
of as_OrderedCollection [input_type=CoreActorCollection]
```

`find_in_vocabulary` falls back to `CORE_TYPE_MAP` (ARCH-12-003).
`OrderedCollection` is registered *only* there, so an inline actor's `inbox`
expanded to a **core** `CoreActorCollection`, which the wire parent rejects. The
fallback was not absorbing partial stubs or unknown types at all — it was
concealing a wire/core layering fault (ARCH-22-001) that flattened every inline
actor to a bare `as_Link`.

That measurement inverted the plan twice over. It showed the tolerated case was
itself a bug, so removing the tolerance was correct rather than risky; and it
showed the *order* the fix had to be applied in — restricting type resolution to
the wire branch first, because refusing malformed inline objects while the core
fallback remained would have turned all 52 into hard rejections.

**How to apply.** When a bare `except`, `or None`, or silent-degradation path
blocks a fix, do not reason about whether it is load-bearing from the code and
the commit message. Instrument it to record what reaches it, run the full suite,
and group the results. The output is a *cause count*, which answers three
questions at once: is the tolerated input legitimate, how many distinct cases
exist, and does anything have to be fixed before the tolerance can be removed. A
single-cause result usually means the fallback is masking a bug; a many-cause
result means it is genuinely a compatibility surface and deserves the ADR.

This is cheap — one instrumented run — and it replaces a guess that had a
coin-flip chance of being wrong in either direction: leaving a silent
mis-routing bug in place, or breaking 52 call paths.

Corroboration needed: one instance so far. The neighbouring claim worth watching
is that *undocumented* defensive code is disproportionately likely to be masking
a defect rather than handling a real case — if a second session measures a
fallback and finds a single bug-shaped cause, that pattern is worth promoting.

Related: [[20260903-2824-clp14-15-do-not-name-their-timestamp]] — also a case
where reading the artifact was not enough and the enforcing side had to be
determined from behaviour.
