---
source: NOTES-received-status-authorization--call-out-bundle
timestamp: '2026-10-12T20:11:17.467495+00:00'
title: Call-Out Bundle
type: note
---

**Archived:** 2026-10-12
**Reason:** call-out inventory restated module docstrings and the call-out configuration note
**Superseded by:** notes/call-out-configuration.md; vultron/core/behaviors/status/

---

## Call-Out Bundle

A `StatusAuthorizationCallOutBundle` covers both gates:

```python
@dataclass(frozen=True)
class StatusAuthorizationCallOutBundle:
    status_adoption_gate_factory: CallOutBackendFactory = ...  # RequireCaseOwnerApproval
    embargo_teardown_authorization_gate_factory: CallOutBackendFactory = ...  # RequireCaseOwnerApproval
```

As built, both fields default to `RequireCaseOwnerApproval` (RSH-07-001,
RSH-07-002, ADR-0076). Under ADR-0080 / RSH-07-004 that default is retired along
with the node: no `CallOutBackendFactory` may return an unconditional `FAILURE`
node as the conservative default, because the conservative posture is expressed
by the routing subtree's branches, not by a backend that always refuses. Demo and
trusted-participant deployments that need automated adoption MUST explicitly
configure a permissive backend — e.g.:

```python
STATUS_AUTHORIZATION_PERMISSIVE = StatusAuthorizationCallOutBundle(
    status_adoption_gate_factory=lambda n: AlwaysSucceed(n),
    embargo_teardown_authorization_gate_factory=lambda n: AlwaysSucceed(n),
)
```

Placed in `vultron/core/behaviors/call_out/bundles/status_authorization.py`
(core-owned, per ADR-0025 / module layout in `notes/call-out-configuration.md`).

---
