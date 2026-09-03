---
title: Clearing a field on a wire object means model_copy, not assignment — and the shared-singleton hazard makes copying the right answer anyway
type: learning
timestamp: "2026-09-02T00:00:00Z"
source: ISSUE-2904
signal: design-question
---

`vultron/wire/as2/vocab/examples/_base.py` needed to blank the
`published`/`updated` timestamps before rendering an example, so the docs would
not churn on every build. It did this by assignment:

```python
cast(Any, obj).published = None
```

Wire objects are frozen by design (`as_Object` sets `frozen=True`, ADR-0074), so
this could never work. Two things about the fix are worth carrying forward.

**1. The `cast(Any, ...)` is what hid it.** `mypy` and `pyright` both pass on
this line and always did. The cast erases the type, so neither checker can see
that the target is frozen. A cast that exists only to silence a checker on an
assignment is a smell: the checker was right. Prefer the shape that needs no
cast.

**2. Copying beats making the mutation work.** The obvious alternative —
`object.__setattr__`, or dropping `frozen=True` — would have been wrong, and not
only because it fights ADR-0074. The example objects are shared module-level
singletons (`_REPORT`, `_CASE`, the actors), and
`vultron/adapters/driving/fastapi/routers/examples.py` serves those same
instances over HTTP. In-place stripping would have permanently removed the
timestamps from the live API responses too, as a side effect of building the
docs. That is the same shared-singleton hazard that closed #1328.

So the correct shape returns a new object and leaves the argument alone:

```python
fields = type(obj).model_fields
updates: dict[str, None] = {
    name: None for name in ("published", "updated") if name in fields
}
if not updates:
    return obj
return obj.model_copy(update=updates)
```

**How to apply:** to clear or override a field on any frozen wire object, build
a new one with `model_copy(update=...)` — the established idiom in this codebase
(see `adapters/driven/datalayer_sqlite/hydration.py`,
`core/models/dimensions.py`). Probe `type(obj).model_fields` rather than
`hasattr`: `hasattr` is also true for properties and extras, where
`model_copy(update=...)` would write a key that does not serialize.

Whenever a helper takes a shared fixture and returns "the same thing, adjusted",
check who else holds that instance before reaching for mutation.
See [[wire-artifact-immutability]].

---

**Promoted**: 2026-09-03 — captured in `notes/wire-artifact-immutability.md` ("Clearing a Field: `model_copy`, Not a Cast-Silenced Assignment"). Docs PR: <DOCS_PR_URL>.
