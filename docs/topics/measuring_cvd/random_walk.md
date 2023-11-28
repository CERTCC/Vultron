# A Random Walk through CVD States

!!! note inline end "Principle of Indifference[@pittphilsci16041]"

     Let $X = \{x_1,x_2,...,x_n\}$ be a
     partition of the set $W$ of possible worlds into $n$ mutually
     exclusive and jointly exhaustive possibilities. In the absence of any
     relevant evidence pertaining to which cell of the partition is the
     true one, a rational agent should assign an equal initial credence of
     $n$ to each cell.

To begin to differentiate skill from chance in the next few sections, we
need a model of what the CVD world would look like without any skill. We
cannot derive this model by observation. Even when CVD was first
practiced in the 1980s, some people may have had social, technical, or
organizational skills that transferred to better CVD. We follow the
principle of indifference as stated in the box at right.

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
$\sigma$ at each state $q \in \mathcal{Q}$. For example, because
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){== TODO fix ref to eq:history_vfd_rule ==} requires $\mathbf{V} \prec \mathbf{F}$
and $\mathbf{F} \prec \mathbf{D}$, only four of the six events in
$\Sigma$ are possible at the beginning of each history at $q_0=vfdpxa$:
$\{\mathbf{V},\mathbf{P},\mathbf{X},\mathbf{A}\}$. Since the principle
of indifference assigns each possible transition event as equally
probable in this model of unskilled CVD, we assign an initial
probability of 0.25 to each possible event. $$\begin{aligned}
    p(\mathbf{V}|q_0) = p(\mathbf{P}|q_0) = p(\mathbf{X}|q_0) = p(\mathbf{A}|q_0) &= 0.25\\
    p(\mathbf{F}|q_0) = p(\mathbf{D}|q_0) &= 0
\end{aligned}$$

From there, we see that the other rules dictate possible transitions
from each subsequent state. For example,
[\[eq:history_vp_rule\]](#eq:history_vp_rule){== TODO fix ref to eq:history_vp_rule ==} says that any $h$ starting with
$(\mathbf{P})$ must start with $(\mathbf{P},\mathbf{V})$. And
[\[eq:history_px_rule\]](#eq:history_px_rule){== TODO fix ref to eq:history_px_rule ==} requires any $h$ starting with
$(\mathbf{X})$ must proceed through $(\mathbf{X},\mathbf{P})$ and again
[\[eq:history_vp_rule\]](#eq:history_vp_rule){== TODO fix ref to eq:history_vp_rule ==} gets us to
$(\mathbf{X},\mathbf{P},\mathbf{V})$. Therefore, we expect histories
starting with $(\mathbf{P},\mathbf{V})$ or
$(\mathbf{X},\mathbf{P},\mathbf{V})$ to occur with frequency 0.25 as
well. We can use these transition probabilities to estimate a neutral
baseline expectation of which states would be common if we weren't doing
anything special to coordinate vulnerability disclosures. Specifically,
for each state we set the transition probability to any other state
proportional to the inverse of the outdegree of the state, as shown in
the $p(transition)$ column of Table
[3.4](#tab:allowed_state_transitions){== TODO fix ref to tab:allowed_state_transitions ==}. Real world data is unlikely
to ever reflect such a sad state of affairs (because
CVD *is* happening
after all).

|  Start State | Next State(s)                          | $p({transition})$  |  PageRank |
|:------------:|:---------------------------------------|:-------------------|:----------|
|   _vfdpxa_   | _vfdpxA_, _vfdpXa_, _vfdPxa_, _Vfdpxa_ | 0.250              | 0.123     |
|   _vfdpxA_   | _vfdpXA_, _vfdPxA_, _VfdpxA_           | 0.333              | 0.031     |
|   _vfdpXa_   | _vfdPXa_                               | 1.000              | 0.031     |
|   _vfdpXA_   | _vfdPXA_                               | 1.000              | 0.013     |
|   _vfdPxa_   | _VfdPxa_                               | 1.000              | 0.031     |
|   _vfdPxA_   | _VfdPxA_                               | 1.000              | 0.013     |
|   _vfdPXa_   | _VfdPXa_                               | 1.000              | 0.031     |
|   _vfdPXA_   | _VfdPXA_                               | 1.000              | 0.016     |
|   _Vfdpxa_   | _VfdpxA_, _VfdpXa_, _VfdPxa_, _VFdpxa_ | 0.250              | 0.031     |
|   _VfdpxA_   | _VfdpXA_, _VfdPxA_, _VFdpxA_           | 0.333              | 0.020     |
|   _VfdpXa_   | _VfdPXa_                               | 1.000              | 0.011     |
|   _VfdpXA_   | _VfdPXA_                               | 1.000              | 0.010     |
|   _VfdPxa_   | _VfdPxA_, _VfdPXa_, _VFdPxa_           | 0.333              | 0.037     |
|   _VfdPxA_   | _VfdPXA_, _VFdPxA_                     | 0.500              | 0.032     |
|   _VfdPXa_   | _VfdPXA_, _VFdPXa_                     | 0.500              | 0.051     |
|   _VfdPXA_   | _VFdPXA_                               | 1.000              | 0.063     |
|   _VFdpxa_   | _VFdpxA_, _VFdpXa_, _VFdPxa_, _VFDpxa_ | 0.250              | 0.011     |
|   _VFdpxA_   | _VFdpXA_, _VFdPxA_, _VFDpxA_           | 0.333              | 0.013     |
|   _VFdpXa_   | _VFdPXa_                               | 1.000              | 0.007     |
|   _VFdpXA_   | _VFdPXA_                               | 1.000              | 0.008     |
|   _VFdPxa_   | _VFdPxA_, _VFdPXa_, _VFDPxa_           | 0.333              | 0.018     |
|   _VFdPxA_   | _VFdPXA_, _VFDPxA_                     | 0.500              | 0.027     |
|   _VFdPXa_   | _VFdPXA_, _VFDPXa_                     | 0.500              | 0.037     |
|   _VFdPXA_   | _VFDPXA_                               | 1.000              | 0.092     |
|   _VFDpxa_   | _VFDpxA_, _VFDpXa_, _VFDPxa_           | 0.333              | 0.007     |
|   _VFDpxA_   | _VFDpXA_, _VFDPxA_                     | 0.500              | 0.010     |
|   _VFDpXa_   | _VFDPXa_                               | 1.000              | 0.007     |
|   _VFDpXA_   | _VFDPXA_                               | 1.000              | 0.009     |
|   _VFDPxa_   | _VFDPxA_, _VFDPXa_                     | 0.500              | 0.012     |
|   _VFDPxA_   | _VFDPXA_                               | 1.000              | 0.026     |
|   _VFDPXa_   | _VFDPXA_                               | 1.000              | 0.031     |
|   _VFDPXA_   | $\emptyset$                            | 0.000              | 0.139     |


## Using PageRank to Estimate Baseline State Probabilities

We use the PageRank algorithm to provide state probability estimates.
The PageRank algorithm provides a probability estimate for each state
based on a Markov random walk of the directed graph of states
[@page1999pagerank]. PageRank assumes each available transition is
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
add a single link from _VFDPXA_ to _vfdpxa_, representing a model
reset whenever the end state is reached. This modification allows
PageRank traversals to wrap around naturally and reach the early states
in the random walk process without needing to rely on teleportation.
With our modification in place, we are ready to compute the PageRank of
each node in the graph. Results are shown in Table
[3.4](#tab:allowed_state_transitions){== TODO fix ref to tab:allowed_state_transitions ==}

