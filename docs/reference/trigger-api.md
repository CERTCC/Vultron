---
description: >
  The `POST /actors/{actor_id}/trigger/{behavior}` endpoints, each of which
  starts a protocol behavior on an actor's behalf.
stakeholder_type: [platform-developer]
level: 400
---

# Trigger API Reference

{% include-markdown "../includes/not_normative.md" %}

The Vultron reference implementation exposes its general-purpose protocol trigger endpoints at `POST /actors/{actor_id}/trigger/{behavior}`; the table below is generated from the running application, so it lists every endpoint the build knows.
Each endpoint initiates a protocol behavior on behalf of the specified actor; the decision to act has already been made by the caller.
Every endpoint has one row in the trigger registry (`vultron/trigger_registry/`), which records its request model, use case, result type and whether it is general-purpose or demo-only.

All endpoints accept JSON request bodies, return HTTP 202 on success with the
resulting ActivityStreams activity in the response body, and run behavior
execution as a background task so the HTTP response is not blocked.

!!! tip "Interactive exploration"

    When running the reference implementation locally, visit `/docs` for an
    interactive Swagger UI over the same schema this page is generated from.

For a conceptual overview of how trigger endpoints fit into the two-surface
integration model, see
[Wiring a Capability](../howto/wire_capability.md#background).

---

```python exec="true" idprefix=""
import sys
from pathlib import Path

_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))
sys.path.insert(0, str(_repo / "docs" / "_scripts"))

from render_trigger_api import render  # noqa: E402
print(render())
```
