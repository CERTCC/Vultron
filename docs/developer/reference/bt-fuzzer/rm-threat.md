---
stakeholder_type: [project-contributor]
---

# Threat monitoring fuzzer nodes

These stub nodes belong to the `MonitorThreats` fallback tree (`vultron/bt/report_management/_behaviors/monitor_threats.py`).
This tree models the search for evidence of attacks, exploits, or public reports of the vulnerability.
In the simulation, the tree polls each tick with a random result.

In production, threat monitoring is event-driven, not polling (ADR-0046).
An external monitoring actor, or any informed participant, detects a threat signal.
That actor then posts `Add(ParticipantStatus, CaseParticipant)` to the CASE_MANAGER with the matching Public State (PXA) change (X for exploit, A for attacks, P for public disclosure).

The received-side behavior tree (BT) of the CASE_MANAGER, `add_participant_status_tree`, adopts the state into the case status and tears down the embargo.
The nodes below model what that monitoring actor watches for.
None of them is wired into the received-side pipeline of the CASE_MANAGER.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `MonitorAttacks`

- **Node name**: `MonitorAttacks`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan threat intelligence feeds and security telemetry for evidence of active attacks that exploit this vulnerability
- **Input dependency**: Integration with a threat intelligence platform.
  Examples are Information Sharing and Analysis Center (ISAC) feeds, intrusion detection system (IDS) or intrusion prevention system (IPS) alerts, and Security Information and Event Management (SIEM) queries.
  Other inputs are a cyber threat intelligence (CTI) application programming interface (API), or a human analyst review of threat reports.
- **Notes**: Succeeds rarely, because few in-the-wild attacks are detected during active coordination
- **Automation potential**: **High** — SIEM queries, IDS/IPS alert feeds, and threat-intelligence platform APIs can fully automate the detection of in-the-wild attacks.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorAttacks`
- **Call-out point shape**: Retriever — synchronous per-tick query to threat-intelligence feeds or SIEM/IDS telemetry.
  It returns SUCCESS if it detects active attacks, and FAILURE otherwise.
  The BT invokes this node on demand each tick.
  The node does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Internal logic of the monitoring actor, not wired into the CASE_MANAGER received-side pipeline.
  The monitoring actor posts `Add(ParticipantStatus)` with A=True when it detects attacks.

## `MonitorExploits`

- **Node name**: `MonitorExploits`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan exploit databases and vulnerability intelligence sources for new published exploits that target this vulnerability
- **Input dependency**: Exploit database feeds (ExploitDB, Metasploit, GitHub), threat intelligence platforms, Common Vulnerabilities and Exposures (CVE) / National Vulnerability Database (NVD) exploit availability fields, or human analyst monitoring
- **Notes**: Rarely succeeds.
  Public exploits usually appear after disclosure, not during the coordination phase.
- **Automation potential**: **High** — exploit database feeds, CVE enrichment APIs, and threat-intel platforms can fully automate the monitoring of exploit publication.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorExploits`
- **Call-out point shape**: Retriever — synchronous per-tick query to exploit database feeds or threat-intelligence platforms.
  It returns SUCCESS if it finds a new published exploit, and FAILURE otherwise.
  The BT invokes this node on demand each tick.
  The node does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Internal logic of the monitoring actor, not wired into the CASE_MANAGER received-side pipeline.
  The monitoring actor posts `Add(ParticipantStatus)` with X=True when it detects an exploit.

## `MonitorPublicReports`

- **Node name**: `MonitorPublicReports`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan public sources (news, social media, security blogs, full-disclosure lists) for reports that show this vulnerability is publicly known
- **Input dependency**: Open-source intelligence (OSINT) tools, Really Simple Syndication (RSS) or news feed monitoring, social media tracking, or human analyst media review
- **Notes**: Triggers more often than attack or exploit detection.
  Public discussion of vulnerabilities is more common than confirmed attacks.
- **Automation potential**: **High** — RSS/news feed monitoring, OSINT tools, and social-media tracking APIs can automate public disclosure detection with high coverage.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorPublicReports`
- **Call-out point shape**: Retriever — synchronous per-tick query to OSINT feeds, news/RSS sources, or social-media tracking APIs.
  It returns SUCCESS if it finds evidence of public disclosure, and FAILURE otherwise.
  The BT invokes this node on demand each tick.
  The node does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Internal logic of the monitoring actor, not wired into the CASE_MANAGER received-side pipeline.
  The monitoring actor posts `Add(ParticipantStatus)` with P=True when it detects public disclosure.

## `NoThreatsFound`

- **Node name**: `NoThreatsFound`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Fallback leaf — confirm that this monitoring cycle detected no threats.
  This leaf prevents failure of the monitoring branch when all monitoring nodes return failure.
- **Input dependency**: None.
  This node is a terminal success placeholder.
- **Notes**: Makes sure that `MonitorThreats` always succeeds, so the larger workflow continues without interruption
- **Automation potential**: **TerminalPlaceholder** — terminal success placeholder.
  It needs no real decision logic.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.NoThreatsFound`
- **Call-out point shape**: ProtocolInternal — terminal success placeholder.
  This AlwaysSucceed fallback leaf prevents failure of MonitorThreats when this monitoring cycle detects no active threats.
  It has no external input, output, or monitoring seam.
- **Factory-fn placement**: N/A — terminal success leaf of the internal `MonitorThreats` tree of the monitoring actor.
  It has no CASE_MANAGER received-side role.
