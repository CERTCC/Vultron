???+ note inline end "DFA Notation Defined"
    A DFA is defined as a 5-tuple $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)
    ~${== [@kandar2013automata] ==}:

    - $\mathcal{Q}$ is a finite set of states.
    - $q_0 \in \mathcal{Q}$ is an initial state.
    - $\mathcal{F} \subseteq \mathcal{Q}$ is a set of final (or accepting)
    states.
    - $\Sigma$ is a finite set of input symbols.
    - $\delta$ is a transition function of the form $\delta: \mathcal{Q} \times \Sigma \xrightarrow{} \mathcal{Q}$.
