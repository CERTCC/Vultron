---
status: accepted-provisional
date: 2026-10-22
created: 2026-10-22
updated: 2026-10-28
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0041, ADR-0107, ADR-0124; specs/case-ledger-processing.yaml
  CLP-02-013, CLP-07-011, CLP-07-013; issues #5122, #5052
informed: []
stakeholder_type: [project-contributor]
---

# A Case's Creation Is One `Create`, Delivered and Ledgered

## Context and Problem Statement

When the CASE_MANAGER creates a case, it sends the case's first participant a bootstrap `Create(VulnerabilityCase)` carrying the case with its participants, reports and active embargo inline.
It also committed a genesis `create_case` entry, but that entry's snapshot was a second `Create`, with its own id, built for the ledger and carrying the case's records by id.
The second `Create` was sealed but never delivered, and the one delivered was never ledgered.

CLP-07-011 says the snapshot of an activity the CASE_MANAGER emits is the body it delivered, and CLP-02-013 says an activity only the CASE_MANAGER sends is ledgered where it sends it.
Two activities for one act break both: a participant's copy of the case's creation is not the one its ledger records (#5122).

Which activity is the case's creation?

## Decision Drivers

- One act is one activity: the body a participant receives is the body the ledger records (CLP-07-011).
- A participant seeding its replica must be able to read every record the case names (EMB-18-003, CBT-01-012).
- Each record the creation writes is still carried in full by an entry of its own (CLP-07-013).

## Considered Options

- Ledger the bootstrap `Create`
- Deliver the genesis entry's `Create`

## Decision Outcome

Chosen option: "Ledger the bootstrap `Create`", because it is the only option that keeps one activity without changing how a participant seeds its replica.

The creation builds and queues one `Create(VulnerabilityCase)`, its id derived as before, and commits that same sealed body as the genesis entry.
Each record it carries inline also follows as its own entry (`create_embargo_event`, `add_report_to_case`, `create_case_participant` and the status entries), so a replica that builds the case from the ledger alone copies each record from its own entry.
A proposal that resolves to a case already created sends no `Create` and commits no second genesis entry.

### Consequences

- Good, because a participant's bootstrap and its ledger's genesis entry are one activity, so its hash covers what the participant was sent.
- Good, because the CASE_MANAGER stores one `Create` per case (CP-09-009) and seals no extra record.
- Neutral, because the genesis entry now carries the case's records inline as well as their own entries; a replica seeded from it treats those entries as already in place, as it does after any full-case copy (#5052).

## Validation

Tests on both creation paths assert the queued `Create` body equals the genesis entry's snapshot, and a test seeds a proposer's replica from that snapshot and compares it with the CASE_MANAGER's case file.

## Pros and Cons of the Options

### Ledger the bootstrap `Create`

- Good, because the proposer seeds exactly as before.
- Bad, because the genesis snapshot repeats records later entries carry.

### Deliver the genesis entry's `Create`

- Good, because the genesis snapshot stays a case naming its records by id.
- Bad, because the proposer would receive a case naming an embargo, participants and reports it cannot read, which EMB-18-003 makes it refuse.
- Bad, because the report receiver could not introduce the CASE_MANAGER to the reporter until later entries arrived (CBT-01-001).

## More Information

Generated spec requirements: CLP-07-011 and CLP-02-013 state the rule.
