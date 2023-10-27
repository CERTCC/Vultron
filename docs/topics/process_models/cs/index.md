# CVD Case State Model Introduction

{% include-markdown "../../../includes/normative.md" %}

Here we revisit the CS model from [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513).
<!-- start_excerpt -->
The CVD Case State (CS) model provides a high-level view of the state of a CVD case.
In it we model two main aspects of the case:

1. A Participant-specific _Vendor Fix Path_ from initial vendor awareness through the deployment of a fix.
2. A Participant-agnostic _Public State_ summarizing both public and attacker awareness of the vulnerability.

These processes run in parallel, and the CS model captures the interactions between them.
<!-- end_excerpt -->
A complete derivation of the CS model can be found in [that report](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513).
Here, we are primarily interested in the final model, which comprises 32 states and their transitions.

However, due to the size of the final CS model, we begin with some necessary
background on the substates of the model in
[CVD Case Substates](#cvd-case-substates)
prior to defining the Case States in
[CVD Case States](cs_model.md).

## CVD Case Substates

In our model, the state of the world is a specification of the current
status of all the events in the vulnerability lifecycle model described
in [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513).
We describe the relevant factors as substates below.
For notational purposes, each substate status is represented by a letter for that part
of the state of the world. For example, _v_ means no Vendor awareness
and _V_ means the Vendor is aware. The complete set of status labels is
shown in the table below.

{% include-markdown "./cs_substates_table.md" %}

!!! tip "References"
  
    In defining these substates, we draw on the following sources:

    - [Windows of Vulnerability: A Case Study analysis](https://doi.org/10.1109/2.889093) by Arbaugh, Fithen, and McHugh
    - [Modeling the Security Ecosystem&mdash;The Dynamics of (In)Security](https://doi.org/10.1007/978-1-4419-6967-5_6) by Frei et al.
    - [Before we knew it: an empirical study of zero-day attacks in the real world](https://doi.org/10.1145/2382196.2382284) by Bilge and Dumitraş

### The _Vendor Awareness_ Substate (_v_, _V_)

The _Vendor Awareness_ substate corresponds to _Disclosure_ in the
Arbaugh, Fithen, and McHugh article, [Windows of Vulnerability: A Case
Study analysis](https://doi.org/10.1109/2.889093) and _vulnerability discovered by
Vendor_ in Bilge and Dumitraş's article, [Before we knew it: an
empirical study of zero-day attacks in the real
world](https://doi.org/10.1145/2382196.2382284).
In the interest of model simplicity, we are
not concerned with _how_ the Vendor finds out about the vulnerability's
existence&mdash;whether it was found via internal testing, reported within a
CVD process, or noticed as the result of incident or malware analysis.

```mermaid
stateDiagram-v2
    direction LR
    v : Vendor Unaware (v)
    V : Vendor Aware (V)
    v --> V : vendor becomes aware
```

!!! tip inline end "Software Delivery Models Affect Fix Readiness and Deployment Timing Relative to Public Awareness"

    We chose to include the *Fix Ready*, *Fix Deployed*, and *Public Awareness* events so that our model could better 
    accommodate two common modes of modern software deployment:

    -   *shrinkwrap* is a traditional distribution mode where the Vendor and
        Deployer are distinct entities, and Deployers must be made aware of
        the fix before it can be deployed. In this case, both *Fix Ready*
        and *Public Awareness* are necessary for *Fix Deployment* to occur.
    -   *SAAS* is a more recent delivery mode where the Vendor also plays the role of 
      Deployer. In this distribution mode, *Fix Ready* can lead directly
      to *Fix Deployed* with no dependency on *Public Awareness*.

    We note that so-called *silent fixes* by Vendors can sometimes result in
    a fix being deployed without public awareness even if the Vendor is not
    the Deployer. Thus, it is possible (but unlikely) for *Fix Deployed* to
    occur before *Public Awareness* even in the shrinkwrap mode above. It is
    also possible, and somewhat more likely, for *Public Awareness* to occur
    before *Fix Deployed* in the SAAS mode as well.

### The _Fix Readiness_ Substate (_f_, _F_)

The _Fix Readiness_ substate refers to the Vendor's creation and possession of a fix that _could_ be deployed to a
vulnerable system _if_ the system owner knew of its existence.
Here we differ somewhat from previous models
([1](https://doi.org/10.1109/2.889093), [2](https://doi.org/10.1007/978-1-4419-6967-5_6), and [3](https://doi.org/10.1145/2382196.2382284))&mdash;their
models address the _release_ of the fix rather than its _readiness_ for release.
This distinction is necessary because we are interested in modeling the activities and states leading up to disclosure.
Fix _release_ is a goal of the CVD process, whereas fix _readiness_ is a significant process milestone along the way.

```mermaid
stateDiagram-v2
    direction LR
    f : Fix Not Ready (f)
    F : Fix Ready (F)
    f --> F : fix is ready
```

### The _Fix Deployed_ Substate (_d_, _D_)

The _Fix Deployed_ substate reflects the deployment status of an
existing fix. The model in [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513) was initially designed to treat this substate as
a singular binary state for a case, but we intend to relax that here to
reflect a more realistic perspective in which each Deployer maintains
their own instance of this state value. It remains a binary state for
each Deployer, which, however, is still a simplification.

```mermaid
stateDiagram-v2
    direction LR
    d : Fix Not Deployed (d)
    D : Fix Deployed (D)
    d --> D : fix is deployed
```

### The _Public Awareness_ Substate (_p_, _P_)

The _Public Awareness_ substate corresponds to _Publication_ in the
Arbaugh, Fithen, and McHugh [article](https://doi.org/10.1109/2.889093), _time of
public disclosure_ in Frei et al.'s article [Modeling the Security
Ecosystem&mdash;The Dynamics of (In)Security](https://doi.org/10.1007/978-1-4419-6967-5_6) and
*vulnerability disclosed publicly* in Bilge and Dumitraş's [article](https://doi.org/10.1145/2382196.2382284).
The public might find out about a vulnerability through the Vendor's announcement of a fix, a news report about a
security breach, a conference presentation by a researcher, or a variety of other means.
As above, we are primarily concerned with the occurrence of the event itself rather than the details of _how_ the public
awareness event arises.

```mermaid
stateDiagram-v2
    direction LR
    p : Public Unaware (p)
    P : Public Aware (P)
    p --> P : public becomes aware
```

### The _Exploit Public_ Substate (_x_, _X_)

The _Exploit Public_ substate reflects whether the method of exploiting
a vulnerability has been made public in sufficient detail to be
reproduced by others. Posting PoC code to a widely available site or
including the exploit code in a commonly available exploit tool meets
this criteria; privately held exploits do not.

```mermaid
stateDiagram-v2
    direction LR
    x : Exploit Not Public (x)
    X : Exploit Public (X)
    x --> X : exploit is public
```

### The _Attacks Observed_ Substate (_a_, _A_)

The _Attacks Observed_ substate reflects whether attacks have been
observed in which the vulnerability was exploited. This substate
requires evidence that the vulnerability was exploited; we can then
presume the existence of exploit code regardless of its availability to
the public. Analysis of malware from an incident might meet
_Attacks Observed_ but not _Exploit Public_, depending on how closely
the attacker holds the malware. Use of a public exploit in an attack
meets both _Exploit Public_ and _Attacks Observed_.

```mermaid
stateDiagram-v2
    direction LR
    a : Attacks Not Observed (a)
    A : Attacks Observed (A)
    a --> A : attacks are observed
```
