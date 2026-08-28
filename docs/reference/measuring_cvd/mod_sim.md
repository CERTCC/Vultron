# Modeling and Simulation

{% include-markdown "../../includes/not_normative.md" %}

!!! note "Historical context — 2026-08-28"
    This page was written in 2022 anticipating a reference implementation of the
    Vultron protocol. That reference implementation now exists — see the
    [code reference](../code/index.md) and the [demo scenarios](../../topics/scenarios/index.md).
    The reward-function optimization research described in [Reward Functions](reward_functions.md)
    remains future work.

The [protocol formalisms](../formal_protocol/index.md) and [Behavior Trees](../../topics/behavior_logic/index.md)
provided in this documentation combined with the [CS model](../../topics/process_models/cs/index.md) described in
[A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"}
point the way toward improvements in MPCVD modeling and simulation.
Given the complexity of the protocol state interactions described in
the [formal protocol](../formal_protocol/index.md)
and the corresponding behaviors described in [CVD Behaviors](../../topics/behavior_logic/cvd_bt.md), we anticipate that modeling
and simulation work will continue progressing toward further improvements and optimizations of the MPCVD process.

Furthermore, the [reward functions](reward_functions.md) we outlined can&mdash;once fully realized&mdash;be used to
evaluate the efficacy of future modifications to the protocol.
This effort could, in turn, lead to future improvements and optimizations of the MPCVD process.
The modularity of [Behavior Trees](../../topics/behavior_logic/index.md) provides ready ground for simulated experiments to determine what additional
optimizations to the MPCVD process might be made in the future.
