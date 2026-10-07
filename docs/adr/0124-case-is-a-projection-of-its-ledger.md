---
status: proposed
date: 2026-10-07
created: 2026-10-07
updated: 2026-10-07
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Concern #4284, Issue #4178; ADR-0107, ADR-0111, ADR-0119,
  ADR-0122; specs/case-ledger-processing.yaml CLP-10; specs/sync-ledger-replication.yaml
  SYNC-00-002
informed: []
stakeholder_type: [project-contributor]
---

# The Case Is a Projection of Its Ledger: One Replay Function for the CASE_MANAGER and Every Replica

## Context and Problem Statement

A participant case replica exists so that a participant can learn the current state of a case by reading its own copy, without asking the CASE_MANAGER for a snapshot each time.
The case ledger is how those copies are kept in step with the CASE_MANAGER's case: the CASE_MANAGER commits entries, and replicas replay them; a replica is synchronized when its ledger tail hash matches the CASE_MANAGER's (SYNC-00-002).

Tracing participant embargo consent for Concern #4284 showed that the CASE_MANAGER's case and its replicas are not kept in step by one rule:

- The CASE_MANAGER changes its case in its lifecycle code, and each replica runs a separate replay path that calls into that lifecycle code again against its own copy.
- Several writes have no replay at all. The inert invitee's `INVITED` and `DECLINED` rows, the CASE_MANAGER's own policy-based consent, and the joiner's consent on accepting the full-case Invite are written only on the CASE_MANAGER.
- Some writes depend on things a replica does not have: the CASE_MANAGER's local policy, or the clock at the moment it ran.
- No test compares a case rebuilt from its ledger with the CASE_MANAGER's case.

Each gap leaves replicas silently disagreeing with the CASE_MANAGER, and each new feature has to remember to add its write in two places.

What is the relationship between the case and its ledger, and how does each node change its copy of the case?

## Decision Drivers

- A replica must be a faithful copy: anything a participant could have learned by asking the CASE_MANAGER for the case, it can learn from its replica.
- A ledger entry records an act that has happened (ADR-0119), never an intention.
- One rule, one implementation: a change written in one place cannot be forgotten in another.
- The CASE_MANAGER is the single writer for its case (the single-writer regime), so no two commits conflict.
- Every claim of consistency should be testable by a test, not maintained by care.

## Considered Options

- Keep two paths: the CASE_MANAGER's own write logic, and a separate replica replay path, kept consistent by tests.
- Commit snapshots: each entry carries the changed records in full, and a replica overwrites its copy.
- Commit state changes: each entry carries the state transitions it caused, and a replica applies them.
- Commit the protocol messages, and derive the case by replaying them with one function used by every node.

## Decision Outcome

Chosen option: "Commit the protocol messages, and derive the case by replaying them with one function used by every node", because it is the only option in which the CASE_MANAGER's case and every replica are, by construction, the same function of the same ledger.

### The case is the replay of its ledger

A case and its complete ledger are transformations of each other.
Replaying a case's complete ledger, from empty and in order, MUST yield the case the CASE_MANAGER holds.
A replica whose ledger tail hash matches the CASE_MANAGER's (SYNC-00-002) therefore holds the same case, not only the same ledger.
No node is expected to rebuild a case that way in normal operation; the property is what makes a replica faithful, and a test asserts it.

Ledger entries are the protocol messages themselves: invites, accepts, rejects, proposals, status updates, terminations.
They carry no separate state-change payload.
The state of the case is what replaying them produces.

### One replay function

One function applies one entry to a case and returns the case after it.
The CASE_MANAGER and every replica use it, and it is the only code that changes case state.

The function is pure:

- Its result depends only on the entry and the case before it.
- It reads no clock. Any time it needs comes from the entry, such as its `published` timestamp, or from the case.
- It reads no local policy, configuration or store state outside the case.
- An entry it cannot apply, because a transition is illegal from the current state or an invariant would break, is refused. On a replica that means an earlier entry is missing, which the gap handling resolves (`LedgerGapBuffer`); it is never patched over.

Two kinds of decision are not pure, and both are therefore committed as messages before they change anything:

- **A decision made from local policy**, such as the CASE_MANAGER agreeing to or declining a proposal by its own embargo policy, is committed as the CASE_MANAGER's own protocol message, for example its `Accept` or `Reject`.
- **A decision made from the clock**, such as an invite's RSVP deadline passing or an embargo reaching its end time, is committed as an entry recording that act.

### How the CASE_MANAGER changes its case

The CASE_MANAGER never edits its case directly.
It decides on an act, checks the act's consequence, records the act, and only then derives the new case from the record:

1. **Decide.** Guards read the current case and refuse the act if it is not allowed.
2. **Trial apply.** The replay function applies the entry to a copy of the case, and every invariant is checked. A refusal here stops the act, and nothing is recorded or sent.
3. **Complete the act.** A received message has already arrived (intake, ADR-0111). A message the CASE_MANAGER sends is complete when it is written to its own outbox (ADR-0119).
4. **Commit.** The entry recording the act is committed to the ledger.
5. **Apply.** The replay function applies the entry to the case. Because the function is pure, a successful trial guarantees this step succeeds, and the trial copy may be kept as the result.
6. **Consequent acts.** Messages sent because of this act, and the `Announce(CaseLedgerEntry)` that replicates the entry, follow, each recorded as its own act.

The copy in step 2 changes only by applying the entry.
Editing its fields directly would derive the CASE_MANAGER's case from different code than its replicas use, which is the drift this ADR removes.
What is committed is the message, never the modified copy.

This is a narrowing of the received-side order of ADR-0111 (intake, guards, commit, effects): changes to case state move out of "effects" into the shared replay step, and only outside acts remain effects.
It keeps ADR-0119's order for sent messages: the outbox write completes the act, and the commit follows it.

### A replica

A replica applies each entry it receives, in ledger order, with the same function.
It runs no lifecycle logic of its own and decides nothing about case state.

### Scope

The rule covers all of the case's state: report management, participant records and status, the embargo register and participant embargo consent (ADR-0122), and anything added later.
A domain whose replay does not yet meet it is a defect to fix, not an exception.

### Consequences

- Good, because the CASE_MANAGER's case and every replica are the same function of the same ledger, so they cannot drift.
- Good, because a write cannot be forgotten on one side: there is only one side.
- Good, because "the replica is faithful" becomes a test: replay the ledger into an empty store and compare.
- Good, because a crash between commit and apply loses nothing; replaying the ledger restores the case.
- Good, because a missing entry on a replica surfaces as a refused transition, not as silent disagreement.
- Bad, because every case-state write in today's lifecycle and behavior-tree code must move into the replay function, and every write with no committed cause must gain one.
- Bad, because decisions taken from local policy or the clock must now be committed as messages, which adds entries to the ledger.
- Neutral, because the ledger's meaning does not change: it still records completed acts (ADR-0119), and an entry still names the message as received (ADR-0107).

## Validation

- A rebuild-from-ledger test replays each demo and integration scenario's CASE_MANAGER ledger into an empty store and asserts the result equals the CASE_MANAGER's case, including participant records, consent rows and the embargo register.
- A test asserts the replay function reads no clock and no store outside the case it is given.
- An architecture test asserts that case state is changed only through the replay function.

## Pros and Cons of the Options

### Two paths kept consistent by tests

- Good, because it is the least rework.
- Bad, because it is the arrangement that produced the gaps in Concern #4284: every new write has to be added twice.

### Commit snapshots

- Good, because a replica only overwrites, so applying is trivial.
- Bad, because the ledger stops recording acts: it records results, and loses which transition happened.
- Bad, because a replica that missed an entry overwrites silently instead of noticing the gap.

### Commit state changes

- Good, because a replica can check each change's starting state and notice a gap.
- Bad, because the ledger then records the CASE_MANAGER's conclusions alongside, or instead of, the messages that caused them, so replay trusts the CASE_MANAGER's arithmetic instead of checking it.
- Bad, because the state changes duplicate what the messages already say.

### Commit messages, replay with one function

- Good, because the ledger records exactly the acts of the protocol, and the case follows from them.
- Good, because the CASE_MANAGER and replicas share one implementation.
- Bad, because the replay function must be pure, which forces policy and clock decisions into committed messages.

## More Information

Decided in the maintainer's design session of 2026-10-07, recorded in Concern #4284; implementation is tracked under epic #4283.
ADR-0122 is the first domain designed against this rule.
