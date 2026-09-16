### 12.4 Role-Specific Normative Requirements

#### 12.4.1 Participant-Specific CS Transitions (VFD)

VFD records what a specific participant has done, so authority to cause a VFD
transition is scoped to the participant that did it.

!!! note "Recall: vendor/fix/deploy states"
    {% include-markdown "../includes/_vfd-states-table.md" %}

    Full definitions are in [§8.1](../index.md#81-vfd-vendor-aware-fix-ready-fix-deployed).

For **self-reported** VFD transitions (a participant advancing its own state via
the local trigger path):

- `f→F` (`VFd`, fix ready): MUST only be driven by an actor holding Vendor;
  MUST fail when Vendor is absent
- `d→D` (`VFD`, fix deployed): MUST only be driven by an actor holding Deployer;
  MUST fail when Deployer is absent
- A Vendor-only actor MUST NOT advance past `VFd` without also holding Deployer

!!! warning "Publishing a fix is not deploying it"
    A vendor that publishes a patch has made the patch available. It has not
    deployed it: deployment happens in the systems that run the product, and it
    is a Deployer's act. Fix Ready and Fix Deployed are therefore distinct
    protocol facts, and one MUST NOT be inferred from the other.

    The same separation applies to public awareness. A notification that
    information is public sets Public Aware, which is world state. It MUST NOT
    set Fix Deployed, which is participant state requiring the Deployer role. An
    implementation that treats publication as deployment produces an
    unauthorized VFD advance.

{% include-markdown "../_oq-v-to-V.md" %}

#### 12.4.2 Participant-Agnostic CS Transitions (PXA)

PXA records the state of the world rather than the state of any participant, so
these transitions are not scoped to a role. Anyone may notice that a vulnerability
has become public.

!!! note "Recall: public/exploit/attacks axes"
    {% include-markdown "../includes/_pxa-states-table.md" %}

    Full definitions are in [§8.2](../index.md#82-pxa-public-aware-exploit-public-attacks-observed).

PXA records the state of the world rather than of any participant, so **any**
participant MAY report a PXA observation. These transitions are role-ungated:
information may become public, exploits may appear, and attacks may be observed
independently of anything a case participant does or causes.

- `p→P` (publicly aware): any participant may report
- `x→X` (exploit public): any participant may report
- `a→A` (attacks observed): any participant may report

Reporting is not adoption. A reported observation is a claim. Whether it becomes
canonical case state, and whether it triggers embargo teardown, is decided by the
**CASE_MANAGER**, following the two-seam model of
[§10.3](../index.md#103-status-adoption-the-two-seam-model) and subject to Case
Owner authorization by default. The role rule here — *who may report* — is
deliberately separate from the authorization rules there — *what the CASE_MANAGER
does with a report*.

!!! note "Informative: automated observers"
    An actor may be an automated service that monitors external sources — threat
    feeds, public disclosures, vulnerability databases — and reports what it finds
    into a case. Such a service is not a distinct protocol role: it reports PXA
    observations on the same terms as any other participant, and its reports are
    adopted through the same authorization as theirs
    ([§10.3](../index.md#103-status-adoption-the-two-seam-model)).

#### 12.4.3 CVE ID Assignment

An actor holding the CVE Numbering Authority (CNA) role MUST be able to assign
CVE IDs, which requires evaluating a vulnerability against the eligibility
criteria before assignment.

An actor that does not hold the CNA role MUST delegate ID assignment. It MAY
delegate to an external CNA service, or to another participant in the same case
that holds the CNA role — a coordinator or vendor acting as a CNA can perform the
assignment without the case leaving the protocol.

**Eligibility criteria posture.** This specification does not
normatively cite a specific edition of the CNA Operational Rules, nor does it
treat eligibility checks as fully implementation-defined. Instead, the
reference implementation follows CNA Operational Rules v4.1.0 as the
conformance baseline. Adopting a newer edition requires updating the spec and
the implementing call-out. This avoids coupling the RFC to an
independently-versioned external document's release cycle while remaining
transparent about which edition the reference implementation follows.

Eligibility checking is a single logical capability: the full set of criteria
applied as a unit against one rules edition. The protocol treats it as one
decision with one outcome, and does not specify how an implementation reaches
that decision.

#### 12.4.4 Case Owner Authority

Adopting a reported status as canonical case state requires the **Case Owner's**
authorization. The Case Owner is the party whose disclosure decision the case
exists to serve, so it is the party entitled to decide what the case asserts.
The CASE_MANAGER MUST obtain that authorization by default before adopting a
participant's reported status ([§10.3](../index.md#103-status-adoption-the-two-seam-model)).

One case is exempt. Where the Case Owner is itself the sender, the CASE_MANAGER
MUST adopt the status without seeking approval: asking the Case Owner to approve
its own report would be circular.
