---
title: Future Demo Ideas
status: active
description: >
  Future demo scenarios and multi-actor workflow ideas for the Vultron
  prototype. Scenario planning tracked in GitHub Issues under epic #1093.
relevant_packages:
  - vultron/demo
related_notes:
  - notes/event-driven-control-flow.md
---

# Future Demo Ideas

## Scenario naming convention

Scenarios are named by the sequence of actor roles involved:

- **R** = Reporter (preferred; replaces the older **F** = Finder convention for new scenarios), **V** = Vendor, **C** = Coordinator, **D** = Deployer
- Numbers distinguish multiple actors of the same role (V1, V2, C1, C2)
- Existing scenario names that use **F** (FV, FCV, FCVCV, etc.) are not renamed retroactively; new scenarios use **R**

## Implemented scenarios

| Scenario | File | Description |
|----------|------|-------------|
| FV | `vultron/demo/scenario/fv_demo.py` | Finder + Vendor; simple coordination |
| FVV | `vultron/demo/scenario/fvv_demo.py` | Finder → Vendor1 → Vendor2; no coordinator; independent fix paths (implements #1265) |
| FVCV-extension | `vultron/demo/scenario/fvcv_extension_demo.py` | V1 retains ownership; C is participant; C suggests V2 via ADR-0026 flow; Vendor1 approves; the CASE_MANAGER invites V2 (implements #1535) |
| FCCV-extension | `vultron/demo/scenario/fccv_extension_demo.py` | C1 retains ownership; C2 is coordinator participant; C2 suggests V via ADR-0026 flow; C1 approves; the CASE_MANAGER invites V (implements #1620) |

## Deprecated / idea-mine only

The following files exist but are based on much older code and no longer work.
They may be useful as reference for future scenario development but should not
be treated as working implementations.

| Scenario | File | Notes |
|----------|------|-------|
| FCV | ~~`vultron/demo/scenario/three_actor_demo.py`~~ (deleted PR #1720) | Superseded by `fcv_demo.py` (PR #1623) |
| FVCV (handoff) | ~~`vultron/demo/scenario/multi_vendor_demo.py`~~ (deleted PR #1720) | Superseded by `fvcv_handoff_demo.py`; see #1214 |

## Planned scenarios (from #1131 planning, 2026-07-06)

### Core multi-party scenarios

| Scenario | Issue | Description | Blocked by | Status |
|----------|-------|-------------|------------|--------|
| FCV | #1593 | F reports to C; C invites V; three-actor coordination | — | **implemented** (#1623) — `fcv` CLI command + CI job |
| FVCV-handoff | #1214 | V1 transfers ownership to C; C invites V2 | — | **implemented** (#1561) — `fvcv-handoff` CLI command + CI job |
| FCCV-extension | #1215 | C1 retains case; C2 is participant; C2 asks C1 to invite V | — | **implemented** (#1620) — `fccv-extension` CLI command + CI job |
| FCCV-handoff | #1216 | C1 transfers to C2; C2 invites V | — | **implemented** (#1216) — `fccv-handoff` CLI command + CI job |
| FCVCV | #1217 | F+C1+V1+C2+V2 (5 actors) | #1212, #1215 | **implemented** (#1962) — `fcvcv` CLI command + CI job |

### Fuzz simulation scenarios

| Scenario | Issue | Description | Status |
|----------|-------|-------------|--------|
| In-process fuzz | #1178 | FCV in-process; STOCHASTIC bundles; N configurable iterations; `vultron demo fuzz` CLI command | planned |
| Multi-container fuzz | *(future Idea under "stochastic demos" Epic)* | Containerised variant of #1178; each actor in its own container; STOCHASTIC bundles configurable via environment; container state reset between iterations | idea-stage |

The multi-container variant is deferred until container reset and STOCHASTIC
bundle configuration via environment variables are designed. See
`notes/call-out-configuration.md` § "Multi-Actor In-Process Simulation" for
the design decisions reached in the #1178 planning session.

### Role-expansion scenarios

| Scenario | Issue | Description | Status |
|----------|-------|-------------|--------|
| Deployer role | #1227 | V develops fix; D deploys in their environment | planned — `fcvd` CLI command + CI job (DEMOMA-24); blocked by CSB-15-004 deployer causal-gate |
| Case split/merge | #1229 | Parent/child/sibling case relationships | |
| Multi-reporter | #1231 | Two Finders, one C consolidates into one case | |

### Embargo lifecycle scenarios

| Scenario | Issue | Description | Status |
|----------|-------|-------------|--------|
| RCV-embargo | #1222 | R+C+V; post-submission negotiation (variation b) + deliberate termination (variation e); EP→EA→ET arc | planned — `rcv-embargo` CLI command + CI job (DEMOMA-20, DEMOCI-07) |
| RCVV-embargo | #1222 | R+C+V1+V2; variations b+c+f+d; EP→EA→EV→EJ→auto-collapse via CS.P; V2 late-invite | planned — `rcvv-embargo` CLI command + CI job (DEMOMA-21, DEMOCI-07) |
| Pre-submission negotiation | *(new Idea, child of epic #1083)* | EP before report submission (variation a); blocked by EP-04-003 protocol gap — no mechanism for reporter to include embargo proposal with/before report; see `notes/embargo-default-semantics.md` | idea-stage |

### Cross-cutting variations (composable with any scenario)

| Variation | Issue | Description |
|-----------|-------|-------------|
| Invitation rejection | #1218 | Invited actor transitions RM:R→I→C |
| Tentative rejection | #1221 | Invited actor transitions RM:R→I→V (reconsiders) |
| Embargo variations | #1222 | Negotiation, collapse, deliberate delay (see embargo lifecycle scenarios above) |
| CVD recipe injects | #1223 | Twists from the CERT Guide to CVD cvd_recipes |

### Pre-case ACK flow (`auto_create_case=False`)

Issue #1133 introduced `ActorConfig.auto_create_case` (default: `True`). When
`False`, the receiver stores the inbound report but does **not** auto-create a
`VulnerabilityCase`, enabling the receiver to send a pre-case
`Read(Offer(Report))` acknowledgment (`AckReportReceivedUseCase`) before
deciding to accept or reject.

The **tentative rejection → acceptance** scenario (#1221) is the first planned
demo to exercise this path:

1. Finder submits report.
2. Vendor (with `auto_create_case=False`) sends pre-case ACK via trigger.
3. Vendor invalidates report (RM:R→I) — "tentative rejection".
4. Vendor later validates (RM:I→V) and engages — "reconsideration".

Once #1221 is implemented, `ack_report` should be wired into the per-scenario
`_*_EXPECTED_EVENT_TYPES` tuples under `test/ci/invariants/` (e.g.
`_FV_EXPECTED_EVENT_TYPES` in `test/ci/invariants/test_fv_invariants.py`,
currently excluded; see the `test_invariant_5_expected_event_types_present`
docstring citing #1133).

See also: #1079 (multi-coordinator motivation from FIRSTCON 2026)
