# Trigger Use Cases — Classification and Design Rules

Cross-references: `specs/triggerable-behaviors.yaml` (TRIG-08,
TRIG-09, TRIG-10), `specs/configuration.yaml` (CFG-04).

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

`RunMode` MUST use `StrEnum`. It is the top-level config field
`AppConfig.mode` (TRIG-08-005), not a `server:` field. In `PROD`, the demo
router is not mounted → HTTP 404 for all `/demo/` paths. Env var:
`VULTRON_MODE=prod`.

## Demo Router Conditional Mounting

```python
from vultron.config import RunMode, get_config

if get_config().mode == RunMode.PROTOTYPE:
    app.include_router(demo_triggers.router)
```

## Layer and Import Rules

- `RunMode` is defined in `vultron/config/app.py` and imported from
  `vultron.config`.
- The demo router module is always imported; only its mounting depends on
  the mode (TRIG-09-002), in `vultron/adapters/driving/fastapi/app.py`.
- Demo-only verbs reuse the trigger use cases in this package; the demo
  router in `vultron/adapters/driving/fastapi/routers/demo_triggers/actions.py`
  wraps them with `run_trigger`.
