# Modeling and Simulation

{% include-markdown "../../includes/not_normative.md" %}

The [protocol formalisms](../../reference/formal_protocol/index.md) and [Behavior Trees](../behavior_logic/index.md)
provided in this documentation combined with the [CS model](../process_models/cs/index.md) described in 
[A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513)
point the way toward improvements in MPCVD modeling and simulation.
Given the complexity of the protocol state interactions described in
the [formal protocol](../../reference/formal_protocol/index.md) 
and the corresponding behaviors described in [CVD Behaviors](../behavior_logic/cvd_bt.md), we anticipate that modeling
and simulation work will continue progressing toward a reference implementation of the protocol we describe here.

Furthermore, the [reward functions](reward_functions.md) we outlined can&mdash;once fully realized&mdash;be used to
evaluate the efficacy of future modifications to the protocol. 
This effort could, in turn, lead to future improvements and optimizations of the MPCVD process.
The modularity of [Behavior Trees](../behavior_logic/index.md) provides ready ground for simulated experiments to determine what additional 
optimizations to the MPCVD process might be made in the future.

