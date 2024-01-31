# Case State Model Definition

{% include-markdown "../../../includes/normative.md" %}

## CS Model Diagram

A diagram of the CS process, including its states and transitions, is shown below.

In this combined model, each point along the vendor fix flow above
corresponds to an instance of the public/exploit/attack diagram.
The full diagram below shows each of these as distinct macrostates embedded in
the larger model.

{% include-markdown "./vfdpxa_diagram.md" %}

### The *Vendor Unware* macrostate (*vfd*)

Found at the top of the diagram, the $vfd$ macrostate is the
least stable of the four because many of its internal transitions are disallowed,
owing to the instability of both $pX$ and $vP$. The effect is a higher
likelihood of exiting this cube than the others. The practical
interpretation is that vendors are likely to become aware of
vulnerabilities that exist in their products barring significant effort on
the part of adversaries to prevent exiting the $vfd$ states.

### The *Vendor Aware* macrostate (*Vfd*)

In this set of states, the vendor is aware of the vulnerability, but the fix is
not yet ready. Vulnerabilities remain in $Vfd$ until the vendor produces a fix.

### The *Fix Available* macrostate (*VFd*)

States in this macrostate share the fact that a fix is available but not yet
deployed. Many publicly-disclosed vulnerabilities spend a sizable amount of
time in this cube as they await system owner or deployer action to deploy
the fix.

### The *Fix Deployed* macrostate (*VFD*)

This macrostate is a sink: once it is reached, there are no exits. Attacks
attempted in this cube are expected to fail. The broader the scope of one's
concern in terms of number of systems, the less certain one can be of having
reached this macrostate. It is rather easy to tell when a single installed
instance of vulnerable software has been patched. It is less easy to tell
when the last of thousands or even millions of vulnerable software instances
across an enterprise has been fixed.

## Simplified CS Model Diagram

A simplified version of the CS model diagram is shown below.
In this version, we are only demonstrating the parallelism between the
participant-specific (vendor fix path) and participant-agnostic (public,
exploit, attacks) aspects of the model, without the additional complexity
of the interactions between the two.

{% include-markdown "../model_interactions/_cs_global_local.md" %}

## CS Model Fully Defined

In combination, the full definition of the Case State DFA $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)^{cs}$ is shown
below.

???+ note "Case State Model $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)^{cs}$ Fully Defined"

    $CS = 
        \begin{pmatrix}
                \begin{aligned}
                        \mathcal{Q}^{cs} = & 
                            \begin{Bmatrix}
                                vfdpxa, & vfdPxa, & vfdpXa, & vfdPXa, \\
                                vfdpxA, & vfdPxA, & vfdpXA, & vfdPXA, \\
                                Vfdpxa, & VfdPxa, & VfdpXa, & VfdPXa, \\
                                VfdpxA, & VfdPxA, & VfdpXA, & VfdPXA, \\
                                VFdpxa, & VFdPxa, & VFdpXa, & VFdPXa, \\
                                VFdpxA, & VFdPxA, & VFdpXA, & VFdPXA, \\
                                VFDpxa, & VFDPxa, & VFDpXa, & VFDPXa, \\
                                VFDpxA, & VFDPxA, & VFDpXA, & VFDPXA
                            \end{Bmatrix},  \\
                    q^{cs}_0 = & vfdpxa,  \\
                    \mathcal{F}^{cs} = &\{VFDPXA\},  \\
                    \Sigma^{cs} = & \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}, \\
                        \delta^{cs} = &
        \begin{cases}
            vfdpxa &\to \mathbf{V}~Vfdpxa~|~\mathbf{P}~vfdPxa~|~\mathbf{X}~vfdpXa~|~\mathbf{A}~vfdpxA \\
            vfdpxA &\to \mathbf{V}~VfdpxA~|~\mathbf{P}~vfdPxA~|~\mathbf{X}~vfdpXA \\
            vfdpXa &\to \mathbf{P}~vfdPXa \\
            vfdpXA &\to \mathbf{P}~vfdPXA \\
            vfdPxa &\to \mathbf{V}~VfdPxa \\
            vfdPxA &\to \mathbf{V}~VfdPxA \\ 
            vfdPXa &\to \mathbf{V}~VfdPXa \\
            vfdPXA &\to \mathbf{V}~VfdPXA \\
            Vfdpxa &\to \mathbf{F}~VFdpxa~|~\mathbf{P}~VfdPxa~|~\mathbf{X}~VfdpXa~|~\mathbf{A}~VfdpxA \\
            VfdpxA &\to \mathbf{F}~VFdpxA ~|~ \mathbf{P}~VfdPxA ~|~ \mathbf{X}~VfdpXA \\
            VfdpXa &\to \mathbf{P}~VfdPXa \\
            VfdpXA &\to \mathbf{P}~VfdPXA \\
            VfdPxa &\to \mathbf{F}~VFdPxa ~|~ \mathbf{X}~VfdPXa ~|~ \mathbf{A}~VfdPxA \\
            VfdPxA &\to \mathbf{F}~VFdPxA ~|~ \mathbf{X}~VfdPXA \\
            VfdPXa &\to \mathbf{F}~VFdPXa ~|~ \mathbf{A}~VfdPXA \\
            VfdPXA &\to \mathbf{F}~VFdPXA \\ 
            VFdpxa &\to \mathbf{D}~VFDpxa~|~\mathbf{P}~VFdPxa ~|~ \mathbf{X}~VFdpXa ~|~ \mathbf{A}~VFdpxA \\
            VFdpxA &\to \mathbf{D}~VFDpxA ~|~ \mathbf{P}~VFdPxA ~|~ \mathbf{X}~VFdpXA \\
            VFdpXa &\to \mathbf{P}~VFdPXa \\
            VFdpXA &\to \mathbf{P}~VFdPXA \\
            VFdPxa &\to \mathbf{D}~VFDPxa ~|~ \mathbf{X}~VFdPXa ~|~ \mathbf{A}~VFdPxA \\
            VFdPxA &\to \mathbf{D}~VFDPxA ~|~ \mathbf{X}~VFDPXA \\
            VFdPXa &\to \mathbf{D}~VFDPXa ~|~ \mathbf{A}~VFdPXA \\
            VFdPXA &\to \mathbf{D}~VFDPXA \\
            VFDpxa &\to \mathbf{P}~VFDPxa ~|~ \mathbf{X}~VFDpXa ~|~ \mathbf{A}~VFDpxA \\
            VFDpxA &\to \mathbf{P}~VFDPxA ~|~ \mathbf{X}~VFDpXA \\
            VFDpXa &\to \mathbf{P}~VFDPXa \\
            VFDpXA &\to \mathbf{P}~VFDPXA \\
            VFDPxa &\to \mathbf{X}~VFDPXa ~|~ \mathbf{A}~VFDPxA \\
            VFDPxA &\to \mathbf{X}~VFDPXA \\
            VFDPXa &\to \mathbf{A}~VFDPXA \\
            VFDPXA &\to \varepsilon \\
        \end{cases}
                \end{aligned}
        \end{pmatrix}$
