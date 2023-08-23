# What Does *Success* Mean in CVD?

    
We take as a base set of criteria the ordering preferences given in the
2021 report 
[A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771)
by Householder and Spring.

While we incorporate this model fully [elsewhere](../process_models/cs),
some notation is necessary to proceed here.
The [Case State model](../process_models/cs) is built on the idea that there are six events of significance
in the lifespan of every vulnerability, shown in the table below.

| Event | Notation | Event | Notation |
| :--- |:---------| :--- |:---------|
| Vendor Awareness | **V** | Public Awareness | **P** |
| Fix Ready | **F** | Exploit Public | **X** |
| Fix Deployed | **D** | Attacks Observed | **A** |

Our 2021 [report](https://doi.org/10.1184/R1/16416771)
defines a set of 12 ordering preferences over these 6 events. 
We present them in roughly descending order of desirability according to the partial
order developed in that report.
Items closer to the top of the list are indicators of CVD skill.

!!! note inline end "Formalism"

    The symbol $\prec$ is read as *precedes*.

    | Ordering Preference | Notation |
    | :--- | :--- |
    | Fix Deployed Before Public Awareness | **D** $\prec$ **P** |
    | Fix Ready Before Public Awareness | **F** $\prec$ **P** |
    | Fix Deployed Before Exploit Public | **D** $\prec$ **X** |
    | Fix Deployed Before Attacks Observed | **D** $\prec$ **A** |
    | Fix Ready Before Exploit Public | **F** $\prec$ **X** |
    | Vendor Awareness Before Public Awareness | **V** $\prec$ **P** |
    | Fix Ready Before Attacks Observed | **F** $\prec$ **A** |
    | Public Awareness Before Exploit Public | **P** $\prec$ **X** |
    | Exploit Public Before Attacks Observed | **X** $\prec$ **A** |
    | Public Awareness Before Attacks Observed | **P** $\prec$ **A** |
    | Vendor Awareness Before Exploit Public | **V** $\prec$ **X** |
    | Vendor Awareness Before Attacks Observed | **V** $\prec$ **A** |

## Fix Deployed Before Public Awareness

For a fix to be deployed prior to public awareness, a lot has to go
right in the CVD process: The vendor has to know about
the vulnerability, create a fix, and deploy it&mdash;all without
public knowledge&mdash;and has to achieve all that prior to any
exploits being published or attacks becoming known to the public.
Furthermore, it requires that the Vendor has the capability to
deploy fixes without intervention by the system owner or user, which
is a rare engineering feat unattainable by many software supply
chains. More often, fix deployment (**D**) requires users
and/or system owners (Deployers) to take action. The need to inform
Deployers implies a need for public awareness of the vulnerability,
making this criteria impossible to achieve in those scenarios.

## Fix Ready Before Public Awareness

Deployers (i.e., the public) can take no action until a fix is
ready. Because public awareness also implies adversary awareness,
the vendor-adversary race becomes even more critical when this
condition is not met. Only Vendors who can receive *and act* on
vulnerability reports---whether those reports originate from inside
or outside of the organization---are able to achieve this goal.

## Fix Deployed Before Exploit Public

Deploying a fix before an exploit is made public helps reduce the
net risk to end users.

## Fix Deployed Before Attacks Observed

Attacks occurring before a fix has been deployed are when there's
maximum risk to users; therefore, we wish to avoid that situation.

## Fix Ready Before Exploit Public

Exploit publication prior to fix readiness represents a period of
increased threat to users since it means that attackers can exploit
the vulnerability even if they lack exploit development skills. When
fixes are ready before exploits are made public, defenders are
better positioned to protect their users.

## Vendor Awareness Before Public Awareness

Public awareness prior to vendor awareness can cause increased
support costs for vendors at the same time they are experiencing
increased pressure to prepare a fix.

## Fix Ready Before Attacks Observed

As in the case with published exploits, when fixes exist before
attacks are observed, defenders are in a substantially better
position to protect their users.

## Public Awareness Before Exploit Public

There is broad agreement that it is better for the public to find
out about a vulnerability via a CVD process rather than because someone
published an exploit for any adversary to use.

## Exploit Public Before Attacks Observed

This criterion is not about whether exploits should be published or
not. It is about whether we should prefer histories in which
exploits are published *before* attacks happen over histories in
which exploits are published *after* attacks happen. Because
attackers have more advantages in the latter case than the former,
histories in which **X** $\prec$ **A** are preferable to
those in which **A** $\prec$ **X**.

## Public Awareness Before Attacks Observed

Similar to the exploit case above, public awareness via
CVD is
generally preferred over public awareness resulting from incident
analysis that results from attack observations.

## Vendor Awareness Before Exploit Public

If public awareness of the vulnerability prior to vendor awareness
is bad, then a public exploit is at least as bad because it
encompasses the former and makes it readily evident that adversaries
have exploit code available for use.

## Vendor Awareness Before Attacks Observed

Attacks prior to vendor awareness represent a complete failure of
the vulnerability remediation process because they indicate that
adversaries are far ahead of defenders.

---

Taken together, these twelve ordering preferences constitute the minimum
set of outcomes we hope to emerge from the protocol that is the focus of this effort.
