---
title: "YAML seed config with no local_actor key must fall through to env vars"
type: learning
timestamp: "2026-07-15"
source: ISSUE-1343
---

When `_actor_config_from_seed_yaml()` reads a YAML that has no `local_actor`
key, returning `{}` as a default and then validating it produces a valid
`ActorConfig()` (all defaults). This causes `load_actor_config()` to return
early, silently ignoring `VULTRON_ACTOR__*` env vars — violating the documented
resolution order (YAML → env → defaults).

Fix: check `"local_actor" in raw` before calling `model_validate`, and return
`None` when the key is absent.

**Why:** Pydantic's `model_validate({})` on a model where every field has a
default does not distinguish "field absent from source" from "field explicitly
set to default". The distinction has to be enforced at the config-reading layer.

**How to apply:** Any loader that reads a YAML sub-block and falls back to a
secondary source must check for key presence (not just type), not just validate
the sub-block. Pattern: `if "key" not in raw: return None`.
