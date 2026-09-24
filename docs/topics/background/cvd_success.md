---
description: >
  The outcomes a Coordinated Vulnerability Disclosure case is trying to reach,
  stated as twelve ordering preferences over six case events, and how a
  Coordinator acts on them during a case.
stakeholder_type: [cvd-practitioner, process-researcher]
level: 200
---

# What Does *Success* Mean in CVD?

A Coordinated Vulnerability Disclosure (CVD) case succeeds to the degree that some events in it happen before others.
This page states those preferences, explains why each one matters, and shows how a Coordinator acts on them during a case.
It is written for CVD practitioners and for researchers who study the process.
The preferences come from the 2021 report [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771){:target="_blank"} by Householder and Spring.

!!! info inline end "Formalism development in Measuring CVD"

    The [Measuring CVD](../measuring_cvd/index.md) section of this documentation, based on the same report, develops these preferences formally.

---

## Six events in every case

The [Case State model](../process_models/cs/index.md) is built on the idea that there are six events of significance in the lifespan of every vulnerability.
This page needs only their names and letters, shown in the table below.

| Event | Notation | Event | Notation |
| :--- |:--------:| :--- |:--------:|
| Vendor Awareness | **V** | Public Awareness | **P** |
| Fix Ready | **F** | Exploit Public | **X** |
| Fix Deployed | **D** | Attacks Observed | **A** |

The first three events form a Vendor's fix path, and each Vendor in a case has its own.
The last three are shared by the whole case.

---

## Twelve ordering preferences

The following table presents the 12 preferences in roughly descending order of desirability, according to the partial order the report develops.
Preferences closer to the top of the list are indicators of CVD skill.

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

The sections below explain each preference in the same order.

### Fix Deployed Before Public Awareness

For a fix to be deployed before public awareness, a lot has to go right in the CVD process.
The Vendor has to know about the vulnerability, create a fix, and deploy it, all without public knowledge.
It has to achieve all of that before any exploit is published or any attack becomes known to the public.
It also needs the capability to deploy fixes without intervention by the system owner or user.
That is a rare engineering feat, and many software supply chains cannot achieve it.

More often, fix deployment (**D**) requires users or system owners (Deployers) to take action.
Deployers have to be told about the vulnerability, and telling them makes it public.
In those scenarios this preference is impossible to achieve.

### Fix Ready Before Public Awareness

Deployers (that is, the public) can take no action until a fix is ready.
Public awareness also implies adversary awareness, so the race between Vendor and adversary becomes more critical when this preference is not met.
Only Vendors who can receive *and act on* vulnerability reports, whether the reports come from inside or outside the organization, can achieve it.

### Fix Deployed Before Exploit Public

Deploying a fix before an exploit is made public reduces the net risk to end users.

### Fix Deployed Before Attacks Observed

Attacks that occur before a fix has been deployed put users at maximum risk, so we want to avoid them.

### Fix Ready Before Exploit Public

An exploit published before a fix is ready increases the threat to users.
Attackers can then exploit the vulnerability even if they lack exploit development skills.
When fixes are ready before exploits are made public, defenders are better positioned to protect their users.

### Vendor Awareness Before Public Awareness

Public awareness before Vendor awareness can raise a Vendor's support costs at the same time as it raises the pressure to prepare a fix.

### Fix Ready Before Attacks Observed

As with published exploits, defenders are in a much better position to protect their users when fixes exist before attacks are observed.

### Public Awareness Before Exploit Public

There is broad agreement that it is better for the public to learn of a vulnerability through a CVD process than through a published exploit that any adversary can use.

### Exploit Public Before Attacks Observed

This preference is not about whether exploits should be published.
It is about whether we prefer histories in which exploits are published *before* attacks happen over histories in which they are published *after*.
Attackers have more advantages in the latter case than in the former.
So histories in which **X** $\prec$ **A** are preferable to those in which **A** $\prec$ **X**.

### Public Awareness Before Attacks Observed

As with exploits, public awareness through CVD is generally preferred over public awareness that comes from analyzing an observed attack.

### Vendor Awareness Before Exploit Public

Public awareness before Vendor awareness is bad, and a public exploit is at least as bad.
It includes public awareness, and it makes plain that adversaries have exploit code available.

### Vendor Awareness Before Attacks Observed

Attacks before Vendor awareness are a complete failure of the vulnerability remediation process.
They show that adversaries are far ahead of defenders.

---

## Acting on the preferences in a case

A Coordinator can cause some of the six events: Vendor Awareness (**V**) by notifying a Vendor, and Public Awareness (**P**) by publishing.
It cannot cause Fix Ready (**F**), Fix Deployed (**D**), or Attacks Observed (**A**).
So most coordination decisions in a case are choices about *when* events happen relative to each other, and which preferences that protects.

**Notifying Vendors early** serves the three Vendor Awareness preferences (**V** $\prec$ **P**, **V** $\prec$ **X**, and **V** $\prec$ **A**).
The earlier a Vendor joins a case, the less likely it is that the public, an exploit, or an attack gets there first.
In a case with a software supply chain, that includes the upstream Vendors whose fixes the others depend on.

**Proposing an embargo** protects the Fix Ready and Fix Deployed preferences over Public Awareness (**F** $\prec$ **P** and **D** $\prec$ **P**).
An embargo holds back public disclosure while defenses are prepared, as [Embargo Principles](../process_models/em/principles.md) describes.
It cannot hold back exploit publication or attacks by anyone outside the case, because adversaries are not bound by it.

**Ending an embargo early** follows once the preferences it protects are no longer at stake.
Once the vulnerability or an exploit for it is public (**P** or **X**), the embargo has nothing left to hold back, and it must end.
Once attacks are observed (**A**), the preferences over **A** are already decided, and the embargo should end.
[Early Termination](../process_models/em/early_termination.md) states these conditions as rules.

**Choosing when to publish** trades one Vendor's preferences against another's.
In a large case, waiting for every Vendor to reach Fix Ready can delay deployment for the users whose Vendors are already ready.
Early Termination discusses how to weigh that quorum.

Different roles can rank these preferences differently.
For example, a Vendor that leaves deployment to system owners might care less about the preferences involving **D**.
A system owner might be indifferent to **F** $\prec$ **P**, depending on its risk tolerance.
[CVD Roles and Their Influence](../other_uses/roles_influence.md) examines those differences.

The [Case State model](../process_models/cs/index.md) is how Vultron records which of the six events have occurred in a case.
Reading a case's state shows which preferences are still open and which are already decided.

---

## Summary

Taken together, these twelve ordering preferences are the minimum set of outcomes we hope to make more likely with the Vultron protocol.

|          $a \prec b$          |      $a \prec b$       |      $a \prec b$       |
|:-----------------------------:|:-----------------------------:|:-----------------------------:|
| $\mathbf{V} \prec \mathbf{P}$ | $\mathbf{F} \prec \mathbf{P}$ | $\mathbf{D} \prec \mathbf{P}$ |
| $\mathbf{V} \prec \mathbf{X}$ | $\mathbf{F} \prec \mathbf{X}$ | $\mathbf{D} \prec \mathbf{X}$ |
| $\mathbf{V} \prec \mathbf{A}$ | $\mathbf{F} \prec \mathbf{A}$ | $\mathbf{D} \prec \mathbf{A}$ |
| $\mathbf{P} \prec \mathbf{X}$ | $\mathbf{P} \prec \mathbf{A}$ | $\mathbf{X} \prec \mathbf{A}$ |

---

## Further reading

- [Vultron Process Models](../process_models/index.md) — the report, embargo, and case state processes that act on these goals during a case.
- [Embargo Principles](../process_models/em/principles.md) — why an embargo exists and what cooperating with one means.
- [On the Desirability of Possible Histories](../measuring_cvd/desirable_histories.md) — these preferences revisited formally, as a way to measure CVD skill.
- [CVD as a Coordination Problem](cvd-coordination-problem.md) — why every CVD case is treated as a multi-party case.
