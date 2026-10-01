## Annex F — Behavior Trees as an Implementation Pattern [I]

The reference implementation expresses its protocol logic as behavior trees. This
is one workable pattern, not a requirement: this specification states what an
implementation must do, not how to structure the code that does it. A conformant
implementation may use any internal structure.

The pattern is described at
[Behavior Logic](../../topics/behavior_logic/index.md), and the reference
implementation's trees are at
[`vultron/core/behaviors/`](https://github.com/CERTCC/Vultron/blob/main/vultron/core/behaviors/).
