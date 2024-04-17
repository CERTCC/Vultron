???+ note inline end "CS Model Input Symbols ($\Sigma^{cs}$) Defined"

    $$\Sigma^{cs} = \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}$$

    Here we diverge somewhat from the notation used for the
    [RM](../rm/index.md) and [EM](../em/index.md) models, which use lowercase letters for transitions and
    uppercase letters for states. Because CS state names already use both lowercase
    and uppercase letters, here we use a bold font for the symbols of the
    CS DFA to differentiate the transition from the corresponding substate it leads
    to: e.g., $vfd\cdot\cdot\cdot \xrightarrow{\mathbf{V}} Vfd\cdot\cdot\cdot$.
