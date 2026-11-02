---
source: NOTES-configuration--yaml-file-format
timestamp: '2026-11-02T14:40:16.248586+00:00'
title: YAML File Format
type: note
---

**Archived:** 2026-11-02
**Reason:** delivered — removed from notes/configuration.md in #4496 without an archive entry; the reader-facing page now carries this content, generated from AppConfig so it cannot drift (this section had already drifted: its `server.base_url` default lacked `/api/v2`)
**Superseded by:** docs/reference/configuration.md (vultron/metadata/docs/config_reference.py), issue #4171

---

## YAML File Format

The canonical `config.yaml` schema:

```yaml
# config.yaml — Vultron application configuration
# All fields are optional; omit to use defaults.

server:
  base_url: "http://localhost:7999"
  log_level: "INFO"

database:
  db_url: "sqlite:///vultron.db"

actor:
  auto_create_case: true
  default_case_roles: []
  case_actor_service_url: "http://case-actor:7999/api/v2"

ledger:
  clock_skew_tolerance_seconds: 300
  future_tolerance_seconds: 300
  staleness_window_days: 7
```

The `ledger:` section maps to `AppConfig.ledger` (`LedgerConfig`,
`vultron/config/ledger.py`). It exposes the timestamp tolerances the CaseActor
applies to a *claimed* `payloadSnapshot.published` at its commit boundary
(CLP-14-009). Thresholds are stored as plain integers because they are set from
the environment; the `timedelta` properties (`clock_skew_tolerance`,
`future_tolerance`, `staleness_window`) are what the guard consumes.

- `clock_skew_tolerance_seconds`: slack on the CLP-14-006 check that an
  assertion is not stamped before its parent case was created. Non-zero because
  participant and CaseActor clocks are not synchronised — ADR-0079 rejected
  wall-clock ordering for that reason.
- `future_tolerance_seconds`: CLP-14-007 ceiling on how far ahead of the
  CaseActor's clock a claimed timestamp may be.
- `staleness_window_days`: CLP-14-008 window on how far behind it may be.

Which timestamp each threshold governs is the load-bearing detail — see
[notes/case-ledger-authority.md](case-ledger-authority.md) § "An Entry Has Two
Timestamps, and They Belong to Different Layers".

The `actor:` section maps to `AppConfig.actor` (`ActorConfig`). It controls
actor-policy defaults used by BT nodes and the production adapter:

- `auto_create_case`: when `true` (default), create a `VulnerabilityCase`
  immediately on `Offer(Report)` receipt (ADR-0015 Option 4).  Set to
  `false` to defer case creation so a pre-case ACK can be sent first
  (CM-15-001, issue #1133).
- `default_case_roles`: list of CVD role strings (e.g. `["coordinator"]`)
  assigned to the local actor when it creates or takes ownership of a case.
  `CVDRole.CASE_OWNER` is always appended at participant-creation time
  (BTND-05-002) and does not need to be listed here. A report receiver states
  these roles on its `Create(CaseProposal)` as `proposerCaseRoles`, and the
  CaseActor seats it with them; the CaseActor never reads its own
  `default_case_roles` for a proposer (CP-01-011, CP-09-007, ADR-0133).
- `case_actor_service_url`: base URL of the dedicated CaseActor container
  (e.g., `http://case-actor:7999/api/v2`). Required for any actor whose BT
  may run the `engage-case` path (i.e., case-creating actors). Absence causes
  `ResolveCaseActorUrlsNode` to return `FAILURE` with a clear error message.
  `None` by default; MUST be supplied via `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`
  or the `config.yaml` `actor:` block. See CP-08-001, `notes/case-proposal.md`.
- `min_rsvp_window` (72 h) and `default_rsvp_window` (7 d): the EP-07-002
  minimum and the CM-18-002 policy window for an embargo invitation's RSVP
  deadline. Both are measured from the invite's `published` time and bounded
  by the embargo's end (EP-07-006); see
  [notes/embargo-default-semantics.md](embargo-default-semantics.md). Inbound
  extraction reads them through `_resolve_actor_config()` on both inbox paths
  (`process_payload(actor_config=...)` and `prepare_for_dispatch()`); when no
  `ActorConfig` loads, the protocol defaults apply.
- `protocol_default_embargo_duration` (72 h): the embargo applied at case
  creation when no proposal and no actor default applies (EP-04-005). A value
  outside `[72 hours, 5 days]` is refused at load. It never competes under
  shortest-wins and is not a minimum (EP-04-006, EP-04-007).
