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
decorate it, declaring its `path` through the branch-point table in
[`branch_points.py`](branch_points.py) — then run `uv run demo-scenarios --write`.

<!-- BEGIN GENERATED SCENARIO TABLE — do not edit; edit the @scenario
     decorators and run `uv run demo-scenarios --write` -->

| Sub-command | Script | Participants | What it demonstrates |
|---|---|---|---|
| `rccv-extension` | `rccv_extension_demo.py` | Reporter + C1 + C2 + Vendor | Second coordinator suggests vendor |
| `rccv-handoff` | `rccv_handoff_demo.py` | Reporter + C1 → C2 + Vendor | Ownership transfer between two coordinators |
| `rcv` | `rcv_demo.py` | Reporter + Coordinator + Vendor | Coordinator-mediated report and vendor onboarding |
| `rcv-embargo` | `rcv_embargo_demo.py` | Reporter + Coordinator + Vendor | Embargo revision after submission and deliberate termination |
| `rcv-reject` | `rcv_reject_demo.py` | Reporter + Coordinator + Vendor (Vendor rejects) | Invite rejection path |
| `rcvcv` | `rcvcv_demo.py` | Reporter + C1 + V1 + C2 + V2 | Actor-suggestion flow (ADR-0026) |
| `rcvv-embargo` | `rcvv_embargo_demo.py` | Reporter + Coordinator + Vendor1 + Vendor2 | Embargo revision cycle, late second vendor, and accidental collapse |
| `rv` | `rv_demo.py` | Reporter + Vendor | Baseline two-actor CVD |
| `rvcv-extension` | `rvcv_extension_demo.py` | Reporter + Vendor1 + Coordinator + Vendor2 | Coordinator-suggested second vendor |
| `rvcv-handoff` | `rvcv_handoff_demo.py` | Reporter + Vendor1 → Coordinator + Vendor2 | Case-ownership transfer to coordinator |
| `rvv` | `rvv_demo.py` | Reporter + Vendor1 + Vendor2 | Direct invitation of a second vendor |

<!-- END GENERATED SCENARIO TABLE -->

## Running scenario demos

Scenario demos require multiple running containers. Use the multi-actor
Docker Compose file:

```bash
# rv scenario
cd docker && docker compose -f docker-compose-multi-actor.yml up
```

Or with the unified CLI (after starting the appropriate containers):

```bash
vultron-demo rv
```

See the parent `README.md` and `docker/README.md` for full setup instructions.
