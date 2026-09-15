## 15. Informative Annexes

### Annex A — Worked Example: Single-Vendor CVD [I]

!!! info "See also"
    [Worked Example: Single-Vendor CVD](../../tutorials/worked_example.md)

### Annex B — Worked Example: Multi-Party CVD [I]

!!! info "See also"
    The following demo scripts in the reference implementation illustrate
    multi-party CVD scenarios. The implementation is authoritative at this
    stage; use these scripts rather than older design documents.

    - `vultron/demo/scenario/fv_demo.py` — Reporter → Vendor (two-party)
    - `vultron/demo/scenario/fcv_demo.py` — Reporter → Coordinator → Vendor
    - `vultron/demo/scenario/fvcv_handoff_demo.py` — Coordinator hand-off
    - `vultron/demo/scenario/README.md` — full scenario inventory

### Annex C — Notation Reference [I]

!!! info "See also"
    [Notation Reference](../notation.md)

### Annex D — Possible Case Histories [I]

Ordering constraints on CS state transitions are not yet normatively specified
(see §8.3 and Open Question 12). The possible-histories material is informative.

!!! info "See also"
    - [Possible Histories](../../topics/measuring_cvd/possible_histories.md)
    - [CS Transitions](../../topics/process_models/cs/transitions.md)

### Annex E — Relationship to ActivityPub [I]

Vultron uses ActivityStreams 2.0 as its wire vocabulary. The current
specification does not require full ActivityPub conformance, but a future
version is expected to raise that floor. This annex covers where Vultron
follows ActivityPub conventions and where it diverges.

!!! info "See also"
    - [ActivityPub Activities](../../howto/activitypub/activities/index.md)
    - §5.1 (informative note on the ActivityPub roadmap, issue #2068)

### Annex F — Behavior Tree Reference Implementation [I]

The reference implementation uses behavior trees (py_trees) to implement
protocol logic. Behavior trees are one valid implementation pattern, not a
normative requirement — this specification does not require a BT implementation.

At this stage, `vultron/core/behaviors/` is the ground truth for BT structure.
Documentation in `docs/topics/behavior_logic/` provides narrative context but
should be verified against the implementation before treating it as normative
for the spec.

!!! info "See also"
    - `vultron/core/behaviors/` (authoritative)
    - [Behavior Logic](../../topics/behavior_logic/index.md) (narrative reference)

---
