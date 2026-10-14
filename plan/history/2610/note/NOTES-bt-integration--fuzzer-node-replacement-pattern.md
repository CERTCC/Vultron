---
source: NOTES-bt-integration--fuzzer-node-replacement-pattern
timestamp: '2026-10-12T19:35:41.891339+00:00'
title: Fuzzer node replacement pattern
type: note
---

**Archived:** 2026-10-12
**Reason:** superseded: fuzzer nodes are replaced by call-out points with injected backend factories, not policy classes
**Superseded by:** ADR-0025; notes/call-out-configuration.md

---

**Fuzzer node replacement pattern**: Create a policy class with a clear
interface (e.g., `ValidationPolicy.is_credible(report) -> bool`) and a
default `AlwaysAcceptPolicy` implementation. This provides a deterministic
stub with an explicit extension point.
