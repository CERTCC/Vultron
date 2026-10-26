???+ note inline end "Automaton Notation Defined"

    A [Deterministic Finite Automaton (DFA)](../../reference/glossary.md#formal-protocol-concepts) ([Wikipedia](https://en.wikipedia.org/wiki/Deterministic_finite_automaton){:target="_blank"}) is defined as a 5-tuple $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)$ where

    - $\mathcal{Q}$ is a finite set of states.
    - $q_0 \in \mathcal{Q}$ is an initial state.
    - $\mathcal{F} \subseteq \mathcal{Q}$ is a set of final (or accepting) states.
    - $\Sigma$ is a finite set of input symbols.
    - $\delta$ is a transition function of the form $\delta: \mathcal{Q} \times \Sigma \xrightarrow{} \mathcal{Q}$.
