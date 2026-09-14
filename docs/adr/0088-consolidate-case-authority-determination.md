---
status: proposed
date: 2026-09-14
deciders: Allen D. Householder
consulted:
informed:
---

# Authority Is the CASE_MANAGER Role; "Case Actor" Is Role-Enactment Shorthand, Not an Identity

## Context and Problem Statement

On nearly every case-scoped message, Vultron code must answer one question: is
the executing actor the case's **single-writer authority** — the actor enacting
the `CASE_MANAGER` role — or an ordinary participant whose replica only mirrors
what the authority commits? The authority commits a `CaseLedgerEntry` and
broadcasts; the participant asserts and waits for the broadcast.

The distinction is correct and load-bearing. The problem is twofold.

**First, the question is answered in many places, in different ways.** There is
no single shared way to determine authority, so the check is re-derived per site
and the project backstops the discipline with ratchet tests (CLP-09-002,
CLP-09-003) that only fire when a site *forgets* to check — the signature of a
convention, not a structural guarantee (`notes/case-ledger-authority.md`,
"Authorization Was a Convention, Not a Gate").

**Second — and this is the deeper error — some of those ways determine
authority from the wrong thing.** They key off *where a thing is hosted* or *the
shape of a URL* rather than off the role. "Case Actor" is a **placeholder name**
— the readable label a demo gives to whichever actor is enacting `CASE_MANAGER`,
exactly like "vendor" or "finder". Nobody adopts a "Case Actor" identity. The
identity is defined entirely by *"the entity enacting `CASE_MANAGER` must do
these things."* Treating the name or URL as a protocol signal elevates a demo
convention to protocol truth.

This ADR settles one decision: **authority, recognition, and routing key off the
`CASE_MANAGER` role, and nothing else.** The scope is authority *determination*.
The per-CVD-role *procedures* (Vendor vs. Coordinator vs. Reporter) legitimately
differ and stay in their own use cases and subtrees; consolidating those would
recreate a god dispatcher and is out of scope.

### What is duplicated, and how it answers the question (verified)

Four resolvers answer variants of "is this actor the case authority", three of
them by the wrong signal:

- **Role membership (correct).** `_resolve_case_manager_id` /
  `resolve_case_manager_id` read `CaseParticipant.case_roles`. This is the twin
  to keep — but it *is* a twin: one copy in `use_cases/_helpers.py`, one in
  `behaviors/case/nodes/participant/roles.py`, the second existing "to avoid a
  behaviors→use_cases import (BTND-04-003)". Yet `CheckIsCaseManagerNode`
  (a behaviors node, `case/nodes/conditions.py:45`) performs exactly that import,
  and `use_cases/_helpers._case_actor_by_role` reaches back into behaviors for
  `is_case_actor_identity`. The twin dodges an import two nodes make anyway.
- **Service-hosting (wrong signal).** `_find_case_actor`
  (`sync/nodes/conditions.py`) scans for a `Service` object with
  `context == case_id` attributed to the executing actor. Used by
  `CheckIsOwnCaseActorNode` to pick the CaseActor arm of the replication router.
- **URL shape (wrong signal).** `is_case_actor_identity`
  (`case/case_actor_identity.py`) tests whether an id ends in
  `/actors/case-actor`. Used to decide whether a role-holder "is really a
  CaseActor".
- **Multi-path address lookup.** `_find_case_actor_id` combines ReportCaseLink
  bootstrap paths, the role, the URL-shape gate, and a `Service` scan. This one
  answers a *different* question — "what address do I route to?" — not "am I the
  authority."

**The hosting/shape signals are not merely duplicative; they are fragile.**
`_find_case_actor_id`'s own docstring records a bootstrap window in which the
`Service` object has no `context` yet. In that window the real CaseActor **fails
its own hosting test** and would take the *participant* arm on its own ledger.
Role membership is stable from replica-seed onward and has no such window.

### Authority is not the same question as "which store may append"

`DeclineForeignLedgerCommitNode` (`sync/nodes/ledger_authority.py`) /
`store_for_actor` (`store_scope.py`) look like a third authority check but are
not one. They are a downstream **anti-fork**
guard: once role-authority says "you may commit," they stop a delegated-emit
fall-through from minting a canonical index in a store that is not the log's
home (which would fork the hash chain, #2626). Authority (role) and "where the
write may land" (store) are different jobs; conflating them was a mistake in an
earlier draft of this ADR.

### The one genuine two-arm site

A full "authority does X / participant does Y, both non-trivial" split exists in
exactly one place: `AnnounceLogEntryReceivedBT` (`sync/announce_tree.py`), where
the authority confirms its own broadcast and the participant validates the hash
chain and applies the entry to its replica. A scan of the other received trees
found only *authorization gates* ("role-holder acts, everyone else skips" —
`reject_tree`, `update_tree`, the status commit/adoption/teardown gates) and
participant-side effects that already live inside the announce arm. Those gates
are already served by the sanctioned `create_case_manager_gated_tree`
(BTND-07-005).

## Decision Drivers

- **DRY / no parallel duplicate implementations.** Determining authority must
  have one implementation, composed at every site.
- **Correct signal.** Authority must derive from the role, never from a hosting
  location or a URL name — both are incidental and one is provably fragile.
- **Composability without over-abstraction.** Reuse the pieces that exist; do not
  invent a router for a single caller.
- **Discoverability.** One module and one glossary entry should answer "how does
  an actor know it is the case authority."
- **Respect the layering.** No `behaviors → use_cases` import (BTND-04-003);
  remove the ones that already leak.

## Considered Options

1. **Status quo** — twin role resolvers, hosting/shape checks, ratchet tests.
2. **Role is the sole authority signal; "Case Actor" is role-enactment
   shorthand** — one neutral role resolver, one role-based predicate, retire the
   hosting and URL-shape signals from all protocol logic, fold address resolution
   into "the role-holder's address", fix the one two-arm site in place.
   *(chosen)*
3. **Consolidate resolvers but keep hosting/shape as legitimate signals** — dedupe
   the plumbing without changing what authority is determined *from*.
4. **Build a reusable authority/participant router** across received trees.

## Decision Outcome

Chosen: **"Role is the sole authority signal; 'Case Actor' is role-enactment
shorthand."** It removes the duplication *and* the wrong/fragile signals, keeps
the pieces composable, and matches the actual protocol meaning: authority is
whoever enacts `CASE_MANAGER`.

Concretely:

1. **One role resolver, in a neutral layer.** A single home (e.g.
   `vultron/core/participants/authority.py`) below both `behaviors/` and
   `use_cases/`, depending only on `models`, `ports`, and `enums`. It answers
   "which actor enacts `CASE_MANAGER` on this case?" by reading
   `CaseParticipant.case_roles`. Both current twins are deleted and delegate to
   it. It needs no `behaviors` import, because the URL-shape concern that forced
   the old cross-layer reach is being removed.
2. **One role-based authority predicate.** `CheckIsCaseManagerNode` and
   `CheckIsOwnCaseActorNode` / `CheckIsNotOwnCaseActorNode` collapse into one
   condition node (plus a negation decorator) that calls the single resolver.
3. **Retire the wrong signals from protocol logic.** `is_case_actor_identity`
   and the `Service`-hosting resolution (`_find_case_actor`) are removed from
   authority, recognition, and routing. `_find_case_actor` loses its only callers
   when the router goes role-based and is deleted.
4. **Fix the one two-arm site in place; no router abstraction.** The announce
   router's two arms switch to the role predicate. This also fixes the
   bootstrap-window latent bug; a regression test covers it. Every other
   received tree keeps `create_case_manager_gated_tree` (the authorization-gate
   shape). No general router is introduced.
5. **Address resolution folds in.** The authority's address is simply the
   role-holder's address. `_find_case_actor_id` keeps whatever bootstrap paths it
   genuinely needs for *delivery*, but drops the URL-shape gate as an
   authority/recognition test; it is documented as an address lookup, a
   different concern from authority.
6. **The store guard is reclassified, not removed.** `DeclineForeignLedgerCommit`
   `Node` / `store_for_actor` stay exactly as they are, relabeled as
   store-consistency / anti-fork — explicitly not authority. There is no
   role/store "coincidence" to assert: authority is purely the role.
7. **"Case Actor" name/URL becomes cosmetic.** A spawned software actor may still
   be provisioned at a stable inbox URL (ADR-0041's fix for the unhostable
   per-case slug stands) — but the string `case-actor` carries no protocol
   meaning and no code may branch on it.

### Consequences

- Good: one implementation of authority, composed everywhere; the twins and the
  leaking cross-layer imports are gone.
- Good: the fragile hosting/shape signals are gone, including the bootstrap
  window where a CaseActor failed to recognize its own ledger.
- Good: one module plus one glossary entry answer "what is the authority."
- Good: no god object and no one-user router — resolver, predicate, gate, and the
  single two-arm site stay separate and composable.
- Bad / cost: a migration touching the resolver twins, the condition-node pair,
  and every reader of `is_case_actor_identity`, guarded by the existing ratchets.
- Neutral: the CVD-role *procedure* dispersion is untouched by design.

## Validation

- A ratchet test asserting exactly one role-authority resolver module, imported
  by both `behaviors/` and `use_cases/` (no twin definition, no
  `behaviors → use_cases._helpers` role-resolution import).
- A test asserting one authority condition node is the only thing resolving "am I
  the authority"; `CheckIsOwnCaseActorNode` / `CheckIsNotOwnCaseActorNode` are
  removed or aliased.
- A ratchet asserting no protocol-logic module branches on
  `is_case_actor_identity` or on the `case-actor` URL substring.
- A regression test for the bootstrap window: the actor enacting `CASE_MANAGER`
  takes the authority arm on its own ledger entry even before any `Service`
  object carries `context`.
- The existing CLP-09 commit-coverage ratchets keep passing throughout.

## Pros and Cons of the Options

### Status quo

- Good, because the ratchets catch the most dangerous omission (unguarded commit).
- Bad, because authority is determined four ways, three of them by the wrong
  signal, one of them fragile in a real bootstrap window.

### Role is the sole authority signal (chosen)

- Good, because it fixes the concept (role, not name/host) and the duplication at
  once, and removes a latent bug.
- Good, because the neutral resolver becomes import-clean once the URL-shape
  concern leaves authority.
- Neutral, because it adds one module and one glossary edit but deletes more.
- Bad, because it is a cross-cutting migration and touches ADR-0041's identity
  narrative.

### Consolidate resolvers but keep hosting/shape signals

- Good, because it is a smaller change.
- Bad, because it preserves the wrong signal and the bootstrap-window fragility;
  it dedupes the plumbing while leaving the concept wrong.

### Reusable authority/participant router

- Good, because every received tree would look identical.
- Bad, because a scan found exactly one genuine two-arm site; the abstraction
  would have a single user, and authorization gates are already unified.

## More Information

Relationship to prior decisions: this **refines ADR-0041 / #1872**. That work
gave the enacting actor a *stable* inbox URL, fixing the unhostable per-case slug
that 404'd; that fix stands. This ADR narrows the earlier identity narrative:
the stable URL is a provisioning convenience, and no protocol logic may treat the
`case-actor` name or URL shape as evidence of authority — the role is the sole
signal. Related: ADR-0021 (CaseActor inbox routing to canonical entries),
ADR-0073 (per-actor storage — origin of the store-consistency guard this ADR
reclassifies). Sibling consolidation: **ADR-0087** applies the same
"one shared implementation, chosen by role, never re-decided per call site"
pattern to a *different* question (a BT node's disposition when a case is
*absent*); this ADR is the analogous consolidation for *who is the authority*
when the case is present. Related notes: `notes/case-communication-model.md`,
`notes/case-ledger-authority.md`.

A companion glossary change redefines "Case Actor" as shorthand for
`CASE_MANAGER`-role enactment (typically an automated software actor), with
authority defined by the role, not by name or identity.

On acceptance this generates recurring testable requirements — the
single-resolver / single-predicate invariants, the no-name-branching ratchet, and
the bootstrap-window regression — to be authored in `specs/architecture.yaml` and
`specs/case-management.yaml` (IDs assigned at authoring time per
`notes/spec-authoring-rules.md`). Re-visit if per-actor storage authority
(ADR-0073) or the `CASE_MANAGER` role model changes.
