## 15. Informative Annexes

### Annex A — Worked Example: Single-Vendor CVD [I]

!!! info "See also"
    [Worked Example: Single-Vendor CVD](../../tutorials/worked_example.md)

### Annex B — Worked Example: Multi-Party CVD [I]

!!! info "See also"
    The reference implementation ships runnable multi-party scenarios. They
    exercise the flows this annex describes end to end.

    - [`fv_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/fv_demo.py) — Reporter → Vendor (two-party)
    - [`fcv_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/fcv_demo.py) — Reporter → Coordinator → Vendor
    - [`fvcv_handoff_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/fvcv_handoff_demo.py) — Coordinator hand-off
    - [scenario inventory](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/README.md) — the full list

### Annex C — Notation Reference [I]

!!! info "See also"
    [Notation Reference](../notation.md)

### Annex D — Possible Case Histories [I]

Ordering constraints on CS state transitions are not yet normatively specified
(see [§8.3](index.md#83-case-state-as-a-compound-tuple)). The possible-histories material is informative.

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
    - [§5.1](index.md#51-base-vocabulary) (informative note on the ActivityPub roadmap, issue #2068)

### Annex F — Behavior Tree Reference Implementation [I]

The reference implementation uses behavior trees (py_trees) to implement
protocol logic. Behavior trees are one valid implementation pattern, not a
normative requirement — this specification does not require a BT implementation.

The reference implementation's behavior trees are the ground truth for its own
tree structure: [`vultron/core/behaviors/`](https://github.com/CERTCC/Vultron/blob/main/vultron/core/behaviors/). The
narrative description under [Behavior Logic](../../topics/behavior_logic/index.md)
explains the approach but is not normative for this specification.

!!! info "See also"
    - [Behavior Logic](../../topics/behavior_logic/index.md)

---
