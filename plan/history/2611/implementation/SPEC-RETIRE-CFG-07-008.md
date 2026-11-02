---
source: SPEC-RETIRE-CFG-07-008
timestamp: '2026-11-02T16:02:45.003503+00:00'
title: Retired requirement CFG-07-008
type: implementation
---

Retired CFG-07-008 from `specs/configuration.yaml` (#5390).

Why: It describes a seed-YAML sub-block loader, `_actor_config_from_seed_yaml()`, that no longer exists. `load_actor_config()` in `vultron/config/app.py` returns `get_config().actor`, and `AppConfig` loads the whole file through `YamlConfigSource`, so no sub-block loader remains to constrain.

Final text: `plan/retired-specs/CFG-07-008.md`.
