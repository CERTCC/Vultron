# Trigger Use Cases — Classification and Design Rules

Cross-references: `specs/triggerable-behaviors.yaml` (TRIG-08,
TRIG-09, TRIG-10), `specs/configuration.yaml` (CFG-04).

Full trigger audit table, wrapper pattern examples, and testing patterns:
[`notes/triggerable-behaviors.md`](../../../../notes/triggerable-behaviors.md)
§ "General-Purpose vs. Demo-Only Trigger Classification"

## Classification (Key Test)

Would a real autonomous actor ever need an external caller to drive this
step? If **yes** → `/trigger/`. If the BT should always handle it →
`/demo/`.

## RunMode Enum (MUST)

```python
from enum import StrEnum

class RunMode(StrEnum):
    PROTOTYPE = "prototype"
    PROD = "prod"
```

`RunMode` MUST use `StrEnum`. In `PROD`, the demo router is not mounted
→ HTTP 404 for all `/demo/` paths. Env var:
`VULTRON_SERVER__RUN_MODE=prod`.

## Demo Router Conditional Mounting

```python
from vultron.config import get_config
from vultron.enums import RunMode

config = get_config()
if config.server.run_mode == RunMode.PROTOTYPE:
    app.include_router(demo_router)
```

## Layer and Import Rules

- `RunMode` MUST be defined in `vultron/enums.py` (alongside
  `MessageSemantics`) to avoid circular imports.
- The demo router module MUST NOT be imported unconditionally — only
  inside the `if run_mode == PROTOTYPE` branch.
- Demo use-case classes MUST live under `vultron/core/use_cases/demo/`.
