---
source: NOTES-triggerable-behaviors--endpoint-design-sketch
timestamp: '2026-10-12T19:34:27.609757+00:00'
title: Endpoint Design Sketch
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — the trigger endpoints exist with per-behavior request bodies
**Superseded by:** `specs/triggerable-behaviors.yaml` (TRIG-01–TRIG-07); `vultron/adapters/driving/fastapi/routers/trigger_*.py`

---

## Endpoint Design Sketch

```http
POST /actors/{actor_id}/trigger/{behavior-name}
Content-Type: application/json

{
  "offer_id":  "...",   // for report-scoped behaviors (required)
  "report_id": "...",   // confirmation check for report-scoped behaviors
  "case_id":   "...",   // for case-scoped behaviors
  "params":    { ... }, // behavior-specific parameters (e.g., SSVC values)
  "note":      "..."    // optional free-text; embedded in outgoing activity
}
```

Response on success:

```http
HTTP 202 Accepted
Content-Type: application/json

{
  "activity": { ... }   // the resulting ActivityStreams activity
}
```

The formal spec is `specs/triggerable-behaviors.yaml` (TRIG-01 through
TRIG-07).
