## 7. Embargo Management (EM) State Machine [N]

An embargo is an agreement among the participants of a case not to disclose the
vulnerability publicly before an agreed point. Embargo Management tracks the
progress of that agreement for the case as a whole: whether one has been
proposed, whether it is in force, whether it is being renegotiated, and whether it
has ended.

There is exactly one embargo state per case. It is shared case state, so only the
CASE_MANAGER writes it ([§5.4.1](index.md#541-single-writer-authority)). Whether
each individual participant has agreed to the current terms is a separate
question, tracked per participant by embargo consent
([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)).

### 7.1 States

The five states below describe the case's collective position, not any one
participant's.

{% include-markdown "./includes/_em-states-table.md" %}

Note that *None* here means no embargo is in effect **for the case**. The embargo
consent machine has a separate state, *Unbound*, meaning the participant is not bound
by any embargo terms ([§9.1](index.md#91-states)). The two can legitimately disagree:
a case at Active may hold a participant at Unbound, if that participant joined after
the terms were agreed or declined them.

### 7.2 Transitions and Guards

Four triggers drive the machine: **propose**, **accept**, **reject** and
**terminate**. Every transition below is a change to shared case state, so the
CASE_MANAGER applies it; a participant causes a transition by sending the
corresponding message, not by writing the state itself.

{% include-markdown "../../topics/process_models/em/em_dfa_diagram.md" %}

| From | Trigger | To | Notes |
|---|---|---|---|
| None | propose | Proposed | |
| Proposed | propose | Proposed | A further proposal supersedes the outstanding one |
| Proposed | reject | None | No terms were ever in force |
| Proposed | accept | Active | |
| Active | propose | Revised | Proposing against an active embargo opens a revision |
| Revised | propose | Revised | |
| Revised | reject | Active | The prior terms stand |
| Revised | accept | Active | The revised terms replace the prior ones |
| Active | terminate | Exited | |
| Revised | terminate | Exited | |

!!! warning "Rejecting a revision does not end the embargo"
    Reject behaves differently depending on where it arrives, and the difference
    is easy to get backwards.

    From **Proposed**, reject returns the case to None: no terms were ever in
    force, so refusing them leaves the case with no embargo.

    From **Revised**, reject returns the case to **Active**, not to None. The
    participants are refusing the *proposed change*, not the embargo. The
    previously agreed terms remain in force. An implementation that returns to
    None here silently drops an embargo that everyone still expects to hold.

**Reaching Exited.** Exited means the embargo has been torn down at the case
level. A participant does not put the case into Exited by deciding to stop
observing the embargo. What a participant may do is report that it intends to
exit, propose a shorter embargo, or propose an earlier end date; the CASE_MANAGER
then terminates the embargo and records the termination
([§10.2](index.md#102-embargo-revision-and-termination-cascades)). Terminating an
embargo requires Case Owner authorization by default, on the same terms as any
other change to canonical case state
([§10.3](index.md#103-status-adoption-the-two-seam-model)).

**Embargo duration selection.** Where several proposals are outstanding,
participants SHOULD accept the shortest and propose the remainder as a revision.
Other policies are also admissible: an implementation MAY defer the choice to the
Case Owner, or apply its own organizational policy. This specification does not
mandate shortest-wins.

**Tacit acceptance.** A receiver MAY publish a default embargo policy. Where it
has, a sender that submits a report without proposing terms accepts that default.
This applies only to the default-policy path. In every other case, embargo
agreement and rejection SHOULD be explicit.

### 7.3 Relationship to Embargo Consent

The two machines answer different questions. Embargo Management says whether the
*case* has an embargo. Embargo consent
([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)) says whether a
given *participant* has agreed to it. Neither determines the other, which is why
both are needed.

They are coupled at two points, because consent is given to specific terms rather
than to the idea of an embargo:

- **Entering Revised** lapses consent. Every participant at Signatory moves to
  Lapsed: their agreement covered the previous terms.
- **Entering Exited** resets consent. Every participant returns to Unbound:
  with no embargo in scope, there is nothing to consent to.

[§10.2](index.md#102-embargo-revision-and-termination-cascades) specifies both
cascades.

!!! info "See also"
    - [Embargo Management Process Model](../../topics/process_models/em/index.md)
    - [Negotiating Embargoes](../../topics/process_models/em/negotiating.md)
    - [Early Termination](../../topics/process_models/em/early_termination.md)

---
