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

| Sub-command       | Script                    | What it demonstrates                                                |
|-------------------|---------------------------|---------------------------------------------------------------------|
| `fv`              | `fv_demo.py`              | FV (Finder + Vendor) CVD workflow                                   |
| `fvv`             | `fvv_demo.py`             | FVV (Finder + Vendor1 + Vendor2) multi-vendor workflow              |
| `fvcv-handoff`    | `fvcv_handoff_demo.py`    | FVCV with ownership handoff from Coordinator to Vendor              |
| `fvcv-extension`  | `fvcv_extension_demo.py`  | FVCV with embargo extension                                         |
| `fccv-handoff`    | `fccv_handoff_demo.py`    | FCCV with case ownership handoff                                    |
| `fccv-extension`  | `fccv_extension_demo.py`  | FCCV with embargo extension                                         |
| `fcvcv`           | `fcvcv_demo.py`           | FCVCV (Finder + Coordinator + Vendor + Coordinator2) full lifecycle |
| `fcv`             | `fcv_demo.py`             | FCV (Finder + Coordinator + Vendor) full VFDPxa lifecycle           |
| `fcv-reject`      | `fcv_reject_demo.py`      | FCV with Vendor rejecting the case invitation (RM rejection)        |
| `vc`              | `vc_demo.py`              | VC (Vendor self-discovers, Coordinator joins as Observer)           |

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
