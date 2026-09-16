## 8. Case State (CS) Dimensions [N]

Case State records what is known about the vulnerability. It answers two different
questions, and it is a compound of two machines because those questions have
different owners.

The first is what each vendor has done about the vulnerability: is it aware, does
it have a fix, has the fix been deployed? That is participant-specific — each
participant answers for itself. The second is what the world knows: is the
vulnerability public, is there a public exploit, are attacks happening? That is a
fact about the world, shared by the whole case.

The two are tracked separately, as VFD and PXA. Confusing them is the most
consequential error in this part of the model: it leads an implementation to
record one participant's action as a change to the state of the world, or to treat
a world event as though some participant caused it.

### 8.1 VFD — Vendor Aware, Fix Ready, Fix Deployed

VFD records what a **specific participant** has done, so each participant has its
own value. It moves in one direction only, and through its states in a fixed
order: a vendor must be aware before a fix can be ready, and a fix must be ready
before it can be deployed. That ordering leaves four reachable states rather than
eight.

{% include-markdown "./includes/_vfd-states-table.md" %}

Because the axes are ordered, the state is written as a single three-letter token
in which case indicates progress: `Vfd` means the vendor is aware, the fix is not
ready, and nothing is deployed.

Which participant may cause which VFD transition depends on the roles it holds,
and is specified at
[§12.4.1](index.md#1241-participant-specific-cs-transitions-vfd).

!!! info "See also"
    - [CS Process Model](../../topics/process_models/cs/index.md)
    - [CS States](../../topics/process_models/cs/cs_model.md)

### 8.2 PXA — Public Aware, Exploit Public, Attacks Observed

PXA records the state of the world, not the state of any participant. There is one
PXA value for the case, it is shared case state, and only the CASE_MANAGER writes
it ([§5.4.1](index.md#541-single-writer-authority)).

Unlike VFD, the three axes are independent: any combination can occur, in any
order.

{% include-markdown "./includes/_pxa-states-table.md" %}

Independence gives PXA **eight** states — every combination of the three, written
by setting each letter to upper or lower case: `pxa`, `Pxa`, `pXa`, `pxA`, `PXa`,
`PxA`, `pXA`, `PXA`.

{% include-markdown "../../topics/process_models/cs/pxa_diagram.md" %}

Any participant MAY report a PXA observation, because a PXA fact is not any
participant's to own — anyone may notice that an exploit has appeared. Reporting
is not the same as the case adopting the observation
([§12.4.2](index.md#1242-participant-agnostic-cs-transitions-pxa),
[§10.3](index.md#103-status-adoption-the-two-seam-model)).

!!! note "Two PXA states are passed through, not rested in"
    Publishing an exploit makes the vulnerability public. The two states in which
    an exploit is public while the public is unaware — `pXa` and `pXA` — therefore
    describe a situation that does not persist: they resolve to `PXa` and `PXA`.
    An implementation SHOULD resolve either in the same processing step rather
    than leaving a case at rest there.

    The reverse does not hold. Attacks being observed does **not** by itself make
    the vulnerability public: an attack can be detected without its mechanism
    being understood or disclosed. `pxA` is a state a case can legitimately rest
    in.

    This specification does not say where the `pX→PX` resolution is enforced. See
    the open question in [§8.3](index.md#83-case-state-as-a-compound-tuple).

### 8.3 Case State as a Compound Tuple

Case State is the pair `CS = (VFD, PXA)`, giving 4 × 8 = 32 compound states.

Not every ordering among them is reachable or meaningful. This specification does
not yet state the ordering constraints normatively, so a conformance claim cannot
cover them.

{% include-markdown "./_oq-cs-ordering.md" %}

One ordering relationship *is* specified, because it is a cascade rather than an
ordering constraint: adopting a status that sets Public Aware, Exploit Public or
Attacks Observed requires the CASE_MANAGER to evaluate embargo teardown
([§10.3](index.md#103-status-adoption-the-two-seam-model)). The embargo therefore
ends after public awareness is recorded, not before.

### 8.4 Receiving CS Messages: Own State vs. Model of Others

A participant holds its own case state and a model of what it believes the other
participants' states to be. Different events update each one.

- **Receiving a VFD message** (`CV`, `CF`, `CD`) updates the receiver's model of
  the **sender's** VFD state. The receiver's own VFD state does not change. No
  acknowledgement is sent: a participant confirms it has the case history by the
  fact that its ledger replica is unbroken, not by acknowledging each entry
  ([§4.6](index.md#46-error-and-acknowledgement-messages)).
- **Driving one's own VFD transition** happens locally, subject to the role
  requirements of
  [§12.4.1](index.md#1241-participant-specific-cs-transitions-vfd), and is then
  announced.
- **PXA is shared case state**, so an adopted PXA observation updates the case's
  canonical status rather than any per-participant model
  ([§10.3](index.md#103-status-adoption-the-two-seam-model)).

!!! info "See also"
    - [CS Global vs. Local State](../../topics/process_models/model_interactions/_cs_global_local.md)

---
