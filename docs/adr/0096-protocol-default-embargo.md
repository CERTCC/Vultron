---
status: accepted
date: 2026-09-18
deciders: [adh, Claude Opus 5]
consulted: []
informed: []
---

# ADR-0096: A Protocol Default Embargo Replaces the Pre-Case Phase

## Context and Problem Statement

`docs/topics/process_models/model_interactions/rm_em.md` states that the EM
process MAY begin — the initial *propose* transition
$q^{em} \in N \xrightarrow{p} P$ — before the report is sent to a potential
Participant ($q^{rm} \in S$). CONCERN-2215 recorded that no implemented
mechanics exist for this, and planning group G08 (#2836) convened to decide
whether Vultron gets a pre-case protocol phase at all.

Scoping the group found the documented behavior is not merely unimplemented.
It is unrepresentable, for four independent reasons:

| Fact | Where |
|---|---|
| EM is defined as a global **per-case** state machine | `docs/reference/glossary.md` |
| EM state exists only as `CaseStatus.em` (an `EmDimension`) | `vultron/core/models/dimensions.py` |
| `EmbargoEvent.context` is required, and every core construction site sets it to `case_id` | `vultron/core/behaviors/case/nodes/embargo.py`, `triggers/embargo/{propose,revise}.py` |
| `EmbargoLifecycle.propose_embargo(case_id=…)` raises `VultronNotFoundError` when the case does not resolve | `vultron/core/services/embargo_lifecycle.py` |

So `rm_em.md` asserts a transition on a machine instance that cannot exist:
there is no Case for that $N \xrightarrow{p} P$ to occur in. CONCERN-2215's
premise — documented behavior whose implementation lags — is right about the
symptom and wrong about the cause.

That reframes the question. A pre-submission phase is wanted for exactly two
situations, and neither is a state-location problem:

- **(a)** The Receiver has published no default embargo, so a Reporter has no
  idea what terms they will get.
- **(b)** The Receiver's published default is unacceptable to the Reporter.

`docs/topics/process_models/em/defaults.md` already answers **(b)**:
shortest-proposal-wins, with the longer duration registered as a revision, so
whoever wants longer accepts the shorter and negotiates the extension inside it.
The goal of the EM process is to lock in *an* embargo as early as possible.
**(b)** therefore needs no new phase — it needs the Reporter to be able to state
terms, which `specs/embargo-policy.yaml` EP-04-004 records as absent.

**(a)** turned out to be handled already, in code, wrongly:

```python
_DEFAULT_EMBARGO_DAYS = 90

def _preferred_embargo_duration(...) -> timedelta:
    duration = timedelta(days=_DEFAULT_EMBARGO_DAYS)
    policies = list(dl.list_objects(VultronObjectType.EMBARGO_POLICY))
    if not policies:
        return duration
```

An actor with no published `EmbargoPolicy` silently gets a 90-day embargo. Three
sources disagree: `defaults.md` § "No Defaults, No Proposals" says *"no embargo
SHALL exist"*; `notes/embargo-default-semantics.md`'s own decision table says
`EM.NONE` remains; and `em/principles.md` says embargo duration *"SHOULD be
limited to the shortest duration possible"*. Worse, the incentive is inverted: a
Receiver who publishes nothing gets a **longer** embargo than one who publishes a
considered 30 days.

The mechanism was invisible because nothing distinguishes the two meanings of
"default". `_preferred_embargo_duration()` returns its fallback into the same
blackboard key a published policy fills (`default_embargo_duration`), so
downstream no code can tell *"the Receiver published 90 days"* from *"the
Receiver published nothing"*.

## Decision Drivers

- Lock in *an* embargo as early as possible. This is the stated goal of the EM
  process (`em/principles.md`), and every rule here is measured against it.
- The written rules are part of the work. `defaults.md` is guidance this project
  authors; where it and the code disagree, either may be the thing that is wrong.
- Publishing an `EmbargoPolicy` must be the *rewarded* behavior. Any fallback
  generous enough to be comfortable removes the reason to publish.
- One concept, one name. A word that means two things in the same subsystem
  produces exactly the conflation above.
- Do not add a protocol phase to solve a problem a rule can solve. A phase costs
  a state machine, a wire context, a storage shape, and a migration.
- Timers that govern the same interaction must be mutually coherent.

## Considered Options

Whether Vultron gains a pre-case phase:

- **No — a protocol default embargo plus a sender-side proposal** makes the phase
  unnecessary.
- **Yes — generalize EM scope** from per-case to per-negotiation-context, so the
  documented transition becomes literally true.
- **Yes — a bilateral negotiation before the report exists**, recorded in an
  actor-scoped register, seeding the Case on submission.
- **Yes — revive the proto-case (ADR-0015)**: the Reporter creates a Case with
  themselves as sole Participant and transfers ownership on acceptance.
- **No, and change nothing else** — correct `rm_em.md` and stop.

What happens when no policy and no proposal apply:

- **A bounded, configurable protocol default.**
- **Honor `defaults.md` as written** — no embargo at all.
- **Ratify the existing 90 days** and fix only the documentation.

How a Reporter states terms with a Report:

- **Embed a proposed `EmbargoEvent`** on `Offer(VulnerabilityReport)`.
- **An activity-level `end_time`** on the `Offer`.
- **Inline the Reporter's own `EmbargoPolicy`.**

## Decision Outcome

Chosen: **no pre-case protocol phase.** A bounded protocol default embargo
removes situation (a), and a sender-side proposal embedded on the report Offer
removes situation (b). With both, a Reporter never faces "no embargo at all" and
can always state the terms they want before disclosing anything — which is
precisely the assurance `rm_em.md` offers as its motivation. The phase becomes a
no-op.

### Two kinds of default, named apart

| Term | What it is | Competes under shortest-wins |
|---|---|---|
| **Actor default** | A duration from a published `EmbargoPolicy`; what `defaults.md` calls a *standing proposal* | **Yes** |
| **Protocol default** | The fallback applied when no proposal and no actor default applies | **No** |

The protocol default is **the value when the candidate set is empty, never a
member of the candidate set.** This is load-bearing. A 72-hour protocol default
that competed under shortest-wins would win against every longer proposal and cap
every embargo in the system at 72 hours; no longer embargo could ever be agreed.

Code must stop conflating them. `_DEFAULT_EMBARGO_DAYS` and the blackboard key
`default_embargo_duration` currently carry both meanings.

### The protocol default is configurable within a fixed range

The protocol default embargo duration MUST be configurable, and MUST be no less
than 72 hours and no more than 5 days. Deployments tune it; none may quietly
restore a value generous enough to re-invert the incentive.

The 72-hour floor is not arbitrary — it equals the minimum RSVP window already
established by EP-07-002. Aligning them means the shortest embargo the protocol
will ever produce is exactly as long as the shortest answer window it will ever
grant, so the two numbers need no relationship maintained between them.

This overturns `defaults.md` § "No Defaults, No Proposals". That section's rule
— no defaults and no proposals means no embargo — optimizes for formal tidiness
at the cost of the process goal. A Case with no embargo is the outcome the EM
process exists to avoid, and reaching it by *silence from both parties* is the
least deliberate way to arrive there.

### Every eligible Case is created with an Active embargo

A Case is created with an Active embargo unless the vulnerability is already
public. `EMB-01-002` already forbids proposing an embargo once any of P/X/A is
set, enforced by `_assert_pxa_embargo_eligible()`; the protocol default inherits
that guard rather than bypassing it. An embargo on an already-public
vulnerability protects nothing.

`EM.NONE` remains reachable for a live Case via `PROPOSED → NONE` on reject
(`vultron/core/states/em.py`), so no state is orphaned by this.

### The protocol default is a fallback, not a minimum

A stated proposal wins however short it is. A Reporter may propose 12 hours and
get 12 hours. The range in the previous section bounds what the *fallback* may be
configured to; it does not constrain what parties may agree. Constraining agreed
terms upward would contradict *"shortest duration possible"* and a Participant's
freedom to set their own terms.

### An RSVP deadline may not outlive its embargo

An RSVP deadline MUST NOT fall after the end of the embargo it concerns. Where a
computed deadline would, it is clamped **down** to the embargo's end.

This is a defect independent of everything else above. Nothing today compares
`Invite.end_time` (or the CM-18-002 policy window) against the embargo's own
`end_time`, and EP-07-003 clamps the deadline *up* to a 72-hour minimum with no
upper bound at all. So:

> A new Participant is invited to a 24-hour embargo. The `Invite(EmbargoEvent)`
> carries no `end_time`, so the CM-18-002 policy window applies: 7 days. The
> Pocket Veto fires on day 7. The embargo ended at hour 24.

The Participant is asked to consent to an embargo that is already over, and their
inaction is recorded as a decline six days after it stopped mattering. The same
thing happens on day 28 of a 30-day embargo, entirely without a protocol default
in the picture.

Consequently EP-07-002's minimum becomes **72 hours, or the remaining embargo,
whichever is shorter.** An invitee to a 12-hour embargo gets a 12-hour window.
That is principled: the minimum exists to prevent an unreasonably short deadline,
and 12 hours is not unreasonable when 12 hours is the whole embargo.

### A Reporter states terms by embedding a proposed `EmbargoEvent`

`Offer(VulnerabilityReport)` carries a proposed `EmbargoEvent`. Its factory
already forwards arbitrary AS2 fields, and its own docstring describes it as *"the
RS message when no case exists"* — it is the right activity to carry pre-case
terms.

This requires widening `EmbargoEvent.context` from *always a Case* to **the thing
the embargo is about**: the Report before a Case exists, the Case afterwards. At
Case creation the context is rewritten to the Case id. The widening is a semantic
change, not a type change — `context` is a `NonEmptyString` and is only ever
*cast* to a Case (`vultron/core/models/events/embargo.py`), never validated as
one. `CreateEmbargoEventPattern`'s `context_=VULNERABILITY_CASE` constraint
widens correspondingly.

This discharges EP-04-004's contingency and makes EP-04-003 — shortest-wins at
Case creation — reachable for the first time.

It also settles CONCERN-2215's remaining questions as a side effect. Pre-case
embargo terms now have a legitimate home, and the migration path into the Case is
a context rewrite. So if a genuine pre-submission negotiation is ever wanted, the
object it would negotiate over already exists; what this decision declines is the
*phase*, not the *representation*.

### Consequences

- Good, because the process goal is served directly: an eligible Case always
  begins with an Active embargo, which is what the EM process exists to produce.
- Good, because publishing an `EmbargoPolicy` becomes strictly better than not
  publishing one, reversing the current incentive.
- Good, because it is subtractive at the protocol level — no new state machine,
  no new wire context type, no new storage shape, no migration.
- Good, because it removes a silent 90-day behavior that three documents deny.
- Good, because the RSVP defect is fixed on its merits, not as a side effect.
- Bad / accepted cost: `defaults.md` § "No Defaults, No Proposals" is overturned,
  and the formal statement that no embargo exists in that case no longer holds.
- Bad / accepted cost: a deployment that wants long default embargoes cannot get
  them from the protocol default. It must publish an `EmbargoPolicy`, which is
  the intended pressure.
- Bad / accepted cost: `EmbargoEvent.context` becomes polymorphic in what it
  points at, so readers must not assume a Case without checking.
- Neutral, because `rm_em.md`'s motivation survives intact; only its mechanism
  claim is withdrawn.

## Validation

- A test enumerates the default-resolution table: for each combination of
  (Reporter proposal present/absent) × (actor default present/absent) × (P/X/A
  set/clear), the resulting EM state and duration are pinned. The
  no-policy-no-proposal row asserts the configured protocol default, not 90 days.
- A test asserts the protocol default cannot be configured outside
  [72 hours, 5 days].
- A test asserts the protocol default does not participate in shortest-wins: a
  30-day actor default with no Reporter proposal yields 30 days, not the protocol
  default.
- A test asserts a Reporter proposal shorter than the protocol default is honored
  rather than clamped.
- A test asserts an RSVP deadline computed beyond the embargo's `end_time` is
  clamped down to it, including the case where the remaining embargo is shorter
  than 72 hours.
- A test asserts a Case created with P/X/A set receives no protocol default
  embargo.

## Pros and Cons of the Options

### No pre-case phase — protocol default plus sender proposal (chosen)

- Good, because it removes both motivating situations rather than building
  machinery to navigate them.
- Good, because both halves are small and independently useful; the protocol
  default fixes a live defect and the sender proposal discharges a spec
  contingency that has been open since EP-04 was written.
- Good, because no new concept enters the protocol.
- Bad, because it requires overturning a `SHALL` in `defaults.md`.

### Generalise EM scope beyond the Case

- Good, because it is the only option that makes `rm_em.md` literally true as
  written.
- Bad, because the blast radius is the whole EM subsystem: `EmbargoEvent.context`
  becomes polymorphic *and* EM state must move off `CaseStatus`, the wire pattern
  must admit a non-Case context, and the formal model documentation and glossary
  definition of EM both change.
- Bad, because it buys a capability to serve a need that a rule change removes.

### Bilateral negotiation before the Report exists

- Good, because it matches CONCERN-2215's words most literally — the Reporter
  obtains a commitment, not merely information.
- Good, because ADR-0080's ask primitive and outstanding-ask register would host
  the round-trip without new framework machinery.
- Bad, because it needs a terms object, a register instance, and a Case-seeding
  path, all to reach an outcome shortest-wins already reaches once the Reporter
  can state terms.
- Bad, because a negotiation with no deadline and no Case is the longest possible
  path to the process goal of locking in an embargo early.

### Revive the proto-case (ADR-0015)

- Good, because `notes/embargo-default-semantics.md` § "Known Gap" already
  proposes it, and it reuses existing machinery.
- Bad, because ADR-0041 supersedes ADR-0015 for precisely this window, and
  ADR-0089 re-rejected it when deciding where pre-case RM state lives.
- Bad, because it makes every prospective report a real Case, including the ones
  that are never submitted.

### Honor `defaults.md` as written — no embargo at all

- Good, because the written rule stands unchanged and the 90-day fallback becomes
  a straightforward defect to delete.
- Bad, because it preserves the one outcome the EM process exists to avoid, and
  reaches it through mutual silence.
- Bad, because it leaves a live reason for a pre-submission phase, so the question
  this decision closes would reopen.

### Ratify the existing 90 days

- Good, because no behavior changes and the fix is a documentation edit.
- Bad, because the incentive stays inverted — publishing nothing still yields the
  longest embargo available.
- Bad, because 90 days sits at the far end of *"a few days to a few months"* as an
  *unchosen* value.

### An activity-level `end_time` on the Offer

- Good, because it mirrors ADR-0065's `Invite.end_time` precedent and needs no
  new object and no context change.
- Bad, because CM-28-001 already names `end_time` a critical naming hazard for
  meaning two different things one nesting level apart. A third meaning on a
  third activity type makes a known trap worse.

### Inline the Reporter's own `EmbargoPolicy`

- Good, because `EmbargoPolicy` is already actor-level, so no context question
  arises.
- Bad, because a policy states a standing preference, not terms for this Report —
  *"I generally prefer 30 days"* is not *"for this Report I propose 30 days"*.
- Bad, because it duplicates what dereferencing the Reporter's profile would give
  (#3258), rather than expressing a per-Report decision.

## More Information

Source: planning group G08 (#2836), resolving CONCERN-2215 and IDEA-2075. Two
members were ejected from the group as belonging to a different question: #1189
(ActivityPub/WebFinger directory service) and #2060 (recipe x03, Reporter cannot
find a Vendor contact). Both are **party discovery** — how to address a party at
all — not embargo state location. Their prerequisites are the actor identity
model (G13, #2841, whose own acceptance criteria already name public-key
discovery) rather than anything decided here.

Four defects surfaced while scoping and are fixed or recorded here:

1. The silent 90-day fallback, contradicting `defaults.md`,
   `notes/embargo-default-semantics.md` and `em/principles.md`, and inverting the
   incentive to publish a policy.
2. `_preferred_embargo_duration()` selects `policies[0]` from an unordered list,
   so which policy applies is arbitrary when an actor's store holds more than one.
3. An RSVP deadline may outlive the embargo it concerns — unguarded, and a gap in
   ADR-0065 as it stands.
4. `rm_em.md` asserts an EM transition on a machine instance that cannot exist.

Related decisions: ADR-0065 (RSVP deadline and pocket veto as one mechanism),
ADR-0041 (CASE_MANAGER-authoritative case initialisation, superseding ADR-0015),
ADR-0089 (pre-case RM state belongs to `ReportCaseLink`), ADR-0048 and ADR-0091
(embargo consent states), ADR-0090 (stub objects narrowed to `VulnerabilityCase`),
ADR-0080 (protocol asks).

Generated spec requirements: `specs/embargo-policy.yaml` EP-04-001 and EP-04-004
(amended), EP-04-005 through EP-04-010 (new), EP-07-002 and EP-07-003 (amended);
`specs/case-management.yaml` CM-28-011 (new); `specs/vultron-as2-mapping.yaml`
VAM-05-001 (amended). Design notes: `notes/embargo-default-semantics.md`.
