---
stakeholder_type: [project-contributor]
---

# Vulnerability discovery fuzzer nodes

These stub nodes belong to the `DiscoverVulnerabilityBt` fallback tree (`vultron/bt/vul_discovery/behaviors.py`), one of the four top-level branches of `CvdProtocolRoot`.
The tree models how a participant with the FINDER role searches for and discovers a new vulnerability.

The tree exists only for the simulation and has no prototype counterpart.
A real Vultron system starts from creating and submitting a vulnerability report, which is the output of discovery.
Every entry below is therefore simulation-only: its cross-ref, shape, and factory placement are N/A.

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `HaveDiscoveryPriority`

- **Node name**: `HaveDiscoveryPriority`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `FindVulnerabilities` (within `DiscoverVulnerabilityBt`)
- **Semantic function**: Condition check — has the participant decided to prioritize vulnerability discovery as a current goal?
- **Input dependency**: Organizational priority setting; could be driven by human tasking, scheduled policy, or an automated work-queue query
- **Notes**: Always succeeds in simulation to keep the discovery loop active
- **Automation potential**: **High** — static role/capability configuration check; can be fully automated as a lookup against the participant's role metadata or organizational task queue.
- **New-arch cross-ref**: N/A — simulation-only BT not ported to new architecture
- **Call-out point shape**: N/A
- **Factory-fn placement**: N/A

## `DiscoverVulnerability`

- **Node name**: `DiscoverVulnerability`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `FindVulnerabilities` (within `DiscoverVulnerabilityBt`)
- **Semantic function**: Action — execute a vulnerability discovery activity, such as fuzzing, code audit, pentesting, or research
- **Input dependency**: Results from a vulnerability research tool, a researcher's findings, or an automated scanning system
- **Notes**: Succeeds often enough to drive simulation throughput while still modeling that discovery is not guaranteed on every cycle
- **Automation potential**: **Low** — inherently a human or tool-driven research activity (fuzzing, code audit, pentesting); results must be fed in from an external research pipeline.
- **New-arch cross-ref**: N/A — simulation-only BT not ported to new architecture
- **Call-out point shape**: N/A
- **Factory-fn placement**: N/A

## `NoVulFound`

- **Node name**: `NoVulFound`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vul_discovery/fuzzer.py`
- **Parent tree**: `DiscoverVulnerabilityBt`
- **Semantic function**: Fallback leaf — acknowledge that no vulnerability was discovered in this tick; keep the overall BT from failing
- **Input dependency**: None (terminal success placeholder); no external input needed once we confirm discovery came up empty
- **Notes**: Ensures the discovery branch always succeeds so the top-level sequence can continue to other work
- **Automation potential**: **TerminalPlaceholder** — terminal success placeholder; no real decision logic required.
- **New-arch cross-ref**: N/A — simulation-only BT not ported to new architecture
- **Call-out point shape**: N/A
- **Factory-fn placement**: N/A
