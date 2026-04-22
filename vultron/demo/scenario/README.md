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

| Sub-command    | Script                 | What it demonstrates                                          |
|----------------|------------------------|---------------------------------------------------------------|
| `two-actor`    | `two_actor_demo.py`    | Two-actor (Finder + Vendor) CVD workflow                      |
| `three-actor`  | `three_actor_demo.py`  | Three-actor (Finder + Vendor + Coordinator) CVD workflow      |
| `multi-vendor` | `multi_vendor_demo.py` | Multi-vendor workflow with ownership transfer                 |

## Running scenario demos

Scenario demos require multiple running containers. Use the multi-actor
Docker Compose file:

```bash
# Two-actor scenario (default)
cd docker && docker compose -f docker-compose-multi-actor.yml up

# Three-actor scenario
DEMO=three-actor cd docker && docker compose -f docker-compose-multi-actor.yml up

# Multi-vendor scenario
DEMO=multi-vendor cd docker && docker compose -f docker-compose-multi-actor.yml up
```

Or with the unified CLI (after starting the appropriate containers):

```bash
vultron-demo two-actor
vultron-demo three-actor
vultron-demo multi-vendor
```

See the parent `README.md` and `docker/README.md` for full setup instructions.
