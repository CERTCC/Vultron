## 8. Case State (CS) Dimensions [N]

### 8.1 VFD — Participant-Specific Axis (Vendor/Fix/Deploy)

VFD tracks what a **specific participant** has done. It is monotonic and
strictly ordered: exactly four states, since a fix cannot be deployed before it
is ready, nor ready before the vendor is aware.

| State | Vendor aware | Fix ready | Fix deployed |
|---|---|---|---|
| `vfd` | no | no | no |
| `Vfd` | yes | no | no |
| `VFd` | yes | yes | no |
| `VFD` | yes | yes | yes |

Transition drive authority is governed by §12.4.1.

!!! info "See also"
    - `vultron/core/states/cs.py` (`CS_vf`, `CS_d`)
    - [CS Process Model](../../topics/process_models/cs/index.md)

### 8.2 PXA — Participant-Agnostic Axis (Public/eXploit/Attacks)

PXA tracks the state of the world, not of any participant. Unlike VFD, the three
axes are independent, giving **eight** states: `pxa`, `Pxa`, `pXa`, `pxA`, `PXa`,
`PxA`, `pXA`, `PXA`.

Any participant MAY report PXA observations (§12.4.2).

!!! note "The `pX→PX` invariant: two PXA states are ephemeral"
    Publication of an exploit implies public awareness. `pXa` and `pXA` — exploit
    public while the public is unaware — are therefore transient: they resolve
    immediately to `PXa` and `PXA` respectively.

    Implementations SHOULD treat `pX*` as a state that is passed through rather
    than rested in. Whether this invariant is normatively enforced, and where, is
    currently underspecified (§8.3).

### 8.3 Case State as a Compound Tuple

Case State is the pair `CS = (VFD, PXA)` — 4 × 8 = 32 compound states.

Not all orderings among these are reachable or meaningful, and some sequences
carry normative weight (for example, `CP` must precede `ET` where public
disclosure triggers embargo teardown, §10).

{% include-markdown "./_oq-cs-ordering.md" %}

### 8.4 Receiving CS Messages: Own State vs. Model of Others

A participant maintains its own CS state **and** a model of every other
participant's CS state. These are updated by different events, and conflating
them is a common implementation error:

- Receiving a CS message (`CV`, `CF`, `CD`) updates the receiver's **model of the
  sender's** VFD state. The receiver's own CS state is unchanged. The receiver
  emits `CK` to acknowledge.
- Driving one's *own* VFD transition happens through the local trigger path and
  is subject to the role gating in §12.4.1.
- PXA is shared world-state rather than participant-specific, so an adopted PXA
  observation updates the canonical case status (§10.1), not a per-participant
  model.

!!! info "See also"
    - `specs/cs-behavior.yaml` CSB-01 through CSB-04
    - [CS Global vs. Local State](../../topics/process_models/model_interactions/_cs_global_local.md)

---
