### 12.4 Role-Specific Normative Requirements

#### 12.4.1 Participant-Specific CS Transitions (VFD)

VFD records what a specific participant has done, so drive authority is scoped to
the participant that did it.

For **self-reported** VFD transitions (a participant advancing its own state via
the local trigger path):

- `f→F` (`VFd`, fix ready): MUST only be driven by an actor holding Vendor;
  MUST fail when Vendor is absent
- `d→D` (`VFD`, fix deployed): MUST only be driven by an actor holding Deployer;
  MUST fail when Deployer is absent
- A Vendor-only actor MUST NOT advance past `VFd` without also holding Deployer

!!! warning "Do not conflate `P` (public aware) with `D` (fix deployed)"
    A publication notification MUST set only the PXA public-awareness state. It
    MUST NOT imply fix deployment. `P` is participant-agnostic world state; `D` is
    a participant-specific act requiring the Deployer role. An implementation that
    treats "we published" as "it's deployed" produces an unauthorized VFD
    advance.

{% include-markdown "../_oq-v-to-V.md" %}

#### 12.4.2 Participant-Agnostic CS Transitions (PXA)

PXA records the state of the world rather than of any participant, so **any**
participant MAY report a PXA observation. These transitions are role-ungated:
information may become public, exploits may appear, and attacks may be observed
independently of anything a case participant does or causes.

- `p→P` (publicly aware): any participant may report
- `x→X` (exploit public): any participant may report
- `a→A` (attacks observed): any participant may report

Reporting is not adoption. A reported observation is a claim; whether it becomes
canonical case state, and whether it triggers embargo teardown, is decided by the
two-seam model in [**§10.1**](../index.md#101-status-adoption-the-two-seam-model). The role rule here — *who may report* — is
deliberately separate from the authorization rules there — *what the Case Actor
does with a report*.

!!! note "Informative: the Sentinel capability shape"
    A participant that monitors external sources (threat feeds, public
    disclosures, vulnerability databases) and reports what it finds into a case is
    an instance of the **Sentinel** capability shape ([§12.6](../index.md#126-capability-shapes-i)).

    The Sentinel shape is defined as an optional, pluggable capability — not a
    mandatory protocol role. No spec group yet defines a Sentinel's trust
    relationship to a case, and nothing in the current protocol distinguishes a
    Sentinel's observations from any other participant's report.
    Given that StatusAdoptionGate's default policy is to auto-adopt non-owner
    reports, an unspecified external reporter is a trust-model question, not
    merely a naming one. See [§12.6](../index.md#126-capability-shapes-i) and Open Question 16. Treat this note
    as informative.

#### 12.4.3 CVE ID Assignment

An actor holding CNA MUST have the capability to assign CVE IDs, which
requires evaluating vulnerability eligibility criteria before assignment. An
actor not holding CNA MUST delegate ID assignment to an external CNA service.

**Eligibility criteria posture (resolves Open Question 9):** The RFC does not
normatively cite a specific edition of the CNA Operational Rules, nor does it
treat eligibility checks as fully implementation-defined. Instead, the
reference implementation follows CNA Operational Rules v4.1.0 as the
conformance baseline. Adopting a newer edition requires updating the spec and
the implementing call-out. This avoids coupling the RFC to an
independently-versioned external document's release cycle while remaining
transparent about which edition the reference implementation follows.

**Architectural note:** CVE eligibility checking is a single logical
capability — the full set of criteria applied as a unit against a specific
rules edition. The correct BT design is one `EvaluateCveEligibility` Evaluator
call-out point, not separate call-out points for each individual criterion
(BTND-05-007). This refactoring is tracked as a separate implementation task.

#### 12.4.4 Case Owner Authority

A Case Owner's status updates MUST be accepted without requiring approval from
a case management policy engine. Requiring a Case Owner to approve their own
updates would be circular.

For all other senders, implementations MAY require approval via a configurable
policy gate before adopting a reported status update.
