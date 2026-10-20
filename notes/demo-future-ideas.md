---
title: Planned Demo Scenarios and Future Demo Ideas
status: active
kind: plan
tracks:
  - "#1160"
  - "#1161"
  - "#1278"
  - "#1279"
  - "#1732"
  - "#2050"
  - "#2591"
  - "#2594"
  - "#3671"
  - "#3672"
  - "#3701"
  - "#3702"
  - "#3937"
  - "#4242"
  - "#4243"
  - "#4244"
  - "#4941"
description: >
  The planned-scenario register (DEMOCI-11-010) — every demo scenario with a
  spec group and no demo module yet — followed by planned multi-actor
  scenarios that have no spec group, each with its tracking Task.
relevant_packages:
  - vultron/demo
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
related_notes:
  - notes/demo-interactive-ui.md
  - notes/demo-scenario-registry.md
  - notes/event-driven-control-flow.md
  - notes/call-out-simulation-plan.md
  - notes/cvd-recipe-injects.md
---

# Planned Demo Scenarios and Future Demo Ideas

## Scenario naming convention

Scenarios are named by the sequence of actor roles involved:

- **R** = Reporter, **V** = Vendor, **C** = Coordinator, **D** = Deployer
- Numbers distinguish multiple actors of the same role (V1, V2, C1, C2)
- No scenario uses the retired **F** = Finder letter: a Finder that enters the
  protocol is a Reporter (ADR-0078)

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
| `rcvd` | #2594 | DEMOMA-24, DEMOMA-16-014 | V develops the fix; D deploys it in their own environment (d→D, gated on the CSB-15-004 causal precondition) |
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

## Planned scenarios with no spec group

Nothing below is in either register. Except for the in-process fuzz row (see
below the table), none of these has a spec group, so DEMOCI-11-010 does not
govern them and none has a name in the registry's grammar yet. A scenario earns
a row in the [planned scenario register](#planned-scenario-register) when its
spec group is written, and a `@scenario` decorator when its demo is.

| Scenario | Tracking issue | What it would demonstrate | Status |
|---|---|---|---|
| In-process fuzz | #1732 | RCV in-process with STOCHASTIC bundles over N configurable iterations, run as `vultron demo fuzz` | see below |
| Case split | #4242 (build), #4243 (demo) | A Vendor case spawns a child case for a second Vendor; the child inherits only the embargo (ADR-0125, CM-32) | planned |
| Case merge | #4244 | Owner-consent offer; the offered case freezes and its participants migrate by invitation (ADR-0105) | blocked by the merge spec #3701 and build #3702 |
| Multi-reporter | #3671 | Two Reporters; the Coordinator adds the second report to the existing case and invites R2, with no merge | planned |
| Concurrent cases | #3672 | Two independent cases through shared actors, one CaseActor managing both, with no cross-case bleed | planned |
| RM non-linear paths | #2050 | R→I→V in `rvcv-handoff` (tentative rejection, then reconsideration) and A→D→A in `rcvcv` | planned |
| Case Manager direct message | #4941 | The Case Manager sends one participant, possibly an inert one, a private note the case record does not carry (a MAY, never a MUST) | blocked: its wire form is undecided (`docs/topics/future_work/_oq-create-then-add.md`) |

The in-process fuzz scenario is misfiled here: it has a spec group, DEMOMA-18,
so DEMOCI-11-010 places it in the [planned scenario
register](#planned-scenario-register). It cannot move there until DEMOMA-18
carries the MS-13-003 `trigger: {type: scenario_start, value: <name>}` marker
the partition check keys on. Its design is in `notes/call-out-simulation-plan.md`
§ "Multi-Actor In-Process Simulation (#1732, DEMOMA-18)".

The Deployer-role and Vendor-as-reporter scenarios are specified, so they sit in
the planned scenario register as `rcvd` and `vc`. CVD recipe injects are
planned in [cvd-recipe-injects.md](cvd-recipe-injects.md).
