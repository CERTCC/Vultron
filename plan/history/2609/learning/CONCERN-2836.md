---
source: CONCERN-2836
timestamp: '2026-09-18T15:47:02.737692+00:00'
title: 'G08: the protocol has no pre-case phase'
type: learning
---

Planning group **G08** of 19 (parent #2828), convened to decide whether Vultron gets a protocol
phase before a Case exists. Members: #2215, #2075, #2060, #1189.

**Resolved**: 2026-09-18 — no pre-case protocol phase. Design recorded in **ADR-0096**;
implementation tracked in #3390, #3391, #3392, #3393.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3389>
Spec: `specs/embargo-policy.yaml` EP-04-005 through EP-04-010, EP-07-006 (new), EP-04-001/004,
EP-07-002/003/005 (amended); `specs/case-management.yaml` CM-28-011 (new), CM-12-004, CM-14-006,
CM-14-010, CM-28-002 (amended); `specs/vultron-protocol-spec.yaml` VP-07-001 (amended);
`specs/vultron-as2-mapping.yaml` VAM-05-001 (amended).
Notes: `notes/embargo-default-semantics.md`.

## The umbrella's premise was half-stale, and its framing was wrong twice

**On state location.** The group was convened on the claim that "there is no protocol phase
before a case exists — every documented pre-case behavior has nowhere to live." That was true
when #2215 was filed and is no longer. `VultronOfferRecord` is durable, DataLayer-backed,
deterministically keyed and works before a case exists; ADR-0089 then moved pre-case RM state
onto `VultronReportCaseLink`, stating outright that "ADR-0041 already owns the pre-case window."

**On the nature of the defect.** #2215 framed this as docs-ahead-of-code. It is not. Four facts
make the documented transition *unrepresentable*, not merely unbuilt: EM is defined per-case
(glossary); EM state exists only as `CaseStatus.em`; `EmbargoEvent.context` is required and was
always `case_id`; and `propose_embargo(case_id=…)` raises when the case does not resolve. So
`rm_em.md`'s `q^em ∈ N → P` while `q^rm ∈ S` named a machine instance that cannot exist.

**On group coherence.** The four members were three different questions. Two were embargo-state
questions; two were **party discovery** questions — how to address a party at all. See the
ejections below.

## What replaced the phase

A pre-submission phase was wanted for two situations: **(a)** the Receiver published no default,
so a Reporter cannot know the terms; **(b)** the published default is unacceptable. Neither is a
state-location problem, and both dissolve:

- **(a) was already handled, wrongly.** `_preferred_embargo_duration()` silently returned a
  hardcoded **90 days** when an actor had no `EmbargoPolicy` — contradicted by `em/defaults.md`
  ("no embargo SHALL exist"), by `notes/embargo-default-semantics.md`'s own decision table, and
  by `em/principles.md` ("shortest duration possible"). It also inverted the incentive the
  protocol depends on: publish nothing, get a *longer* embargo than someone who published a
  considered 30 days. Replaced by a **protocol default** bounded to [72h, 5d].
- **(b) was already answered** by shortest-proposal-wins. It needed only that the Reporter be
  able to state terms — which EP-04-004 recorded as absent, and which is now specified as a
  proposed `EmbargoEvent` embedded on `Offer(VulnerabilityReport)`.

## The distinction that made it work

Two things were both called "a default", and conflating them is what hid the defect for so long:

| Term | What it is | Competes under shortest-wins |
|---|---|---|
| **Actor default** | A duration from a published `EmbargoPolicy`; a *standing proposal* | Yes |
| **Protocol default** | The fallback when no proposal and no actor default applies | **No** |

The "No" is load-bearing and was the sharpest point in the session: a 72-hour protocol default
that competed under shortest-wins would beat every longer proposal and cap **every** embargo in
the system at 72 hours. The protocol default is the value when the candidate set is empty, never
a member of it. It is also not a minimum — a 12-hour proposal yields 12 hours.

`_preferred_embargo_duration()` returned its fallback into the *same blackboard key*
(`default_embargo_duration`) a published policy filled, so no downstream code could tell "the
receiver published 90 days" from "the receiver published nothing". That is the mechanism by which
a behaviour three documents deny survived unnoticed.

## Five defects surfaced

1. The silent 90-day fallback, contradicting three documents and inverting the publish incentive.
2. `_preferred_embargo_duration()` selects `policies[0]` from an unordered `list_objects()`
   result — arbitrary when an actor's store holds more than one `EmbargoPolicy`.
3. **An RSVP deadline can outlive the embargo it concerns.** Unguarded; nothing compares
   `Invite.end_time` or the CM-18-002 policy window against the embargo's `end_time`, and
   EP-07-003 clamps *up* with no ceiling. Invite someone to a 24-hour embargo with no explicit
   `end_time` and the Pocket Veto fires on day 7. Reachable today without any protocol default —
   day 28 of a 30-day embargo does it. Recorded as a gap in ADR-0065 as it stood.
4. `rm_em.md` asserting a transition on a machine that cannot exist.
5. A second undeclared duration: `EmbargoEvent.end_time` defaults to `_45_days_hence`, so any
   `EmbargoEvent` built without an explicit `end_time` silently gets 45 days — nine times the new
   5-day ceiling. Found during PR review, not scoping; EP-04-010 widened to cover it. Impl #3404.

Defect 3 is the one worth remembering: it was found only because aligning the protocol-default
floor with EP-07-002's minimum RSVP window forced a look at how the two timers relate. The
maintainer's first instinct was to constrain the two *configured* numbers against each other —
`minRSVP >= minProtoDefault`, which the chosen values satisfy by construction (both 72h). That
instinct is the trap: comparing the RSVP floor against the *default* embargo says nothing about
the RSVP floor against a *particular* embargo, which is where the bug lives. Today's 90-day
fallback makes the inequality false and the bug fires anyway; any protocol default makes it true
and the bug still fires, because a 12-hour agreed embargo is reachable either way. The coherent
constraint is not between the two configured numbers at all — it runs per-invitation: an invitee
must be able to answer while the embargo still exists.

## Where each member's content went

| Member | Disposition |
|---|---|
| **#2215** | Closed. All five of its questions answered: the documented MAY is corrected (not a commitment); pre-case terms *do* get a home via the `context` widening; migration into the case is a context rewrite; the wire format does need a non-case context (VAM-05-001); and it interacts with EP-04 decisively — EP-04 is where the whole thing lands. Impl: #3392 |
| **#2075** | Closed. Unblocked as the **real** variation (a), not its own proposed "very-early variation (b)" fallback. Impl: #3393 |
| **#2060** | **Ejected**, stays open. Party discovery, not embargo state. Rewired `blocked-by` G13 (#2841) and returned to G16 (#2844) as a Tier B sort item |
| **#1189** | **Ejected**, stays open. Rewired `blocked-by` G13, which should now **own** it |

## The ejections, and a wiring defect they exposed

Both ejected issues are about addressing a party you cannot identify. A directory service is
needed whatever the pre-case answer is: its consumers are public-key discovery (`notes/encryption.md`,
epic #1156), `EmbargoPolicy` compatibility evaluation, and disclosure-policy interrogation.
Pre-case contact-finding is one consumer among several, and the smallest — deciding a directory
service inside a frame of "does Vultron have a pre-case phase" inverts the dependency.

The wiring confirmed it: **G08 and G13 had each been told to leave #1189 to the other.** G08's
body said "G13 also touches key discovery — do not close #1189 there"; G13's AC-4 said "#1189
referenced for discovery overlap, not closed here". A mutual deferral, so neither owned it. G13
does now.

A distinction worth carrying into G13: dereferencing a **known** actor URI ("what is this peer's
key or policy?") is a plain AS2 `GET` — already tracked as **#3258** under epic #890 — and is
*not* a directory service. Resolving an **unknown** party ("who is the Vendor for product X?")
is what #1189 covers. G13's AC-1 needs the first, not the second.

Also found: `EmbargoPolicy` is declared on the actor as `embargo_policy: Any | None` and served
on the actor profile, but **nothing fetches a peer's policy** — so the glossary's claim that it
exists to "evaluate compatibility before proposing an embargo" is currently unrealisable.

## Process notes

- The maintainer's opening challenge — "I'm not convinced all of them are ready for design work"
  — was correct, and checking it first changed the session's shape. Per-member readiness beat
  per-group planning: #2215 ready, #2075 derivative, #2060 triage-ready but not design-ready,
  #1189 greenfield.
- The maintainer's reframe mid-interview ("the rules are malleable... this process is to discover
  and improve the rules as written, not to blindly follow them") was the turning point. Reading
  `em/defaults.md` as *authored guidance that may itself be wrong* is what allowed a `SHALL` to
  be overturned instead of engineering around it.
- **ADR renumbered 0095 → 0096 mid-session**: #3370 landed ADR-0095 during the write-up, and
  `freshen-branch.sh` surfaced it as a cherry-pick conflict in `docs/adr/index.md` and
  `mkdocs.yml`. `notes/git-workflow-pitfalls.md` warns to re-check ADR numbers before merge; the
  warning earned its place again.

## Implementation Tasks

```text
#3390  Split actor default from protocol default; kill the 90-day fallback   → #2687
└── #3392  Proposed EmbargoEvent on the report Offer; shortest-wins merge    → #2687
    └── #3393  Demo scenario: Reporter proposes terms with the Report        → #2425
#3391  Clamp the RSVP deadline to the embargo end                            → #2687
```

`#3391` is deliberately independent: it fixes a defect that needs none of the rest.
