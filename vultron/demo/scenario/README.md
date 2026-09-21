# Scenario Demos

This sub-package contains end-to-end multi-actor scenario demos for the
Vultron CVD workflow.

## What these demos do

Each module in `scenario/` orchestrates a complete multi-actor CVD workflow
across **separate API server containers**. These demos use **trigger-based
puppeteering** — they call trigger endpoints on each actor's own container
so that the actor's behavior tree and outbox logic are exercised end-to-end.

This technique is the correct way to test the full Vultron Protocol:

- Each actor makes its own decisions via its behavior tree.
- Activities are emitted from the sending actor's outbox and delivered to
  the receiving actor's inbox via HTTP.
- No inter-actor messages are constructed or injected manually.

Compare with the `exchange/` demos, which use direct inbox injection to
illustrate individual message semantics in isolation.

## Available scenario demos

Each scenario declares itself by decorating its `main()` with `@scenario(...)`
from [`registry.py`](registry.py); the table below is generated from those
declarations (ADR-0098, DEMOCI-11). To add a scenario, write the module and
decorate it — then run `uv run demo-scenarios --write`.

<!-- BEGIN GENERATED SCENARIO TABLE — do not edit; edit the @scenario decorators and run `uv run demo-scenarios --write` -->

| Sub-command | Script | Participants | What it demonstrates |
|---|---|---|---|
| `fccv-extension` | `fccv_extension_demo.py` | Finder + C1 + C2 + Vendor | Second coordinator suggests vendor |
| `fccv-handoff` | `fccv_handoff_demo.py` | Finder + C1 → C2 + Vendor | Ownership transfer between two coordinators |
| `fcv` | `fcv_demo.py` | Finder + Coordinator + Vendor | Coordinator-mediated report and vendor onboarding |
| `fcv-reject` | `fcv_reject_demo.py` | Finder + Coordinator + Vendor (Vendor rejects) | Invite rejection path |
| `fcvcv` | `fcvcv_demo.py` | Finder + C1 + V1 + C2 + V2 | Actor-suggestion flow (ADR-0026) |
| `fv` | `fv_demo.py` | Finder + Vendor | Baseline two-actor CVD |
| `fvcv-extension` | `fvcv_extension_demo.py` | Finder + Vendor1 + Coordinator + Vendor2 | Coordinator-suggested second vendor |
| `fvcv-handoff` | `fvcv_handoff_demo.py` | Finder + Vendor1 → Coordinator + Vendor2 | Case-ownership transfer to coordinator |
| `fvv` | `fvv_demo.py` | Finder + Vendor1 + Vendor2 | Direct invitation of a second vendor |

<!-- END GENERATED SCENARIO TABLE -->

## Running scenario demos

Scenario demos require multiple running containers. Use the multi-actor
Docker Compose file:

```bash
# FV scenario
cd docker && docker compose -f docker-compose-multi-actor.yml up
```

Or with the unified CLI (after starting the appropriate containers):

```bash
vultron-demo fv
```

See the parent `README.md` and `docker/README.md` for full setup instructions.
