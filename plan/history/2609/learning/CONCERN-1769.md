---
source: CONCERN-1769
timestamp: '2026-09-17T20:22:32.382643+00:00'
title: 'UCORG-05 received-side HandlerResult: what it is for'
type: learning
---

## Original concern

UCORG-05 mandated a `UseCaseResult` envelope and forbade `dict`/`None` use-case
return types. It was 0% implemented while three documents described it as done.
For the received (inbound) half it was not clear the requirement as written
bought anything: all 51 received-side `execute()` methods were `-> None`, the
dispatcher discarded the result, and a fieldless `HandlerResult` would change 51
signatures to convey nothing.

Three outcomes were live: an empty envelope (51 mechanical changes, arguably
ceremony), a meaningful envelope (51 per-use-case design decisions), or a spec
amendment narrowing UCORG-05 to the trigger side.

## What planning found

**The answer already existed in the tracker.** #2255 — an open Bug,
"Received-side BT failures cannot reach InboxOutcome; senders always get
202/processed" — described the same three-layer signal drop and explicitly
named #1769 as the place its interface contract gets defined. So a received-side
`HandlerResult` is for carrying a handler's own verdict to `InboxOutcome`. That
settled the choice as the meaningful envelope, and removed the other two options:
an empty envelope leaves the defect untouched, and deleting UCORG-05-002 would
strand a filed bug with no contract to build on.

**The spec corpus contained both answers.** `specs/handler-protocol.yaml`
HP-01-002 said handlers MAY return `None` or `HandlerResult`; UCORG-05-002 said
they MUST return `HandlerResult`. The code conformed to the permissive one. This
was not a spec-vs-code gap but a contradiction *inside* the corpus, so the
deliverable had to adjudicate rather than merely implement. Resolved in favour of
MUST, because ADR-0094 gives the return value a consumer.

**A received-side outcome envelope already existed, one layer up.**
`InboxOutcome` carries `processed`/`deferred`/`rejected` and `failure_reason`,
but `_read_inbox_outcome()` assembles it from inbox-BT blackboard keys rather
than from the handler, and `DispatchNode` treats "dispatch did not raise" as
SUCCESS. Confirmed observable in `AnnounceLedgerEntryReceivedUseCase`, which
returns early with a WARNING when `entry is None` and is still reported as
`processed`.

**Two premises in the issue were wrong.**

- It named three stale documents; there were five. The two it missed were
  `notes/use-case-behavior-trees.md` (code samples annotated
  `# UCORG-05-001: must return UseCaseResult subtype`) and
  `docs/reference/glossary.md` (defining all three types as existing).
  `AGENTS.md` separately contradicted them with `execute() -> None`.
- It listed `ActivityDispatcher.dispatch() -> None` as settled and
  not-to-be-touched, citing "ADR-0040 'Out of Scope'". ADR-0040 has no such
  section and never mentions the dispatcher boundary at all; the "separate
  architectural decision" language it was reaching for lived in
  `notes/use-case-protocol.md`. So the boundary was not settled in either
  direction, and since it is the only route from a handler to `InboxOutcome`, the
  decision had to be made. ADR-0094 makes it. Worth noting that the citation
  survived into the first draft of this PR unchecked — a plausible-looking ADR
  citation is exactly as easy to inherit as the stale Validation section below.

## Transferable lessons

**A "0% implemented, documented as done" concern is often two problems, and the
docs are the more active harm.** The gap itself was inert — nothing was broken by
the missing envelope. What was harmful was five documents asserting completed
work, which would lead any agent reading them to assume the types existed.
ADR-0040's Validation section listing a ratchet test file that was never written
is the sharpest form of this: a Validation section is read as evidence, so an
aspirational one is worse than an empty one. ADR-0094 therefore states in its own
Validation section that nothing is implemented yet, and names the issue that will
add the ratchet.

**Before deciding a requirement buys nothing, search the tracker for a
consumer.** The issue's framing — is this ceremony or not? — was answerable only
by finding #2255. The uniformity mandate genuinely was ceremony *in isolation*;
it stopped being ceremony the moment a filed bug needed the return channel. A
requirement with no consumer and a requirement whose consumer is filed elsewhere
look identical from inside the spec.

**When two spec files disagree, the code silently picks one.** HP-01-002 (MAY)
and UCORG-05-002 (MUST) coexisted, and the implementation followed the permissive
one — which is indistinguishable from "not yet migrated." A permissive
requirement in one file can quietly nullify a MUST in another, and nothing in the
corpus lint detects it. Worth grepping sibling spec files for the same subject
before concluding a requirement is simply unimplemented.

**Distinguish acceptance from processing on any async ingress path.** The inbox
returns 202 for "well-formed and addressed to me" before any handler runs, so the
HTTP response can never carry a processing verdict. #2255's "Done when" asked for
exactly that and had to be amended. This is the same conflation #2369 documents
on the trigger side; it is a recurring shape, not a one-off.

**A vocabulary that a producer cannot legitimately emit invites misuse.**
`InboxOutcome` models `deferred`, but `DeferCheckNode` decides deferral *before*
dispatch, so a handler can never produce it. `HandlerDisposition` therefore
carries only `APPLIED`/`SKIPPED`/`REFUSED`, and `DispatchNode` owns the mapping.
Reusing the downstream vocabulary wholesale would have handed handlers a value
with no legitimate use.

## Resolution

**Resolved**: 2026-09-17 — implementation tracked in #3371, #3372, and #3373,
with #2255 unblocked and rescoped to the per-handler verdict determinations.
Also filed #3374 (HP-04's `dispatchable.payload` contract, which no handler uses
— same species of spec residue, unrelated to this work).

Docs PR: <https://github.com/CERTCC/Vultron/pull/3370>.
ADR: `docs/adr/0094-received-side-handler-result.md` (extends ADR-0040).
Specs: `specs/handler-protocol.yaml` HP-01-002/003/004;
`specs/use-case-organization.yaml` UCORG-05-004b, -005, -009, -010, -011.
Notes: `notes/use-case-protocol.md`.
