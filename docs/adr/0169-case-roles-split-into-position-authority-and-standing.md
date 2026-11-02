---
status: proposed
date: 2026-11-02
created: 2026-11-02
updated: 2026-11-02
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5; ADR-0057, ADR-0078, ADR-0088, ADR-0121, ADR-0133;
  specs/case-management.yaml CM-16-003, CM-25-001, CM-26-001, CM-31-004,
  CM-33-003; specs/case-proposal.yaml CP-01-013;
  specs/configuration.yaml CFG-07-002
informed: []
partially_supersedes: 0133-the-report-receiver-states-its-case-roles-on-the-case-proposal.md
stakeholder_type: [project-contributor]
lint_suppress: [phantom_symbol_ref]
---

# Case Roles Split Three Ways — Position, Case Authority and Actor Standing — and Every Participant Claims a Position

## Context and Problem Statement

`CVDRole` holds eight values that are three different kinds of thing.

Five name a **position** a participant holds in one case: Reporter, Vendor, Deployer, Coordinator, Observer.
A position is assigned by an act in that case, and the same actor holds a different one on another case.
Two name **authority** over the case: Case Owner and Case Manager.
Authority is conferred by case creation and by ownership transfer, and is never offered or removed the way a position is.
One, CVE Numbering Authority, names a **standing** of the organization that is true across every case; `IsIDAssignmentAuthority` calls it "a static property of the organization's metadata".

Because all eight share one enum and one list field on `CaseParticipant`, a participant record can hold authority and no position at all, and nothing refuses it.
Two doors do exactly that today.
A report receiver whose `ActorConfig.default_case_roles` is empty proposes a case stating an empty claim, which ADR-0133 recorded as acceptable: "a proposal without the field seats the receiver as `CASE_OWNER` only".
`CreateCaseParticipantNode` hard-codes `[CVDRole.CASE_OWNER, CVDRole.CASE_MANAGER]` and names no position.
In both cases the owner holds no position, and the refusal surfaces far from the cause, wherever a position is later required — a Coordinator that cannot invite, a Vendor that cannot report a fix ready.

Two run-time guards exist only to patch the same conflation.
`RoleOfferAdmissibleNode` refuses a role Offer that names Case Owner or Case Manager, and `PROTECTED_ROLES` stops a participant removal from stripping them.
Both encode in a check what one enum makes expressible in the first place.

How should the three kinds of role be modeled, and where does a participant's position come from?

## Decision Drivers

- A position is case-scoped, so no actor-level setting can be its authority: the same actor is a Reporter on one case and a Vendor on another.
- A participant with no position has no place in the protocol, because every permission and obligation attaches to a position (CM-26-001) and Observer exists as the floor (CM-25-001).
- An actor's standing is not a case fact, so a copy of it on a participant record would be a stale copy of something the actor owns (AKM-05-005).
- A constraint the type system can carry should not be a rule a reader has to remember.
- The word *capability* is already taken twice — by the conformance capability sets and by the behavior-tree call-out shapes — and both are deliberately kept clear of role names (ADR-0088).

## Considered Options

- Three enums split by scope, and a mandatory position claim
- One enum with named subsets, and a non-empty-position rule
- One enum, and refuse only an empty claim at the two creation doors

## Decision Outcome

Chosen option: "Three enums split by scope, and a mandatory position claim", because it is the only option that makes the defect unrepresentable rather than merely forbidden, and the scope of each kind of role is what justifies the boundary.

`CVDRole` keeps the five case-scoped positions.
A second enum holds the two case-scoped authority values, and `CaseParticipant` carries them in a field of their own, separate from its position list.
A third enum holds actor-scoped standing, with CVE Numbering Authority as its first member; standing lives on the actor and is never copied onto a participant record.

Every `CaseParticipant` holds at least one position, enforced at construction.
Both doors that create a participant claim one.
The report receiver's proposal carries a claim supplied by its caller, which reads the value from `ActorConfig.default_case_roles`; the node that builds the proposal no longer reads the configuration itself, and a claim naming no position refuses the proposal.
Direct case creation takes the creator's position the same way instead of naming only authority.

The configuration field is therefore a **hint** — the value a caller reads when it has nothing more specific to claim — and not the authority for what the participant holds.
That is the invariant this record fixes: a participant's roles come from an act in the case, and an actor-level setting only supplies a default for the act to carry.

### Consequences

- Good, because a participant that holds authority and no position cannot be constructed, so the late and misattributed role refusal cannot happen.
- Good, because two run-time guards lose their reason to exist: a role Offer is typed to positions, so it cannot name authority, and a removal that edits positions cannot reach the authority field.
- Good, because an actor's standing stops masquerading as a case role, which is what let "holds a position" be satisfied by something that is not one.
- Bad, because the participant's stored shape and wire form both change, and every reference to the two authority values moves to the new type — about fifty files under `vultron/` and a hundred and sixty under `test/`.
- Bad, because an actor configured with no default position can no longer propose a case; it is refused at the proposal rather than seated without a position.
- Neutral, because the Exploit Publisher the protocol specification already constrains gains an obvious home in the standing enum, but is not modeled here.

## Validation

A participant constructed with authority and no position raises.
A case proposal whose claim names no position is refused at the parse edge, and the node that builds a proposal reads no configuration.
Direct case creation seats its creator with a position.
An architecture test confirms every value of the three enums sits in exactly one of them.

## Pros and Cons of the Options

### Three enums split by scope, and a mandatory position claim

- Good, because each enum's membership is decided by a question with one answer: is this fact about a case, about authority over a case, or about the organization?
- Good, because the invariant reduces to "the position list is non-empty", with no subset of a larger enum to declare and keep honest.
- Bad, because it is a large mechanical migration and a stored-shape change.

### One enum with named subsets, and a non-empty-position rule

- Good, because no call site moves and neither the stored shape nor the wire form changes.
- Neutral, because it states the taxonomy, which is most of the value.
- Bad, because the subsets are a rule beside the type rather than the type, so a role Offer can still name authority and a removal can still reach it; both guards stay.
- Bad, because the two places that already hard-code the authority pair under their own names would cite the subset without the type stopping anything.

### One enum, and refuse only an empty claim at the two creation doors

- Good, because it is the smallest change that closes the observed hole.
- Bad, because it leaves "holds a position" satisfiable by the CVE Numbering Authority value, which names no position.
- Bad, because it treats a modeling problem as two input checks, so the next door added repeats the defect.

## More Information

Source: #5586, which reported the symptom — a demo decision point whose deciding actor held no position — and whose premise this record overturns.
The symptom's apparent cause, a container-level role setting, is read in exactly one place: the proposal a report receiver sends.

Revisit when the Exploit Publisher is modeled, which is the standing enum's expected second member.

The implementing change adds the role-taxonomy and position-claim requirements to `specs/participant-role-management.yaml`, each with its marker test, and revises the requirement in `specs/case-proposal.yaml` that currently makes the actor configuration authoritative for a proposal's roles.
Those requirements are not written ahead of the code, because a rule an implementer must obey needs a test in the same change.
