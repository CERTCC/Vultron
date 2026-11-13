---
status: accepted
status_override: >-
  Decided by the maintainer in the planning interview for #6336 on 2026-11-12.
date: 2026-11-12
created: 2026-11-12
updated: 2026-11-12
revision: 2
amended: "2026-11-13"
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# Shadow Mode Is a Standalone, Read-Only Advisor That Translates a Case on Request

## Context and Problem Statement

CERT/CC wants Vultron's view of cases it already tracks in another system, starting with VINCE: where a case stands, which CVD desiderata it has met or broken, and which moves are open from here.
Other trackers, such as GHSA or Jira, raise the same need.

Planning for the VINCE shadow (Epic #5954) described it as a running Vultron node that kept a local copy of each VINCE case as CERT/CC's Case Manager and ran the protocol's behavior trees on it.
That framing made three problems: the node's trees would emit activities that a server mode had to suppress (#5962), acts by participants who are not on Vultron had no truthful way into the local case (#5965), and the node needed a fail-closed server mode with storage and logging rules attached (#6336).

**What is shadow mode, and what does its first version leave out?**

## Decision Drivers

- The first question to answer is whether a case from an outside system can be translated into Vultron's model and give useful insights. Nothing beyond that is needed to answer it.
- The first version must advise the people working a case, not act in it. A shadow that runs the protocol on a case is a second player at the board.
- Outside-system cases hold embargoed data, so every component that holds or sends that data is a place it can leak.
- Translation cost and the share of mappings that need judgment rather than mechanical translation are unknown until tried.

## Considered Options

- A Vultron node in shadow mode: CERT/CC's actor runs its trees on a local replica, with outward delivery suppressed.
- A standalone tool that reads, translates and analyses one case on request, then discards it.

## Decision Outcome

Chosen option: "A standalone tool that reads, translates and analyses one case on request, then discards it", because it answers the first question with no actor, no network presence and no act to fake.

1. **Advisor, not player.** The shadow tells an analyst where a case stands and which moves are open or better. This version does not act in the case, does not write to the outside system, and does not send anything to the case's participants.
2. **Pull.** An analyst names one case. The shadow reads it, translates it, analyses it and shows the result. Nothing runs between requests.
3. **Ephemeral.** A translation is built for the request that needs it and discarded afterwards. The shadow keeps no long-lived copy of an outside-system case or its translation. Transient working files within a request are allowed. A later need for the case is met by translating it again.
4. **Standalone.** The shadow uses the Vultron core as a library. It hosts no actor and has no inbox, outbox or activity delivery, so "delivers nothing" holds because no delivery path exists, not because a setting turns one off.
5. **Insights come in levels.** The first level reads the translated case as it stands: each participant's states, the desiderata met or broken, and the moves the state machines allow. The second level ranks each allowed move by the score the case would have if that move came next. A multi-step search or simulation of future play is a later decision.
6. **Measure before building on it.** Translating real-shaped cases, timing it, and sorting each mapping into translation or interpretation comes before the analysis is built on top.
7. **This is the first version.** Every "does not" above describes the shadow this record decides. A later version that writes to an outside system, acts in a case, or sends to participants is a later decision, and that record supersedes the parts of this one it changes.

How a case is read from an outside system, and what its translation contains, is [ADR-0191](0191-an-outside-system-reaches-the-core-through-a-read-only-case-reader-port.md).
How the shadow is presented and packaged is [ADR-0192](0192-the-shadow-is-a-streamlit-dashboard-shipped-as-a-compose-service.md).

### Consequences

- Good, because an act by a participant who is not on Vultron needs no door into a live case: it becomes an entry in a translation (#5965).
- Good, because no activity can leave the shadow, with no suppression code to get wrong (#5962).
- Good, because a long-lived store of outside-system cases does not exist to protect.
- Good, because the same translation is the first half of a later gateway between two outside systems, each translated to and from Vultron.
- Bad, because every request pays the full read and translation cost, which is unmeasured.
- Bad, because a pull tool cannot alert anyone when a case changes. A watcher that runs the same pull on a schedule can be added on top.
- Neutral, because the read-write gateway, where Vultron or an outside system does act through the protocol, is a separate later decision that this record leaves open.

## Validation

`specs/case-shadow.yaml` states the checkable rules (no delivery or write path, no long-lived copy), each citing this record; its packaging rules cite [ADR-0192](0192-the-shadow-is-a-streamlit-dashboard-shipped-as-a-compose-service.md).
The data rules for VINCE in [ADR-0189](0189-vince-derived-data-stays-out-of-the-repository-unless-synthetic-or-cleared-by-case-id.md) still apply.

## Pros and Cons of the Options

### A Vultron node in shadow mode

- Good, because the same deployment shape could later take part in cases as a peer.
- Bad, because its trees run as CERT/CC's Case Manager on a copy of a case CERT/CC runs elsewhere, so Vultron acts rather than advises.
- Bad, because every act by a participant outside Vultron must either be credited to CERT/CC or synthesized as that participant's own message.
- Bad, because no-delivery, storage and log rules all depend on a server mode that a half-configured server can get wrong.

### A standalone tool that translates on request

- Good, because it answers the first question with the least machinery.
- Good, because it has nothing to suppress and nothing to keep.
- Bad, because translation cost is paid on every request.

## Amendment — 2026-11-13

Rule 1 was replaced, and rule 7 was added.
Rule 1 read: "**Advisor, not player.** The shadow tells an analyst where a case stands and which moves are open or better. It never acts in the case, never writes to the outside system, and never sends anything to the case's participants."
It now reads: "**Advisor, not player.** The shadow tells an analyst where a case stands and which moves are open or better. This version does not act in the case, does not write to the outside system, and does not send anything to the case's participants."
Rule 7 reads: "**This is the first version.** Every "does not" above describes the shadow this record decides. A later version that writes to an outside system, acts in a case, or sends to participants is a later decision, and that record supersedes the parts of this one it changes."

The maintainer asked that the record state what this version does, not what the shadow will never do: a later version may write to VINCE.

- Source: #6336 (PR #6364 review)

## More Information

Planned in #6336, with the maintainer, on 2026-11-12.
The VINCE shadow's data-handling rules are [ADR-0189](0189-vince-derived-data-stays-out-of-the-repository-unless-synthetic-or-cleared-by-case-id.md).

Generated spec requirements: `case-shadow.yaml` SHD-01.
