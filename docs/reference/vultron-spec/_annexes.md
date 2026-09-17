## 16. Informative Annexes

The annexes below illustrate and explain the protocol. Nothing in them is
normative: where an annex and a normative section appear to disagree, the
normative section governs.

### Annex A — Worked Example: Single-Vendor CVD [I]

This annex traces one two-party case from first contact to closure. Each step
names the message sent and the state transition it reports, so the sequence can
be read against the state machine sections
([§6](index.md#6-report-management-rm-state-machine-n)–[§9](index.md#9-participant-embargo-consent-pec-state-machine-n)).

Four embargo outcomes are shown — accepted, rejected, countered, and accepted then
revised — because embargo negotiation is where two-party cases most often diverge.

{% include-markdown "../../tutorials/worked_example.md" start="<!-- single-vendor-start -->" end="<!-- single-vendor-end -->" heading-offset=2 %}

### Annex B — Worked Example: Multi-Party CVD [I]

This annex extends Annex A to a case with a coordinator and a second vendor. It
shows the coordinator acting as proxy for the reporter, a participant joining a
case that already has an active embargo, and the teardown-publish-close sequence
across three parties.

{% include-markdown "../../tutorials/worked_example.md" start="<!-- multi-party-start -->" end="<!-- multi-party-end -->" heading-offset=2 %}

!!! info "Runnable scenarios"
    The reference implementation ships these flows as executable scenarios, which
    are the most current statement of what it supports:

    - [`fv_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/fv_demo.py) — Reporter → Vendor (two-party)
    - [`fcv_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/fcv_demo.py) — Reporter → Coordinator → Vendor
    - [`fvcv_handoff_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/fvcv_handoff_demo.py) — Coordinator hand-off
    - [scenario inventory](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/README.md) — the full list

### Annex C — Notation Reference [I]

The conventions this specification uses for state names and case-state notation
are stated at [§1.4](index.md#14-document-conventions). This annex collects the
mathematical and diagram notation used in the formal treatment.

{% include-markdown "../notation.md" start="<!-- notation-math-start -->" end="<!-- notation-math-end -->" heading-offset=2 %}

### Annex D — Possible Case Histories [I]

Case State has 32 compound states, but far fewer orderings among them are
reachable: a fix cannot be deployed before it is ready, and vendors learn of a
vulnerability no later than the public does. Applying those constraints to the six
case-state events reduces 720 naive orderings to 70 possible case histories.

This annex derives that result. It is informative: this specification does not yet
state the ordering constraints normatively
([§8.3](index.md#83-case-state-as-a-compound-tuple)).

{% include-markdown "../../topics/measuring_cvd/possible_histories.md" heading-offset=2 %}

!!! info "See also"
    - [CS Transitions](../../topics/process_models/cs/transitions.md) — the
      complete transition grammar the derivation above rests on

### Annex E — Relationship to ActivityPub [I]

Vultron uses the ActivityStreams 2.0 vocabulary as its wire format. This version
does not require full ActivityPub server behavior; the roadmap is at
[§1.3](index.md#13-relationship-to-existing-standards).

Where Vultron follows ActivityPub conventions:

- Actors are identified by URI and expose an inbox and an outbox.
- Messages are Activities with `type`, `actor`, `object` and `id`.
- Delivery is an HTTP POST to the recipient's inbox.

Where Vultron adds constraints ActivityPub does not impose:

- Case-scoped messages route through the participant holding the Case Manager
  role rather than directly between participants
  ([§5.4.2](index.md#542-routing-topology)).
- An activity MUST carry its object inline rather than by reference
  ([§4.8](index.md#47-knowledge-model-and-actor-isolation)), because a
  participant's knowledge must not depend on another participant being reachable.
- The Vultron vocabulary extends the ActivityStreams vocabulary with the object
  types of [§5.2](index.md#52-object-types).

!!! info "See also"
    - [Vultron AS Activities](../../howto/activitypub/activities/index.md) —
      worked wire-format examples for each protocol flow

### Annex F — Behavior Trees as an Implementation Pattern [I]

The reference implementation expresses its protocol logic as behavior trees. This
is one workable pattern, not a requirement: this specification states what an
implementation must do, not how to structure the code that does it. A conformant
implementation may use any internal structure.

The pattern is described at
[Behavior Logic](../../topics/behavior_logic/index.md), and the reference
implementation's trees are at
[`vultron/core/behaviors/`](https://github.com/CERTCC/Vultron/blob/main/vultron/core/behaviors/).
