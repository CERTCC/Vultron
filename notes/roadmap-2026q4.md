---
title: Roadmap 2026Q4 — Year Goal and This Quarter's Objectives
status: active
kind: plan
tracks:
  - "#1156"
  - "#5911"
  - "#6100"
  - "#6440"
  - "#5954"
  - "#6350"
  - "#6367"
  - "#5676"
  - "#5677"
  - "#5624"
  - "#5912"
  - "#5354"
  - "#5226"
  - "#5674"
  - "#5913"
  - "#5068"
  - "#5931"
  - "#5396"
  - "#5829"
  - "#5830"
  - "#5683"
  - "#2619"
  - "#3794"
description: >
  The year goal (Vultron piloted on CERT/CC's own case work and available for
  others to try) and the 2026Q4 objectives with their finish lines: Interconnect,
  Self-serve start, Spec Draft 1 and Measuring CVD, plus the Health budget. Each
  objective is a `2026Q4 · <name>` milestone; which Epics serve it are listed
  here, and their order is the Now tier's position on Project #24.
related_notes:
  - notes/planning-rules.md
---

# Roadmap 2026Q4 — Year Goal and This Quarter's Objectives

How these objectives become milestones and how the next Focus Epic is chosen:
`notes/planning-rules.md`. **The order of work is the Now tier's position on
Project #24**, not this note.

## Year Goal (through about 2027Q3)

The Vultron reference implementation has been **piloted on CERT/CC's own case
work** and is **available for others to try**. The protocol specification stands
on its own, so others can implement it.

A direction, not a commitment:

1. Vultron accepts the documents CVD tools already exchange (CSAF) and verifies who
   sent them.
2. The **case shadow** reads a live VINCE case on request and shows Vultron's
   analysis of it, without writing back (`CONTEXT.md` § Outside Systems).
3. The **VINCE gateway** lets VINCE take part in cases as a protocol peer.
4. Beyond the year: an independent second implementation.

Out of scope this year unless the gateway pulls a piece in: high availability, a
distributed ledger, production key handling, end-to-end encryption.

## Objectives (milestones due 2026-12-31)

### Interconnect

Vultron exchanges case data with outside systems. Deliverables, in this order:

1. **A receiver accepts a report with an attached CSAF 2.1 vulnerability report**
   (#5911). The CSAF document is an attachment of the report in
   `Offer(VulnerabilityReport)`, with no new wire activity (ADR-0184). The build
   tasks are #6089 to #6094, and the deliverable waits on the Offer(Report)
   receive tree rewrite (#5045, #5046). A demo scenario shows it end to end
   (#6100), and it waits on #6091 and #6092.
2. **That offer carries a seeded-key proof that is verified** (#1156). A missing
   or failing proof gets 422 with its own error name (#5763), not 401: a proof is
   content, not an HTTP credential.
3. **The case shadow reads a real VINCE case and shows Vultron's analysis.** On
   request it reads one case through a case reader, shows where the case stands
   and ranks the next moves, then keeps nothing (ADR-0190). It is built from both
   sides of the `CaseReader` port at once, so the two meet at the case ledger:
   - The dashboard (#6366) and its port (#6358), under Epic #6440, built first on a
     Vultron case-ledger file (#6441), which leaves nothing untranslated. It shows
     the scored standing and the best moves (#6368, #6369; Epic #6367).
   - The VINCE case reader, under Epic #5954: the translation experiment first
     (#6365), then the mapping (#5964) and the reader (#5963). What VINCE cannot
     map shows as untranslated facts, not as a dashboard change.
   - The read-only and keeps-nothing rules, which hold for any source (Epic #6350).

   The data rules are decided (ADR-0189): a VINCE user runs the shadow with their
   own credential, and development uses the test instance.

The VINCE gateway is 2027. Replay of historical VINCE cases moved to the shadow:
reading live cases through the API covers what a data dump was for.

### Self-serve start

Someone outside the team succeeds alone: the site matches `main`, and a newcomer
gets from clone to a multi-party case using the docs alone.

- Deterministic demo recordings (#5676), scenario drift failing its PR (#5677), and
  the demo UI reading today's ledger (#5624).
- The site accuracy audit and the newcomer run (#5912). The colleague who does the
  run needs booking early: their availability likely sets the finish date.

### Spec Draft 1

The Protocol Specification is a draft a reader can cite:

- it carries a draft label, a version and a revision log (#5913);
- no published statement contradicts `main` (#5354, #5226, #5674);
- the known-gaps page is current when Draft 1 is tagged.

Interconnect's findings go into Draft 2, so Draft 1 does not wait on them. An
outside review of Draft 1 is the first item for 2027Q1.

### Measuring CVD

The ledger-to-event-history translation exists, and the CVD measures run on the
recorded demo ledgers (#5068). VINCE has parallel work on measuring CVD from its
cases: name Vultron's events so they line up with VINCE's, so that the shadow can
later measure one real case both ways and compare.

### Health (budget)

Case authority answered in one place (#5931), order independence (#5396),
`plan/history` cleanup (#5829), size estimates that predict PR size (#5830),
AS2-only fields (#5683), tests that check what they claim (#2619) and a docs site
that follows green `main` (#3794).

Case authority (#5931) edits the received-message trees that #5674 is aligning
with the specs, so it waits for #5674 to close.

Among the Health Epics in Now, #5830 comes first: its recalibrated estimates feed
the staggering rule's "closest to done" judgment. #5683's child #5168 (outbound
`@context`) blocks the signing work in #1156 (#5382), so it lands ahead of its
Epic.
