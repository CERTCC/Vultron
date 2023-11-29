# Improving Definitions of Common Terms {#sec:defining_common_terms}

{% include-markdown "../../includes/not_normative.md" %}

Some terms surrounding CVD and VM have been ambiguously defined in common
usage. One benefit of the definition of events, states, and possible CVD
histories presented in this whitepaper is an opportunity to clarify
definitions of related terms. In this section we will use our model to
formally define their meaning.

## Zero Day {#sec:zerodays}

!!! info inline end "Vultron and the Wassenaar Arrangement"

    This section extends prior work by Allen Householder in 
    [Like Nailing Jelly to the Wall: Difficulties in Defining "Zero-Day Exploit"](https://insights.sei.cmu.edu/blog/like-nailing-jelly-to-the-wall-difficulties-in-defining-zero-day-exploit/),
    written in response to then-proposed changes to the Wassenaar Arrangement regarding export 
    controls for intrusion software.

The information security community uses a variety of common phrases that
contain the words *zero day*. This creates confusion that we can resolve 
formally using our model.

!!! example "What does *zero day* mean to you?"

    As an example, a reviewer stated that they prefer to define "zero day vulnerability" as
    **X** $\prec$ **V** and not **P** $\prec$ **F** or **A** $\prec$ **F**.
    We should seek these precise definitions
    because sometimes both **X** $\prec$ **V** and
    **P** $\prec$ **F** are true, in which case two people might
    agree that an instance is a "zero day" without realizing that they
    disagree on its definition.



### Zero Day Vulnerability


Two common definitions for this term are in widespread use; a third
is drawn from an important policy context. The two commonly-used
definitions can be considered a relatively *low* threat level
because they only involve states $q \in {xa}$ where no exploits are
public and no attacks have occurred. We ordered all three
definitions in approximately descending risk due to the expected
duration until **D** can be achieved.

|  Zero Day Vulnerability Type  |                                                  Definition                                                   | Description                                                                                                                                                                                                                                                                                                                                | 
|:-----------------------------:|:-------------------------------------------------------------------------------------------------------------:|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|               1               |                                           $q \in vfdp \cdot \cdot$                                            | The United States VEP [@usg2017vep] defines *zero day vulnerability* in a manner consistent with $q \in {vp}$. Further discussion appears in [VEP](vep.md).                                                                                                                               |
|               2               |  **P** $\prec$ **V**<br/>${v \cdot \cdot p \cdot \cdot} \xrightarrow{\mathbf{P}} {v \cdot \cdot P \cdot \cdot}$  | when the vulnerability becomes public before the vendor is aware of it. Note that our model assumes that states in ${vP}$ are unstable and resolve to ${vP} \xrightarrow{\mathbf{V}} {VP}$ in the next step.                                                                                                                               |
|               3               |  **P** $\prec$ **F**<br/>${\cdot f \cdot p \cdot \cdot} \xrightarrow{\mathbf{P}} {\cdot f \cdot P \cdot \cdot}$  | when the vulnerability becomes public before a fix is available, regardless of the vendor's awareness. Some states in ${fP}$---specifically, those in ${VfP}$---are closer to ${\mathbf{F}}$ (and therefore ${\mathbf{D}}$) occuring than others (i.e., ${vfP}$), thus this definition could imply less time spent at risk than the first. |

### Zero Day Exploit

This term has three common definitions. Each can be considered a
*moderate* threat level because they involve transition from
${xa} \xrightarrow{\mathbf{X}} {Xa}$. However, we ordered them in
approximately descending risk due to the expected duration until
**D** can be achieved.

|  Zero Day Exploit Type  |                                                Definition                                                 | Description                                                                                                                                                                                                       |
|:-----------------------:|:---------------------------------------------------------------------------------------------------------:|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|            1            |          **X** $\prec$ **V**<br/>${vfd \cdot x \cdot} \xrightarrow{\mathbf{X}} {vfd \cdot X \cdot}$          | when an exploit is released before the vendor is aware of the vulnerability.                                                                                                                                      |
|            2            |     **X** $\prec$ **F**<br/>${\cdot fd \cdot x \cdot} \xrightarrow{\mathbf{X}} {\cdot fd \cdot \cdot X}$     | when an exploit is released before a fix is available for the vulnerability. Because $\mathcal{Q}_{vf} \subset \mathcal{Q}_{f}$, any scenario matching the previous definition also matches this one.             |
|            3            | **X** $\prec$ **P**<br/>${\cdot \cdot \cdot px \cdot} \xrightarrow{\mathbf{X}} {\cdot \cdot \cdot pX \cdot}$ | when an exploit is released before the public is aware of the vulnerability. Note that our model assumes that states in ${pX}$ are unstable and transition ${pX} \xrightarrow{\mathbf{P}} {PX}$ in the next step. |

### Zero Day Attack

We have identified three common definitions of this term. Each can
be considered a *high* threat level because they involve the
**A** transition. However, we ordered them in approximately
descending risk due to the expected duration until **D** can
be achieved.

| Zero Day Attack Type |                                                 Definition                                                  | Description                                                                                                                                                                                                                                        |
|:--------------------:|:-----------------------------------------------------------------------------------------------------------:|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|          1           |           **A** $\prec$ **V**<br/>${vfd \cdot \cdot a} \xrightarrow{\mathbf{A}} {vfd \cdot \cdot A}$           | when attacks against the vulnerability occur before the vendor is aware of the vulnerability.                                                                                                                                                      |
|          2           |      **A** $\prec$ **F**<br/>${\cdot fd \cdot \cdot a} \xrightarrow{\mathbf{A}} {\cdot fd \cdot \cdot A}$      | when attacks against the vulnerability occur before a fix is available for the vulnerability. As with *zero day exploit*, because $\mathcal{Q}_{vf} \subset \mathcal{Q}_{f}$, any scenario matching the previous definition also matches this one. |
|          3           | **A** $\prec$ **P**<br/>${\cdot \cdot \cdot p \cdot a} \xrightarrow{\mathbf{A}} {\cdot \cdot \cdot p \cdot A}$ | when attacks against the vulnerability occur before the public is aware of the vulnerability. Note that this definition disregards the vendor entirely since it makes no reference to either **V** or **F**.                                       |

## Forever Day

In common usage, a *forever day* vulnerability is one that is expected
to remain unpatched indefinitely [@ars2012forever]. In other words, the
vulnerability is expected to remain in *..d...* forever. This 
situation can
occur when deployed code is abandoned for a number of reasons,
including:

|  Forever Day Type  |                   States                    | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
|:------------------:|:-------------------------------------------:|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|        EoL         |      $q \in {Vfd  \cdot \cdot \cdot}$       | The vendor has designated the product as EoL and thereby declines to fix any further security flaws, usually implying $q \in {Vfd}$. Vendors should evaluate their support posture for EoL products when they are aware of vulnerabilities in ${VfdX}$ or ${VfdA}$. Potential vendor responses include issuing additional guidance or an out-of-support patch.                                                                                                                                                                                                                                                                                                                                |
|     No Vendor      |       $q \in {vfd \cdot \cdot \cdot}$       | The vendor no longer exists, implying a state $q \in {vfd}$. Neither **F** nor **D** transitions can be expected although **P**, **X**, and **A** remain possible. For this reason alone, coordinators or other stakeholders may choose to publish anyway to cause **P**. In this situation, if deployers are to respond at all, states in ${vfdP}$ are preferable to states in ${vfdp}$. Defender options in this case are usually limited to retiring or otherwise isolating affected systems, especially for vulnerabilities in either ${vfdPX}$ or ${vfdPA}$.                                                                                   |
|    Never Deploy    | $q \in {\cdot \cdot d \cdot \cdot \cdot }$  | The deployer chooses to never deploy, implying an expectation to remain in ${d}$ until the affected systems are retired or otherwise removed from service. This situation may be more common in deployments of safety-critical systems and OT than it is in IT deployments. It is also the most reversible of the three *forever day* scenarios, because the deployer can always reverse their decision as long as a fix is available ($q \in {VF}$). In deployment environments where other mitigations are in place and judged to be adequate, and where the risk posed by **X** and/or **A** are perceived to be low, this can be a reasonable strategy within a VM program. |


!!! question "What about when a vendor declines to fix a vulnerability in a supported product?"

    Scenarios in which the vendor has chosen not to develop a patch for an
    otherwise supported product, and which also imply $q \in {Vfd}$, are
    omitted from the above definition because as long as the vendor exists
    the choice to not develop a fix remains reversible. That said, such
    scenarios most closely follow the first bullet in the list above.

