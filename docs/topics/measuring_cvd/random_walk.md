# A Random Walk through CVD States

{% include-markdown "../../includes/not_normative.md" %}

To begin to differentiate skill from chance in the next few sections, we
need a model of what the CVD world would look like without any skill. We
cannot derive this model by observation. Even when CVD was first
practiced in the 1980s, some people may have had social, technical, or
organizational skills that transferred to better CVD. We follow the
*principle of indifference* as stated below.

<!-- for spacing -->
<br/>

!!! quote "Benjamin Eva in [*Principles of Indifference*](https://doi.org/10.5840/jphil2019116724){:target="_blank"}"

    Let $X = \{x_1,x_2,...,x_n\}$ be a
    partition of the set $W$ of possible worlds into $n$ mutually
    exclusive and jointly exhaustive possibilities. In the absence of any
    relevant evidence pertaining to which cell of the partition is the
    true one, a rational agent should assign an equal initial credence of
    $n$ to each cell.

While the principle of indifference is rather strong, it is inherently
difficult to reason about absolutely skill-less CVD when the work
of CVD is, by its nature, a skilled job.
Given the set of states and allowable transitions between them, we can apply
the principle of indifference to define a baseline against which
measurement can be meaningful.

## Estimating State Transition Probabilities

Our assumption is that *transitions* are equally probable, not that
*states* or *histories* are. The events $\sigma \in \Sigma$ trigger
state transitions according to $\delta$ and the histories
$h \in \mathcal{H}$ are paths (traces) through the states. This meets
the definition above because each $\sigma \in \Sigma$ is unique
(mutually exclusive) and $\delta$ defines an exhaustive set of valid
$\sigma$ at each state $q \in \mathcal{Q}$.

!!! example "Initial State Probabilities"

    For example, because causality requires $\mathbf{V} \prec \mathbf{F}$
    and $\mathbf{F} \prec \mathbf{D}$, only four of the six events in
    $\Sigma$ are possible at the beginning of each history at $q_0=vfdpxa$:
    $\{\mathbf{V},\mathbf{P},\mathbf{X},\mathbf{A}\}$. Since the principle
    of indifference assigns each possible transition event as equally
    probable in this model of unskilled CVD, we assign an initial
    probability of 0.25 to each possible event. 

    $$
    \begin{aligned}
        p(\mathbf{V}|q_0) = p(\mathbf{P}|q_0) = p(\mathbf{X}|q_0) = p(\mathbf{A}|q_0) &= 0.25\\
        p(\mathbf{F}|q_0) = p(\mathbf{D}|q_0) &= 0
    \end{aligned}
    $$

From there, we see that the other rules dictate possible transitions
from each subsequent state.

!!! example "More implications for initial state probabilities"

    For example, in the [CS Model Transitions](../process_models/cs/transitions.md), we 
    established that 

    - any $h$ starting with $(\mathbf{P})$ must start with $(\mathbf{P},\mathbf{V})$
    - any $h$ starting with $(\mathbf{X})$ must proceed through $(\mathbf{X},\mathbf{P})$ which coupled with the previous
    rule yields $(\mathbf{X},\mathbf{P},\mathbf{V})$.

    Therefore, we expect histories starting with $(\mathbf{P},\mathbf{V})$ or $(\mathbf{X},\mathbf{P},\mathbf{V})$ to occur 
    with frequency 0.25 as well.

We can use these transition probabilities to estimate a neutral
baseline expectation of which states would be common if we weren't doing
anything special to coordinate vulnerability disclosures.
Specifically, for each state we set the transition probability to any other state
proportional to the inverse of the outdegree of the state, as shown in
the $p(transition)$ column of the table below. Real world data is unlikely
to ever reflect such a sad state of affairs (because CVD *is* happening after all).

!!! tip "State Transition Diagram"

    For convenience, we've reproduced the [CS model](../process_models/cs/model_definition.md) state transition diagram
    here.
    The diagram below shows the allowed transitions between states in the
    CS model. The diagram is a directed graph with states as nodes and
    transitions as edges. The diagram is acyclic and begins at the
    *vfdpxa* state and ends at the *VFDPXA* state.
    


    {% include-markdown "../process_models/cs/vfdpxa_diagram.md" %}

!!! info "Allowed State Transitions, their Probabilities, and PageRank"

    The table below shows the allowed transitions between states in the
    CS model. The $p(transition)$ column shows the probability of each
    transition under the assumption that all transitions are equally
    probable. The final column shows the PageRank of each state, which
    is a measure of the probability of being in that state after a
    random walk through the state graph.

    |  Start State | Next State(s)                          | $p({transition})$  |  PageRank |
    |:------------:|:---------------------------------------|:-------------------|:----------|
    |   *vfdpxa*   | *vfdpxA*, *vfdpXa*, *vfdPxa*, *Vfdpxa* | 0.250              | 0.123     |
    |   *vfdpxA*   | *vfdpXA*, *vfdPxA*, *VfdpxA*           | 0.333              | 0.031     |
    |   *vfdpXa*   | *vfdPXa*                               | 1.000              | 0.031     |
    |   *vfdpXA*   | *vfdPXA*                               | 1.000              | 0.013     |
    |   *vfdPxa*   | *VfdPxa*                               | 1.000              | 0.031     |
    |   *vfdPxA*   | *VfdPxA*                               | 1.000              | 0.013     |
    |   *vfdPXa*   | *VfdPXa*                               | 1.000              | 0.031     |
    |   *vfdPXA*   | *VfdPXA*                               | 1.000              | 0.016     |
    |   *Vfdpxa*   | *VfdpxA*, *VfdpXa*, *VfdPxa*, *VFdpxa* | 0.250              | 0.031     |
    |   *VfdpxA*   | *VfdpXA*, *VfdPxA*, *VFdpxA*           | 0.333              | 0.020     |
    |   *VfdpXa*   | *VfdPXa*                               | 1.000              | 0.011     |
    |   *VfdpXA*   | *VfdPXA*                               | 1.000              | 0.010     |
    |   *VfdPxa*   | *VfdPxA*, *VfdPXa*, *VFdPxa*           | 0.333              | 0.037     |
    |   *VfdPxA*   | *VfdPXA*, *VFdPxA*                     | 0.500              | 0.032     |
    |   *VfdPXa*   | *VfdPXA*, *VFdPXa*                     | 0.500              | 0.051     |
    |   *VfdPXA*   | *VFdPXA*                               | 1.000              | 0.063     |
    |   *VFdpxa*   | *VFdpxA*, *VFdpXa*, *VFdPxa*, *VFDpxa* | 0.250              | 0.011     |
    |   *VFdpxA*   | *VFdpXA*, *VFdPxA*, *VFDpxA*           | 0.333              | 0.013     |
    |   *VFdpXa*   | *VFdPXa*                               | 1.000              | 0.007     |
    |   *VFdpXA*   | *VFdPXA*                               | 1.000              | 0.008     |
    |   *VFdPxa*   | *VFdPxA*, *VFdPXa*, *VFDPxa*           | 0.333              | 0.018     |
    |   *VFdPxA*   | *VFdPXA*, *VFDPxA*                     | 0.500              | 0.027     |
    |   *VFdPXa*   | *VFdPXA*, *VFDPXa*                     | 0.500              | 0.037     |
    |   *VFdPXA*   | *VFDPXA*                               | 1.000              | 0.092     |
    |   *VFDpxa*   | *VFDpxA*, *VFDpXa*, *VFDPxa*           | 0.333              | 0.007     |
    |   *VFDpxA*   | *VFDpXA*, *VFDPxA*                     | 0.500              | 0.010     |
    |   *VFDpXa*   | *VFDPXa*                               | 1.000              | 0.007     |
    |   *VFDpXA*   | *VFDPXA*                               | 1.000              | 0.009     |
    |   *VFDPxa*   | *VFDPxA*, *VFDPXa*                     | 0.500              | 0.012     |
    |   *VFDPxA*   | *VFDPXA*                               | 1.000              | 0.026     |
    |   *VFDPXa*   | *VFDPXA*                               | 1.000              | 0.031     |
    |   *VFDPXA*   | $\emptyset$                            | 0.000              | 0.139     |

## Using PageRank to Estimate Baseline State Probabilities

We use the [PageRank algorithm](https://en.wikipedia.org/wiki/PageRank){:target="_blank"}
to provide state probability estimates.
The PageRank algorithm provides a probability estimate for each state
based on a Markov random walk of the directed graph of states.
PageRank assumes each available transition is
equally probable, consistent with our model. To avoid becoming stuck in
dead ends, PageRank adds a *teleport* feature by which walks can, with a
small probability, randomly jump to another node in the graph.

Before proceeding, we need to make a small modification of our state
digraph. Without modification, the PageRank algorithm will tend to be
biased toward later states because the only way to reach the earlier
states is for the algorithm to teleport there. Teleportation chooses
states uniformly, so for example there is only a $1/32$ chance of our
actual start state ($q_0={vfdpxa}$) ever being chosen. Therefore, to
ensure that the early states in our process are fairly represented we
add a single link from *VFDPXA* to *vfdpxa*, representing a model
reset whenever the end state is reached. This modification allows
PageRank traversals to wrap around naturally and reach the early states
in the random walk process without needing to rely on teleportation.
With our modification in place, we are ready to compute the PageRank of
each node in the graph. Results are shown in the preceding table.
