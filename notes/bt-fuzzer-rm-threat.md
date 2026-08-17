---
title: "BT Fuzzer Nodes: RM Threat Monitoring"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Threat Monitoring sub-workflow
  (`MonitorThreatsBt`): active-threat detection, severity escalation,
  and threat-monitoring nodes used in simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-fuzzer-nodes-report-management.md
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/report_management
---

## Production Architecture Note (supersedes polling model)

> **IDEA-1836 (2026-07-30)**: In production, threat monitoring is **event-driven**,
> not polling. An external **sentinel actor** (or any informed participant) detects
> a threat signal and posts `Add(ParticipantStatus, CaseParticipant)` to the CaseActor
> with the appropriate PXA state change (X=True for exploit, A=True for attacks,
> P=True for public disclosure). The CaseActor's received-side BT
> (`add_participant_status_tree` → StatusAdoptionGate → self `Add(CaseStatus)` →
> `add_case_status_tree` → EmbargoTeardownAuthorizationGate → ThreatTerminationBranchNode) handles
> state canonicalization and embargo teardown.
>
> The four nodes catalogued below are valid fuzzer stubs for the **sentinel actor's
> internal monitoring logic** — they model what the sentinel watches for. They are
> not wired into the CaseActor's received-side pipeline.
>
> See `notes/received-status-authorization.md` and ADR-0046 for the production design.

## Threat Monitoring

These nodes belong to the `MonitorThreats` fallback tree
(`vultron/bt/report_management/_behaviors/monitor_threats.py`), which models
continuous scanning for evidence that the vulnerability is being actively
exploited in the wild. Threat detection can trigger embargo termination via
`TerminateEmbargoBt`.

In the simulation, this tree polls probabilistically each tick. In production,
the sentinel actor runs equivalent logic and posts the result as an
`Add(ParticipantStatus)` activity rather than mutating case state directly.

### `MonitorAttacks`

- **Node name**: `MonitorAttacks`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan threat intelligence feeds
  and security telemetry for evidence of active attacks exploiting this
  vulnerability
- **Input dependency**: Threat intelligence platform integration (e.g.,
  ISAC feeds, IDS/IPS alerts, SIEM queries), CTI API, or human analyst
  review of threat reports
- **Notes**: Succeeds rarely to reflect the low base rate of detected
  in-the-wild attacks during active coordination
- **Automation potential**: **High** — SIEM queries, IDS/IPS alert feeds, and threat-intelligence platform APIs can fully automate in-the-wild attack detection.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorAttacks`
- **Call-out point shape**: Retriever — synchronous per-tick query to threat-intelligence feeds or SIEM/IDS telemetry; returns SUCCESS if active attacks are detected, FAILURE otherwise. The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Sentinel actor internal logic — not wired into
  CaseActor received-side pipeline. Issue #1250 (polling factory) superseded
  by IDEA-1836 (event-driven sentinel pattern). The sentinel runs equivalent
  logic and posts `Add(ParticipantStatus)` with CS.A=True when attacks are
  detected.

### `MonitorExploits`

- **Node name**: `MonitorExploits`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan exploit databases and
  vulnerability intelligence sources for newly published exploits targeting
  this vulnerability
- **Input dependency**: Exploit database feeds (ExploitDB, Metasploit,
  GitHub), threat intelligence platforms, CVE/NVD exploit availability
  fields, or human analyst monitoring
- **Notes**: Rarely succeeds; public exploits typically appear after
  disclosure, not during the coordination phase
- **Automation potential**: **High** — exploit database feeds, CVE enrichment APIs, and threat-intel platforms can fully automate exploit publication monitoring.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorExploits`
- **Call-out point shape**: Retriever — synchronous per-tick query to exploit database feeds or threat-intelligence platforms; returns SUCCESS if a newly published exploit is found, FAILURE otherwise. The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Sentinel actor internal logic — not wired into
  CaseActor received-side pipeline. Issue #1250 (polling factory) superseded
  by IDEA-1836 (event-driven sentinel pattern). The sentinel runs equivalent
  logic and posts `Add(ParticipantStatus)` with CS.X=True when an exploit
  is detected.

### `MonitorPublicReports`

- **Node name**: `MonitorPublicReports`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan public sources (news,
  social media, security blogs, full-disclosure lists) for reports of
  this vulnerability being publicly known
- **Input dependency**: Open-source intelligence (OSINT) tools, RSS/news
  feed monitoring, social media tracking, or human analyst media review
- **Notes**: Somewhat more likely to trigger than attack/exploit detection
  because public discussion of vulnerabilities is more common than
  confirmed attacks
- **Automation potential**: **High** — RSS/news feed monitoring, OSINT tools, and social-media tracking APIs can automate public disclosure detection with high coverage.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorPublicReports`
- **Call-out point shape**: Retriever — synchronous per-tick query to OSINT feeds, news/RSS sources, or social-media tracking APIs; returns SUCCESS if public disclosure evidence is found, FAILURE otherwise. The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Sentinel actor internal logic — not wired into
  CaseActor received-side pipeline. Issue #1250 (polling factory) superseded
  by IDEA-1836 (event-driven sentinel pattern). The sentinel runs equivalent
  logic and posts `Add(ParticipantStatus)` with CS.P=True when public
  disclosure is detected.

### `NoThreatsFound`

- **Node name**: `NoThreatsFound`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Fallback leaf — confirm that no threats were
  detected in this monitoring cycle; keep the monitoring branch from
  failing when all monitoring nodes return failure
- **Input dependency**: None; terminal success placeholder
- **Notes**: Ensures `MonitorThreats` always succeeds so the broader
  workflow continues uninterrupted
- **Automation potential**: **TerminalPlaceholder** — terminal success placeholder; no real decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.NoThreatsFound`
- **Call-out point shape**: ProtocolInternal — terminal success placeholder; AlwaysSucceed fallback leaf that prevents MonitorThreats from failing when no active threats are detected in this monitoring cycle; no external input, output, or monitoring seam.
- **Factory-fn placement**: N/A — ProtocolInternal terminal success leaf in
  the sentinel actor's internal `MonitorThreats` tree. Issue #1250 (polling
  factory) superseded by IDEA-1836. No CaseActor received-side role.

---
