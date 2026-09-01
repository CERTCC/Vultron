---
name: wire-type-map-key-naming-agents-md-wrong
description: AGENTS.md incorrectly states WIRE_TYPE_MAP uses wire type_ value keys; actual keys are cls.__name__.removeprefix("as_"), which diverges from type_ for actor classes
metadata:
  type: project
---

AGENTS.md line 302 says: "WIRE_TYPE_MAP uses wire `type_` value keys (`'VulnerabilityCase'`)".

**Actual behavior**: `__init_subclass__` in `as_Base` registers `WIRE_TYPE_MAP[cls.__name__.removeprefix("as_")] = cls`.  For `as_VulnerabilityCase` the key happens to equal the `type_` value, but for `as_VultronPerson` the key is `"VultronPerson"` while `type_` is `"Person"`.  The AS2 type_ keys (`Person`, `Application`, etc.) are added by explicit override in `vultron_actor.py` lines 103–107, not by the generic hook.

**Why:** Discovered during code review of PR for issue #2500.

**How to apply:** AGENTS.md needs a correction to say the key is `cls.__name__.removeprefix("as_")` (not the type_field value). Separately, `vultron_actor.py` explicitly registers the AS2 type_ key overrides for actor classes. This is a pre-existing doc error.
