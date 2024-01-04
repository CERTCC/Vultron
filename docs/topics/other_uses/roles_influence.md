# CVD Roles and Their Influence

{% include-markdown "../../includes/not_normative.md" %}

CVD stakeholders include vendors, system owners, the security research community,
coordinators, and governments. Of primary interest here
are the main roles defined in the
[CERT Guide to CVD](https://vuls.cert.org/confluence/display/CVD):
*finder/reporter*, *vendor*, *deployer*, and *coordinator*.
Each of the roles corresponds to a set of transitions
they can cause. For example, a *coordinator* can notify the *vendor*
(**V**) but not create the fix (**F**), whereas a *vendor*
can create the fix but not notify itself (although a *vendor* with an
in-house vulnerability discovery capability might also play the role of
a *finder/reporter* as well). A mapping of CVD Roles to the transitions they can control
can be found in the table below. Roles can be combined (vendor +
deployer, finder + coordinator, etc.). We also included a role of *adversary* just
to cover the **A** transition.

| Role            |           **V**            |           **F**            |           **D**            |           **P**            |           **X**            |           **A**            |
|:----------------|:--------------------------:|:--------------------------:|:--------------------------:|:--------------------------:|:--------------------------:|:--------------------------:|
| Finder/Reporter | :octicons-check-circle-24: |                            |                            | :octicons-check-circle-24: | :octicons-check-circle-24: |                            |
| Vendor          |                            | :octicons-check-circle-24: |                            | :octicons-check-circle-24: | :octicons-check-circle-24: |                            |
| Deployer        |                            |                            | :octicons-check-circle-24: |                            |                            |                            |
| Coordinator     | :octicons-check-circle-24: |                            |                            | :octicons-check-circle-24: | :octicons-check-circle-24: |                            |
| Adversary       |                            |                            |                            |                            |                            | :octicons-check-circle-24: |

Different stakeholders might want different things, although most
benevolent parties will likely seek some subset of $\mathbb{D}$. Because
$\mathcal{H}$ is the same for all stakeholders, the expected frequencies
shown in [Event Order Frequency](../measuring_cvd/reasoning_over_histories.md/#event-order-frequency)
will be consistent across any such variations in desiderata.

A discussion of some stakeholder preferences is given below, while a
summary can be found in the following table. We notate these variations of the
set of desiderata $\mathbb{D}$ with subscripts: $\mathbb{D}_v$ for
vendors, $\mathbb{D}_s$ for system owners, $\mathbb{D}_c$ for
coordinators, and $\mathbb{D}_g$ for governments. (Government stakeholders
are omitted from the table because they are expected to have similar preferences to
coordinators.)

| Desideratum $d \in \mathbb{D}$ | Vendor ($\mathbb{D}_v$) | System Owner ($\mathbb{D}_s$) | Coordinator ($\mathbb{D}_c$) |
|:------------------------------:|:-----------------------:|:-----------------------------:|:----------------------------:|
|        **V** $\prec$ **P**        |           yes           |           maybe^4^            |             yes              |
|        **V** $\prec$ **X**        |           yes           |           maybe^4^            |             yes              |
|        **V** $\prec$ **A**        |           yes           |           maybe^4^            |             yes              |
|        **F** $\prec$ **P**        |           yes           |           maybe^5^            |             yes              |
|        **F** $\prec$ **X**        |           yes           |              yes              |             yes              |
|        **F** $\prec$ **A**        |           yes           |              yes              |             yes              |
|        **D** $\prec$ **P**        |        maybe^1^         |           maybe^1^            |             yes              |
|        **D** $\prec$ **X**        |        maybe^2^         |           maybe^5^            |             yes              |
|        **D** $\prec$ **A**        |        maybe^2^         |              yes              |             yes              |
|        **P** $\prec$ **X**        |           yes           |              yes              |             yes              |
|        **P** $\prec$ **A**        |           yes           |              yes              |             yes              |
|        **X** $\prec$ **A**        |        maybe^3^         |           maybe^3^            |           maybe^3^           |

!!! tip "Table Notes"

    1. When vendors control deployment, both vendors and system owners
    likely prefer **D** $\prec$ **P**. When system owners control
    deployment, **D** $\prec$ **P** is impossible.
    2. Vendors should care about orderings involving **D** when they
    control deployment, but might be less concerned if deployment
    responsibility is left to system owners.
    3. Exploit publication can be controversial. To some, it enables
    defenders to test deployed systems for vulnerabilities or detect
    attempted exploitation. To others, it provides unnecessary adversary
    advantage.
    4. System owners may only be concerned with orderings involving
    **V** insofar as it is a prerequisite for **F**.
    5. System owners might be indifferent to **F** $\prec$ **P**
    and **D** $\prec$ **X** depending on their risk tolerance.

 In
Table [3.3](#tab:ordered_pairs){== TODO fix ref to tab:ordered_pairs ==} we defined a preference ordering between
every possible pairing of events, therefore $\mathbb{D}$ is the largest
possible set of desiderata. We thus expect the desiderata of benevolent
stakeholders to be a subset of $\mathbb{D}$ in most cases. That said, we
note a few exceptions in the text that follows.

## Vendors

As shown in the table above, we expect vendors' desiderata
$\mathbb{D}_v$ to be a subset of $\mathbb{D}$. It seems reasonable to
expect vendors to prefer that a fix is ready before either exploit
publication or attacks (**F** $\prec$ **X** and
**F** $\prec$ **A**, respectively). Fix availability implies
vendor awareness (**V** $\prec$ **F**), so we would expect
vendors' desiderata to include those orderings as well
(**V** $\prec$ **X** and **V** $\prec$ **A**,
respectively).

Vendors typically want to have a fix ready before the public finds out
about a vulnerability (**F** $\prec$ **P**). We surmise that a
vendor's preference for this item could be driven by at least two
factors: the vendor's tolerance for potentially increased support costs
(e.g., fielding customer support calls while the fix is being prepared),
and the perception that public awareness without an available fix leads
to a higher risk of attacks. As above, vendor preference for
**F** $\prec$ **P** implies a preference for
**V** $\prec$ **P** as well.

When a vendor has control over fix deployment (**D**), it will
likely prefer that deployment precede public awareness, exploit
publication, and attacks (**D** $\prec$ **P**,
**D** $\prec$ **X**, and **D** $\prec$ **A**,
respectively).

!!! tip "Some vendors might prefer public awareness before deployment anyway"

    On the other hand, some vendors might actually prefer public
    awareness before fix deployment even if they have the ability to
    deploy fixes, for example in support of transparency or trust
    building. In that case, $\mathbb{D_V} \not\subseteq \mathbb{D}$, and
    some portions of the analysis presented here may not apply.

However, when fix deployment depends on system owners
to take action, the feasibility of **D** $\prec$ **P** is
limited.

!!! tip "Silent Patches"

    "Silent patches" can obviously occur when vendors fix a
    vulnerability but do not make that fact known. In principle, silent
    patches could achieve $\mathbf{D} \prec \mathbf{P}$ even in
    traditional COTS or OSS distribution models. However, in practice
    silent patches result in poor deployment rates precisely because
    they lack an explicit imperative to deploy the fix.

Regardless of the vendor's ability to deploy fixes or
influence their deployment, it would not be unreasonable for them to
prefer that public awareness precedes both public exploits and attacks
(**P** $\prec$ **X** and **P** $\prec$ **A**,
respectively).

Ensuring the ease of patch deployment by system owners remains a likely
concern for vendors. Conscientious vendors might still prefer
**D** $\prec$ **X** and **D** $\prec$ **A** even if
they have no direct control over those factors. However, vendors may be
indifferent to **X** $\prec$ **A**.

!!! tip inline end "Related ISO/IEC Standards"

    The ISO/IEC [30111](https://www.iso.org/standard/69725.html) and
    [29147](https://www.iso.org/standard/72311.html) standards provide
    guidance to vendors on how to handle vulnerability reports and
    coordinate with security researchers. These standards are intended to
    improve the efficiency and effectiveness of the CVD process by
    providing a common framework for vendors and security researchers to
    work together. The standards do not explicitly address the ordering
    of events, but they do provide guidance on how to improve CVD outcomes
    by encouraging vendors to be responsive to vulnerability reports and
    security researchers to be cooperative with vendors. 

    See also our detailed [crosswalk](../../reference/iso_crosswalk.md) between 
    the ISO/IEC standards and the Vultron CVD model.

Although our model only addresses event ordering, not timing, a few
comments about timing of events are relevant since they reflect the
underlying state transition process from which $\mathcal{H}$ arises.
Vendors have significant influence over the speed of **V** to
**F** based on their vulnerability handling, remediation, and
development processes. They can also influence how early
**V** happens based on promoting a cooperative atmosphere with
the security researcher community. Vendor architecture and
business decisions affect the speed of **F** to **D**.
Cloud-based services and automated patch delivery can shorten the lag
between **F** and **D**. Vendors that leave deployment
contingent on system owner action can be expected to have longer lags,
making it harder to achieve the **D** $\prec$ **P**,
**D** $\prec$ **X**, and **D** $\prec$ **A**
objectives, respectively.

## System Owners

System owners ultimately determine the lag from **F** to
**D** based on their processes for system inventory, scanning,
prioritization, patch testing, and deployment---in other words, their
VM practices. In
cases where the vendor and system owner are distinct entities, system
owners should optimize to minimize the lag between **F** and
**D** in order to improve the chances of meeting the
**D** $\prec$ **X** and **D** $\prec$ **A**
objectives, respectively. Enabling automatic updates for security
patches is one way to improve **F** to **D** performance,
although not all system owners find the resulting risk of operational
impact to be acceptable to their change management process.

System owners might select a different desiderata subset than vendors
$\mathbb{D}_s \subseteq \mathbb{D}$, $\mathbb{D}_s \neq \mathbb{D}_v$.
In general, system owners are primarily concerned with the **F**
and **D** events relative to **X** and **A**.
Therefore, we expect system owners to be concerned about
**F** $\prec$ **X**, **F** $\prec$ **A**,
**D** $\prec$ **X**, and **D** $\prec$ **A**. As
discussed above, **D** $\prec$ **P** is only possible when the
vendor controls **D**. Depending on the system owner's risk
tolerance, **F** $\prec$ **P** and
**D** $\prec$ **X** may or may not be preferred. Some system
owners may find **X** $\prec$ **A** useful for testing their
infrastructure, others might prefer that no public exploits be
available.

## Security Researchers

The "friendly" offensive security community (i.e., those who research
vulnerabilities, report them to vendors, and sometimes release
proof-of-concept exploits for system security evaluation purposes) can
do their part to ensure that vendors are aware of vulnerabilities as
early as possible prior to public disclosure

!!! note "Early Vendor Notification Improves Outcomes"

    Because vendors can only develop fixes for vulnerabilities they know
    about, we expect that security researchers would prefer that vendors
    are aware of vulnerabilities before the public (**V** $\prec$ **P**), and 
    especially before exploits are publicly available (**V** $\prec$ **X**) or
    attacks are observed (**V** $\prec$ **A**).

    $$vfdpxa \xrightarrow{\mathbf{V}} Vfdpxa \implies \mathbf{V} \prec \mathbf{P} \textrm{, } \mathbf{V} \prec \mathbf{X} \textrm{ and } \mathbf{V} \prec \mathbf{A}$$

    Also note that many of the other desiderata are impossible to achieve
    without **V**. For example, **F** $\prec$ **P** is impossible 
    without **V** $\prec$ **P** because the vendor cannot create a fix for a 
    vulnerability it does not know about. The same applies to **F** $\prec$ **X**
    and **F** $\prec$ **A**. Likewise, **D** $\prec$ **P**, **X**, or **A** is 
    similarly impossible without both **V** $\prec$ **P**, **X**, or **A** and 
    **F** $\prec$ **P**, **X**, or **A** for the reasons discussed above.

Security researchers can also delay the publication of exploits until
after fixes exist, are public, and possibly even until most system owners
have deployed the fix.

!!! note "Exploit Delay Improves Outcomes"

    Delaying exploit publication until after fixes are available, the public is
    aware of the vulnerability, and system owners have deployed the fix can also
    improve outcomes. This is because it gives defenders the opportunity to
    respond before giving potential attackers a (hopefully unintended) 
    advantage.

    $$\begin{aligned}
      \mathbf{X}|q \in VFdpx &\implies \mathbf{F} \prec \mathbf{X} \\
      \mathbf{X}|q \in VFdPx &\implies \mathbf{F} \prec \mathbf{X} \textrm{ and } \mathbf{P} \prec \mathbf{X}\\
      \mathbf{X} |q \in VFDPx &\implies \mathbf{F} \prec \mathbf{X} \textrm{, } \mathbf{P} \prec \mathbf{X} \textrm{ and } \mathbf{D} \prec \mathbf{X} 
    \end{aligned}$$

    This does not preclude adversaries from doing their own exploit development 
    on the way to **A**, but it avoids providing them with unnecessary assistance.

## Coordinators

Coordinators have been characterized as seeking to balance the social
good across both vendors and system owners [@arora2008optimal]. This
implies that they are likely interested in the union of the vendors' and
system owners' preferences. In other words, coordinators want the full
set of desiderata ($\mathbb{D}_c = \mathbb{D}$).

!!! question "Why not a *Coordinator Awareness* event?"

    We pause for a brief aside about the design of the model with respect to
    the coordination role. We considered adding a *Coordinator Awareness*
    (**C**) event, but this would expand $|\mathcal{H}|$ from 70 to
    452 because it could occur at any point in any $h$. There is not much
    for a coordinator to do once the fix is deployed, however, so we could
    potentially reduce $|\mathcal{H}|$ to 329 by only including positions in
    $\mathcal{H}$ that precede the **D** event. This is still too
    large and unwieldy for meaningful analysis within our scope; instead, we
    simply provide the following comment.
    
    The goal of coordination is this: regardless of which stage a
    coordinator becomes involved in a case, the objective is to choose
    actions that make preferred histories more likely and non-preferred
    histories less likely.

The rules outlined in [CVD Action Rules](./action_rules.md) suggest available
actions to improve outcomes. Namely, this means focusing coordination
efforts as needed on vendor awareness, fix availability, fix deployment, and the
appropriately timed public awareness of vulnerabilities and their exploits
(**V**,**F**,**D**, **P**, and **X**).

## Governments

In their defensive roles, governments act as a combination of system
owners, vendors, and increasingly coordinators. Therefore we might
anticipate $\mathbb{D}_g = \mathbb{D}_c = \mathbb{D}$.

However, governments sometimes also have an adversarial role to play for
national security, law enforcement, or other reasons. The model
presented in this paper could be adapted to that role by drawing some
desiderata from the lower left triangle of Table
[3.3](#tab:ordered_pairs){== TODO fix ref to tab:ordered_pairs ==}. While defining such adversarial
desiderata ($\mathbb{D}_a$) is out of scope for this paper, we leave the
topic with our expectation that $\mathbb{D}_a \not\subseteq \mathbb{D}$.
