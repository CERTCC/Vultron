---
title: Designed self-healing recovery paths must not log at ERROR
type: learning
timestamp: 2026-08-11
source: ISSUE-2169
signal: concern
---

## What happened

`ReconstructChainTailNode` hit CLP-08-005 (empty ledger + no per-case genesis
hash) during the fvcv-handoff pre-genesis window and logged at `ERROR`, even
though this is an **expected, self-healing** condition: the
`ReconstructOrRejectOnMissingCase` selector fires a `Reject(CaseLedgerEntry)`
with `last_accepted_hash=""` and the CaseActor replays from genesis
(SYNC-15-001). The demo job passes on the demo-runner exit code and invariants
read JSONL — neither greps logs — so the churn was non-fatal, but the `ERROR`
line on `finder-1` read as a failure during triage of PR #2168.

## Why it matters

Log level is a contract with whoever reads the logs (humans and CI log scans).
A protocol path that is *designed to recover* — where a downstream node
guarantees convergence — is a `WARNING` (recoverable) or `INFO`, not an
`ERROR`. Logging designed recoveries at `ERROR` manufactures false failure
signals and wastes triage cycles chasing self-healing noise.

## How to apply

Before logging at `ERROR` in a BT node, ask: is there a wired fallback/reject
node that makes this self-heal? If yes, downgrade to `WARNING` and name the
recovery in the message. Reserve `ERROR` for conditions with no recovery path.
Here the `except VultronValidationError` branch is provably the *only*
pre-genesis case (that helper raises for nothing else), so the downgrade is
precisely scoped — genuine chain corruption is handled by a different node
(`CheckHashOrRejectOnMismatchNode`) and still logs loudly.

## Root cause vs symptom

Issue #2169 fixed the symptom (log level). The underlying protocol gap — no
pre-genesis buffer for `Announce(CaseLedgerEntry)` arriving before
`Create(VulnerabilityCase)` — is tracked as **#2186** (child of #2136, blocks
the merge-to-main task #2143). See
[[20260810-clp-08-005-protocol-hardening-gap]].

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: designed self-healing recovery paths must not log at ERROR.
Docs PR: TBD.
