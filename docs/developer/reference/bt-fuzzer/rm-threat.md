---
stakeholder_type: [project-contributor]
---

# Threat monitoring fuzzer nodes

These stub nodes belong to the `MonitorThreats` fallback tree (`vultron/bt/report_management/_behaviors/monitor_threats.py`), which models scanning for evidence of attacks, exploits, or public reports of the vulnerability.
In the simulation the tree polls probabilistically each tick.

In production, threat monitoring is event-driven, not polling (ADR-0046).
An external monitoring actor, or any informed participant, detects a threat signal and posts `Add(ParticipantStatus, CaseParticipant)` to the CASE_MANAGER with the matching PXA change (X for exploit, A for attacks, P for public disclosure).
The CASE_MANAGER's received-side behavior tree (BT) (`add_participant_status_tree` → `add_case_status_tree`) canonicalizes the state and tears down the embargo.
The nodes below model what that monitoring actor watches for; none is wired into the CASE_MANAGER's received-side pipeline.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `MonitorAttacks`

- **Node name**: `MonitorAttacks`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan threat intelligence feeds and security telemetry for evidence of active attacks exploiting this vulnerability
- **Input dependency**: Threat intelligence platform integration, such as Information Sharing and Analysis Center (ISAC) feeds, intrusion detection system (IDS) or intrusion prevention system (IPS) alerts, and Security Information and Event Management (SIEM) queries; a cyber threat intelligence (CTI) application programming interface (API); or human analyst review of threat reports
- **Notes**: Succeeds rarely to reflect the low base rate of detected in-the-wild attacks during active coordination
- **Automation potential**: **High** — SIEM queries, IDS/IPS alert feeds, and threat-intelligence platform APIs can fully automate in-the-wild attack detection.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorAttacks`
- **Call-out point shape**: Retriever — synchronous per-tick query to threat-intelligence feeds or SIEM/IDS telemetry; returns SUCCESS if active attacks are detected, FAILURE otherwise.
  The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Monitoring-actor internal logic, not wired into the CASE_MANAGER received-side pipeline; the monitoring actor posts `Add(ParticipantStatus)` with A=True when it detects attacks.

## `MonitorExploits`

- **Node name**: `MonitorExploits`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan exploit databases and vulnerability intelligence sources for newly published exploits targeting this vulnerability
- **Input dependency**: Exploit database feeds (ExploitDB, Metasploit, GitHub), threat intelligence platforms, Common Vulnerabilities and Exposures (CVE) / National Vulnerability Database (NVD) exploit availability fields, or human analyst monitoring
- **Notes**: Rarely succeeds; public exploits typically appear after disclosure, not during the coordination phase
- **Automation potential**: **High** — exploit database feeds, CVE enrichment APIs, and threat-intel platforms can fully automate exploit publication monitoring.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorExploits`
- **Call-out point shape**: Retriever — synchronous per-tick query to exploit database feeds or threat-intelligence platforms; returns SUCCESS if a newly published exploit is found, FAILURE otherwise.
  The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Monitoring-actor internal logic, not wired into the CASE_MANAGER received-side pipeline; the monitoring actor posts `Add(ParticipantStatus)` with X=True when it detects an exploit.

## `MonitorPublicReports`

- **Node name**: `MonitorPublicReports`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Action/condition — scan public sources (news, social media, security blogs, full-disclosure lists) for reports of this vulnerability being publicly known
- **Input dependency**: Open-source intelligence (OSINT) tools, Really Simple Syndication (RSS) or news feed monitoring, social media tracking, or human analyst media review
- **Notes**: Somewhat more likely to trigger than attack/exploit detection because public discussion of vulnerabilities is more common than confirmed attacks
- **Automation potential**: **High** — RSS/news feed monitoring, OSINT tools, and social-media tracking APIs can automate public disclosure detection with high coverage.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.MonitorPublicReports`
- **Call-out point shape**: Retriever — synchronous per-tick query to OSINT feeds, news/RSS sources, or social-media tracking APIs; returns SUCCESS if public disclosure evidence is found, FAILURE otherwise.
  The BT invokes this node on-demand each tick; it does not run independently or fire a trigger endpoint (see BT-18-006).
- **Factory-fn placement**: Monitoring-actor internal logic, not wired into the CASE_MANAGER received-side pipeline; the monitoring actor posts `Add(ParticipantStatus)` with P=True when it detects public disclosure.

## `NoThreatsFound`

- **Node name**: `NoThreatsFound`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/monitor_threats.py`
- **Parent tree**: `MonitorThreats`
- **Semantic function**: Fallback leaf — confirm that no threats were detected in this monitoring cycle; keep the monitoring branch from failing when all monitoring nodes return failure
- **Input dependency**: None; terminal success placeholder
- **Notes**: Ensures `MonitorThreats` always succeeds so the broader workflow continues uninterrupted
- **Automation potential**: **TerminalPlaceholder** — terminal success placeholder; no real decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.monitor_threats.NoThreatsFound`
- **Call-out point shape**: ProtocolInternal — terminal success placeholder; AlwaysSucceed fallback leaf that prevents MonitorThreats from failing when no active threats are detected in this monitoring cycle; no external input, output, or monitoring seam.
- **Factory-fn placement**: N/A — terminal success leaf of the monitoring actor's internal `MonitorThreats` tree; no CASE_MANAGER received-side role.
