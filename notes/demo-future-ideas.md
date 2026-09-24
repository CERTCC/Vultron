---
title: Planned Demo Scenarios and Future Demo Ideas
status: active
description: >
  The planned-scenario register (DEMOCI-11-010) — every demo scenario with a
  spec group and no demo module yet — followed by multi-actor workflow ideas
  that have no spec group. Scenario planning tracked in GitHub Issues under
  epic #1093.
relevant_packages:
  - vultron/demo
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/demo-scenario-registry.md
  - notes/event-driven-control-flow.md
---

# Planned Demo Scenarios and Future Demo Ideas

## Scenario naming convention

Scenarios are named by the sequence of actor roles involved:

- **R** = Reporter (preferred; replaces the older **F** = Finder convention for new scenarios), **V** = Vendor, **C** = Coordinator, **D** = Deployer
- Numbers distinguish multiple actors of the same role (V1, V2, C1, C2)
- Existing scenario names that use **F** (FV, FCV, FCVCV, etc.) are not renamed retroactively; new scenarios use **R**

## Planned scenario register

This is the **second of the two registers** DEMOCI-11-010 defines. A demo
scenario that has a spec group sits in exactly one of them: the scenario
registry (`vultron/demo/scenario/registry.py`) if it is built, this table if it
is specified but not yet built. The partition is checked in both directions —
see [demo-scenario-registry.md](demo-scenario-registry.md).

Scenario names are spelled in the registry's name grammar, because that is what
the check keys on and what the sub-command will be. Rows are in name order, the
canonical order for every scenario table.

| Scenario | Tracking issue | Spec IDs | What it would demonstrate |
|---|---|---|---|
| `fcvd` | #1227 | DEMOMA-24, DEMOMA-16-014 | V develops the fix; D deploys it in their own environment (d→D, gated on the CSB-15-004 causal precondition) |
| `rcv-embargo` | #1222 | DEMOMA-20, DEMOCI-07 | R+C+V; post-submission negotiation (variation b) + deliberate termination (variation e); EP→EA→ET arc |
| `rcvv-embargo` | #1222 | DEMOMA-21, DEMOCI-07 | R+C+V1+V2; variations b+c+f+d; EP→EA→EV→EJ→auto-collapse via CS.P; V2 late-invite |
| `vc` | #2591 | DEMOMA-25, DEMOMA-16-015 | V self-reports and owns the case; C joins as Observer |

**Do not list a built scenario here.** Registration means built, so a scenario
that appears in both registers fails the partition check. The built scenarios
are enumerated by the generated tables in
[`vultron/demo/scenario/README.md`](../vultron/demo/scenario/README.md) and
[`test/ci/README-case-log-ratchet.md`](../test/ci/README-case-log-ratchet.md);
this note deliberately keeps no copy of them.

**Do not list an idea here either.** A row in this register asserts that a spec
group specifies the scenario, and the check enforces that. Scenario ideas with
no spec group belong in the sections below.

## Scenario ideas with no spec group (from #1131 planning, 2026-07-06)

Nothing below is in either register: none of these has a spec group, so
DEMOCI-11-010 does not govern them and none has a name in the registry's
grammar yet. An idea earns a row in the [planned scenario
register](#planned-scenario-register) when its spec group is written, and a
`@scenario` decorator when its demo is.

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
| Case split/merge | #1229 | Parent/child/sibling case relationships | |
| Multi-reporter | #1231 | Two Finders, one C consolidates into one case | |

The Deployer-role and Vendor-as-finder ideas from this group are specified, so
they sit in the [planned scenario register](#planned-scenario-register) as
`fcvd` and `vc` instead.

### Embargo lifecycle scenarios

| Scenario | Issue | Description | Status |
|----------|-------|-------------|--------|
| Pre-submission negotiation | *(new Idea, child of epic #1083)* | EP before report submission (variation a); blocked by EP-04-003 protocol gap — no mechanism for reporter to include embargo proposal with/before report; see `notes/embargo-default-semantics.md` | idea-stage |

The RCV-embargo and RCVV-embargo scenarios from this group are specified, so
they sit in the [planned scenario register](#planned-scenario-register) as
`rcv-embargo` and `rcvv-embargo` instead.

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

## Deprecated / idea-mine only

The following files exist but are based on much older code and no longer work.
They may be useful as reference for future scenario development but should not
be treated as working implementations.

| Scenario | File | Notes |
|----------|------|-------|
| FCV | ~~`vultron/demo/scenario/three_actor_demo.py`~~ (deleted PR #1720) | Superseded by `fcv_demo.py` (PR #1623) |
| FVCV (handoff) | ~~`vultron/demo/scenario/multi_vendor_demo.py`~~ (deleted PR #1720) | Superseded by `fvcv_handoff_demo.py`; see #1214 |

See also: #1079 (multi-coordinator motivation from FIRSTCON 2026)
