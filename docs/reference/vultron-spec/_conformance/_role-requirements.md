### 13.4 Role-Specific Normative Requirements

#### 13.4.1 Participant-Specific CS Transitions (VFD)

VFD records what a specific participant has done, so authority to cause a VFD transition is scoped to the participant that did it.

!!! note "Recall: vendor/fix/deploy states"
    {% include-markdown "../includes/_vfd-states-table.md" %}

    Full definitions are in [§8.1 VFD — Vendor Aware, Fix Ready, Fix Deployed](../tracking-models.md#81-vfd-vendor-aware-fix-ready-fix-deployed).

Participant status is self-declared: each participant reports its own VFD transitions.
Each self-reported transition needs the role that owns it:

- `f→F` (`VFd`, fix ready) needs the Vendor role.
- `d→D` (`VFD`, fix deployed) needs the Deployer role.
  A Deployer that is not also a Vendor has no fix of its own, so it can deploy only once some Vendor in the case has a fix ready.

A Vendor-only actor therefore cannot advance past `VFd`.
A CASE_MANAGER refuses a received status that states a fix-readiness value from a sender without the Vendor role, or a deployment value from a sender without the Deployer role.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("PRM-06-001", "CSB-15-001", "CSB-15-002", "CSB-15-004", "RSH-09-003"))
```

Two transitions can also be asserted on another participant's behalf, by the Case Manager or the Case Owner.
Vendor awareness (`v→V`) is the usual case: once the notification is evidenced, for example by the vendor's acknowledgment of its Invite, the party that notified the vendor knows that the vendor has the information.
A Deployer's fix deployment (`d→D`) can be asserted the same way, which is expected to be rare: deployment is normally the Deployer's own report.
Fix readiness is never asserted on a vendor's behalf, because only the vendor can know it.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("PRM-06-003", "PRM-06-004", "PRM-06-005", "PRM-06-006"))
```

!!! warning "Publishing a fix is not deploying it"
    A vendor that publishes a patch has made the patch available.
    It has not deployed it: deployment happens in the systems that run the product, and it is a Deployer's act.
    Fix Ready and Fix Deployed are therefore distinct protocol facts, and neither is inferred from the other.

    The same separation applies to public awareness.
    A notification that information is public sets Public Aware, which is world state.
    It does not set Fix Deployed, which is participant state requiring the Deployer role.
    An implementation that treats publication as deployment produces an unauthorized VFD advance.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CSB-15-003"))
```

{% include-markdown "../_oq-v-to-V.md" %}

#### 13.4.2 Participant-Agnostic CS Transitions (PXA)

PXA records the state of the world rather than the state of any participant, so these transitions are not scoped to a role.
Anyone can notice that a vulnerability has become public.

!!! note "Recall: public/exploit/attacks axes"
    {% include-markdown "../includes/_pxa-states-table.md" %}

    Full definitions are in [§8.2 PXA — Public Aware, Exploit Public, Attacks Observed](../tracking-models.md#82-pxa-public-aware-exploit-public-attacks-observed).

Because PXA is world state, **any** participant can report a PXA observation, whatever roles it holds.
These transitions are role-ungated: information can become public, exploits can appear, and attacks can be observed independently of anything a case participant does or causes.

- `p→P` (publicly aware): any participant can report it
- `x→X` (exploit public): any participant can report it
- `a→A` (attacks observed): any participant can report it

A participant reports an observation in the case status that its own participant status carries.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("RSH-09-009", "MSM-03-004", "MSM-03-005", "MSM-03-006"))
```

Reporting is not adoption.
A reported observation is a claim.
Whether it becomes canonical case state, and whether it triggers embargo teardown, is decided by the **CASE_MANAGER**, following the two-seam model of [§11.3 Status Adoption: The Two-Seam Model](../interactions.md#113-status-adoption-the-two-seam-model) and subject to Case Owner authorization by default.
The role rule here — *who can report* — is deliberately separate from the authorization rules there — *what the CASE_MANAGER does with a report*.

!!! note "Informative: automated observers"
    An actor can be an automated service that monitors external sources — threat feeds, public disclosures, vulnerability databases — and reports what it finds into a case.
    Such a service is not a distinct protocol role: it reports PXA observations on the same terms as any other participant, and its reports are adopted through the same authorization as theirs ([§11.3 Status Adoption: The Two-Seam Model](../interactions.md#113-status-adoption-the-two-seam-model)).

#### 13.4.3 CVE ID Assignment

Assigning Common Vulnerabilities and Exposures (CVE) IDs happens outside the protocol, so this section states no protocol requirement for it.
It describes how the CVE Numbering Authority (CNA) role fits into a case.

An actor holding the CNA role can assign CVE IDs.
Assignment includes evaluating the vulnerability against the eligibility criteria first.

An actor that does not hold the CNA role delegates ID assignment.
It can delegate to an external CNA service, or to another participant in the same case that holds the CNA role.
A coordinator or vendor acting as a CNA can do the assignment without the case leaving the protocol.

**Eligibility criteria posture.** This specification does not cite a specific edition of the CNA Operational Rules, and it does not treat eligibility checks as fully implementation-defined.
Instead, the reference implementation follows CNA Operational Rules v4.1.0 as its baseline.
Adopting a newer edition means updating the specification and the implementing call-out.
This avoids coupling the Request for Comments (RFC) to the release cycle of an independently-versioned external document, while remaining transparent about which edition the reference implementation follows.

Eligibility checking is a single logical capability: the full set of criteria applied as a unit against one rules edition.
The protocol treats it as one decision with one outcome, and does not specify how an implementation reaches that decision.

#### 13.4.4 Case Owner Authority

Adopting a reported status as canonical case state is the **Case Owner's** decision.
The Case Owner is the party whose disclosure decision the case exists to serve, so it is the party entitled to decide what the case asserts.
By default the CASE_MANAGER therefore asks for the Case Owner's authorization before it adopts a participant's reported status.

One case is exempt.
Where the Case Owner is itself the sender, the CASE_MANAGER adopts the status without asking: asking the Case Owner to approve its own report would be circular.

[§11.3 Status Adoption: The Two-Seam Model](../interactions.md#113-status-adoption-the-two-seam-model) states both rules and the permissive configuration an implementation can choose instead.
