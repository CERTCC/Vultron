# Vulnerability Equities Process

{% include-markdown "../../includes/not_normative.md" %}

The Vulnerability Equities Process (VEP) is the United States government's
process to decide whether to inform vendors
about vulnerabilities they have discovered. The
[VEP Charter](<https://trumpwhitehouse.archives.gov/sites/whitehouse>.
gov/files/images/External%20-%20Unclassified%20VEP%20Charter%20FINAL.PDF) describes the process.

!!! quote inline "VEP Charter"

    The Vulnerabilities Equities Process (VEP) balances whether to
    disseminate vulnerability information to the vendor/supplier in the
    expectation that it will be patched, or to temporarily restrict the
    knowledge of the vulnerability to the USG, and potentially other
    partners, so that it can be used for national security and law
    enforcement purposes, such as intelligence collection, military
    operations, and/or counterintelligence.

For each vulnerability that enters the process, the VEP results in a
decision to *disseminate* or *restrict* the information.

In terms of our model:

| Decision    | States and Transitions                                                                         | Description              |
|-------------|------------------------------------------------------------------------------------------------|--------------------------|
| disseminate | ${v \cdot \cdot \cdot \cdot \cdot} \xrightarrow{\mathbf{V}} {V \cdot \cdot \cdot \cdot \cdot}$ | notify the vendor        |
| restrict    | ${v \cdot \cdot \cdot \cdot \cdot}$ (no transition)                                            | do not notify the vendor |

VEP policy does not explicitly touch on any other aspect of the CVD process. By solely addressing
**V**, VEP
is mute regarding intentionally triggering the **P** or
**X** transitions. It also makes no commitments about
**F** or **D**, although obviously these are entirely
dependent on **V** having occurred. However, preserving the
opportunity to exploit the vulnerability implies a chance that such use
would be observed by others, thereby resulting in the **A**
transition.

The charter sets the following scope requirement as to which
vulnerabilities are eligible for VEP:

!!! quote "VEP Charter"

    To enter the process, a *vulnerability* must be both *newly
    discovered* and not *publicly known*

given the following definitions (taken from Annex A of the charter)

| Term | Definition |
|------|------------|
| Newly Discovered | After February 16, 2010, the effective date of the initial Vulnerabilities Equities Process, when the USG discovers a zero-day vulnerability or new zero-day vulnerability information, it will be considered newly discovered. This definition does NOT preclude entry of vulnerability information discovered prior to February 16, 2010. |
| Publicly known | A vulnerability is considered publicly known if the vendor is aware of its existence and/or vulnerability information can be found in the public domain (e.g., published documentation, Internet, trade journals). |
| Vulnerability | A weakness in an information system or its components (e.g., system security procedures, hardware design, internal controls) that could be exploited or impact confidentiality, integrity, or availability of information. |
| Zero-Day Vulnerability | A type of vulnerability that is unknown to the vendor, exploitable, and not publicly known. |

Mapping back to our model, the VEP definition of *newly discovered* hinges
on the definition of *zero day vulnerability*. The policy is not clear
what distinction is intended by the use of the term *exploitable* in the
*zero day vulnerability* definition, as the definition of
*vulnerability* includes the phrase "could be exploited," seeming to
imply that a non-exploitable vulnerability might fail to qualify as a
*vulnerability* altogether.

Regardless, "unknown to the vendor" clearly
matches with $v \cdot \cdot \cdot \cdot \cdot$, and "not publicly known"
likewise
matches with $\cdot \cdot \cdot p \cdot \cdot$. Thus we interpret their
definition of
*newly discovered* to be consistent with $q \in {v \cdot \cdot p \cdot \cdot}$.

VEP's definition of
*publicly known* similarly specifies either "vendor is aware"
($V \cdot \cdot \cdot \cdot \cdot$) or "information can be found in the public
domain"
($\cdot \cdot \cdot P \cdot \cdot$). As above, the logical negation of these two
criteria puts us back in $q \in {v \cdot \cdot p \cdot \cdot}$ since

$${v \cdot \cdot p \cdot \cdot} = \lnot {V \cdot \cdot \cdot \cdot \cdot} \cap
\lnot {\cdot \cdot \cdot P \cdot \cdot}$$

We further
note that because a public exploit ($\cdot \cdot \cdot \cdot X \cdot$) would
also meet the
definition of "vulnerability information in the public domain," we can
narrow the scope from ${v \cdot \cdot p \cdot \cdot}$ to ${v \cdot \cdot px
\cdot}$.

Lastly, we note that due to the
[vendor fix path causality rule](../process_models/cs/cs_model.md),
${v \cdot \cdot px \cdot}$ is equivalent to ${vfdpx \cdot}$, and therefore
we can formally specify that VEP is only applicable to vulnerabilities in

$$\mathcal{S}_{VEP} = {vfdpx \cdot} = \{vfdpxa, vfdpxA\}$$

Vulnerabilities in any other state by definition should not enter into
the VEP, as the
first transition from ${vfdpx\cdot}$ (i.e., **V**, **P**, or
**X**) exits the inclusion criteria. However it is worth
mentioning that the utility of a vulnerability for offensive use
continues throughout $\cdot \cdot d \cdot \cdot \cdot$, which is a considerably
larger subset of states than ${vfdpx \cdot}$ ($|\cdot \cdot d \cdot \cdot \cdot| = 24$,
$|{vfdpx \cdot}| = 2$).
