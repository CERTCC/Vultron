---
title: "CSB-16-001 scope: received-wire adjudication is exempt from strict VFD adjacency"
type: learning
timestamp: "2026-08-22T00:00:00Z"
source: ISSUE-2478
signal: spec-ambiguity
---

During implementation of CSB-16-001 (VFD transition validation at write boundary), it was unclear whether the spec also required the received-wire adjudication path (`_adjudicate_dimensions` in `_adjudication.py`) to use `is_valid_vfd_transition` (strict adjacency) or whether the weaker `is_monotonic_vfd_forward` check already in use was acceptable.

**Interpretation made**: The received-wire path is explicitly exempt from strict adjacency. A remote peer may legitimately advance through multiple VFD states between status messages (e.g. the vendor becomes aware and develops a fix offline, then sends a single `VFD=VFd` status). The strict adjacency rule of CSB-16-001 applies only to *local* write nodes that advance an actor's own state.

**Evidence**: `_adjudication.py` uses `is_monotonic_vfd_forward` intentionally. A comment was added to document this rationale. CSB-16-001 refers to "a BT node or helper that writes a VFD state" — the adjudication path filters inbound state assertions rather than writing them unconditionally, so the spec's intent appears to be local writes only.

**Recommended follow-up**: CSB-16-001 should be amended to explicitly scope it to local-write paths and carve out the received-wire adjudication exemption. A `spec-gap` or `spec-ambiguity` Concern issue may be appropriate.
