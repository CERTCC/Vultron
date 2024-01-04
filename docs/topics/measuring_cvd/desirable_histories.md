# On the Desirability of Possible Histories

{% include-markdown "../../includes/not_normative.md" %}

{== TODO merge or deduplicate with [CVD Success](../background/cvd_success.md) ==}

All possible case histories are not equally preferable. Some are quite
bad&mdash;for
example, those in which attacks precede vendor awareness
($\mathbf{A} \prec \mathbf{V}$). Others are very desirable&mdash;for example,
those in which fixes are deployed before either an exploit is made
public ($\mathbf{D} \prec \mathbf{X}$) or attacks occur
($\mathbf{D} \prec \mathbf{A}$).

In pursuit of a way to reason about our preferences for some histories
over others, we define the following preference criteria: history $h_a$
is preferred over history $h_b$ if, all else being equal, a more
desirable event $\sigma_1$ precedes a less desirable event $\sigma_2$.
This preference is denoted as $\sigma_1 \prec \sigma_2$. We define the
following ordering preferences:

## Vendor Awareness Ordering Preferences

| Ordering Preference | Meaning |
| :--- | :--- |
| $\mathbf{V} \prec \mathbf{P}$ | Vendor awareness precedes public awareness |
| $\mathbf{V} \prec \mathbf{X}$ | Vendor awareness precedes exploit publication |
| $\mathbf{V} \prec \mathbf{A}$ | Vendor awareness precedes attacks |

Vendors can take no action to
produce a fix if they are unaware of the vulnerability. Public
awareness prior to vendor awareness can cause increased support
costs for vendors at the same time they are experiencing increased
pressure to prepare a fix. If public awareness of the vulnerability
prior to vendor awareness is bad, then a public exploit is at least
as bad because it encompasses the former and makes it readily
evident that adversaries have exploit code available for use.
Attacks prior to vendor awareness represent a complete failure of
the vulnerability remediation process because they indicate that
adversaries are far ahead of defenders.

## Fix Availability Ordering Preferences

| Ordering Preference | Meaning |
| :--- | :--- |
| $\mathbf{F} \prec \mathbf{P}$ | Fix availability precedes public awareness |
| $\mathbf{F} \prec \mathbf{X}$ | Fix availability precedes exploit publication |
| $\mathbf{F} \prec \mathbf{A}$ | Fix availability precedes attacks |

As noted above, the public can take
no action until a fix is ready. Because public awareness also
implies adversary awareness, the vendor/adversary race becomes even
more critical if this condition is not met. When fixes exist before
exploits or attacks, defenders are better able to protect their
users.

## Fix Deployment Ordering Preferences

| Ordering Preference | Meaning |
| :--- | :--- |
| $\mathbf{D} \prec \mathbf{P}$ | Fix deployment precedes public awareness |
| $\mathbf{D} \prec \mathbf{X}$ | Fix deployment precedes exploit publication |
| $\mathbf{D} \prec \mathbf{A}$ | Fix deployment precedes attacks |

Even better than vendor awareness
and fix availability prior to public awareness, exploit publication
or attacks are scenarios in which fixes are deployed prior to one or
more of those transitions.

## Public Awareness Ordering Preferences

| Ordering Preference | Meaning |
| :--- | :--- |
| $\mathbf{P} \prec \mathbf{X}$ | Public awareness precedes exploit publication |
| $\mathbf{P} \prec \mathbf{A}$ | Public awareness precedes attacks |

In
many cases, fix deployment ($\mathbf{D}$) requires system owners to
take action, which implies a need for public awareness of the
vulnerability. We therefore prefer histories in which public
awareness happens prior to either exploit publication or attacks.

## Exploit Publication Ordering Preferences

| Ordering Preference | Meaning |
| :--- | :--- |
| $\mathbf{X} \prec \mathbf{A}$ | Exploit publication precedes attacks |

This criteria is not about whether
exploits should be published or not.[^3] It is about whether we
should prefer histories in which exploits are published *before*
attacks happen over histories in which exploits are published
*after* attacks happen. Our position is that attackers have more
advantages in the latter case than the former, and therefore we
should prefer histories in which $\mathbf{X} \prec \mathbf{A}$.

---

Equation [\[eq:desiderata\]](#eq:desiderata){== TODO fix ref to eq:desiderata ==} formalizes our definition of desired
orderings $\mathbb{D}$. Table
[3.3](#tab:ordered_pairs){== TODO fix ref to tab:ordered_pairs ==} displays all 36 possible orderings of
paired transitions and whether they are considered impossible, required
(as defined by
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){== TODO fix ref to eq:history_vfd_rule ==},
[\[eq:history_vp_rule\]](#eq:history_vp_rule){== TODO fix ref to eq:history_vp_rule ==}, and
[\[eq:history_px_rule\]](#eq:history_px_rule){== TODO fix ref to eq:history_px_rule ==}), desirable (as defined by
[\[eq:desiderata\]](#eq:desiderata){== TODO fix ref to eq:desiderata ==}), or undesirable (the complement of the set
defined in [\[eq:desiderata\]](#eq:desiderata){== TODO fix ref to eq:desiderata ==}).

Before proceeding, we note that our model focuses on the ordering of
transitions, not their timing. We acknowledge that in some situations,
the interval between transitions may be of more interest than merely the
order of those transitions, as a rapid tempo of transitions can alter
the options available to stakeholders in their response. We discuss this
limitation further in §[8](#sec:limitationsAnd){== TODO fix ref to sec:limitationsAnd ==}; however, the following model posits
event sequence timing on a human-oriented timescale measured in minutes
to weeks.

!!! note "Formalizing Desirable Orderings"

    $$\begin{split}
     \mathbb{D} \stackrel{\mathsf{def}}{=}\{ & \mathbf{V} \prec \mathbf{P}, \mathbf{V} \prec \mathbf{X}, \mathbf{V} \prec \mathbf{A},\\
    & \mathbf{F} \prec \mathbf{P}, \mathbf{F} \prec \mathbf{X}, \mathbf{F} \prec \mathbf{A},\\
    & \mathbf{D} \prec \mathbf{P}, \mathbf{D} \prec \mathbf{X}, \mathbf{D} \prec \mathbf{A},\\
    & \mathbf{P} \prec \mathbf{X}, \mathbf{P} \prec \mathbf{A}, \mathbf{X} \prec \mathbf{A} \}
    \end{split}$$

    An element $d \in \mathbb{D}$ is of the form
    $\sigma_i \prec \sigma_j$. More formally, $d$ is a relation of the form
    $d\left(\sigma_1, \sigma_2, \prec \right)$. 
    $\mathbb{D}$ is a set of such relations.

## Some states are preferable to others

The desiderata defined above address the preferred ordering of transitions
in CVD histories, which imply that one should prefer to pass through some
states and avoid others.

!!! example "Preferences over states"

    For example, $\mathbf{V} \prec \mathbf{P}$ implies that we
    prefer the paths
    ${vp} \xrightarrow{\mathbf{V}} {Vp} \xrightarrow{\mathbf{P}} {VP}$ over
    the paths
    ${vp} \xrightarrow{\mathbf{P}} {vP} \xrightarrow{\mathbf{V}} {VP}$.

In the table below, we adapt those desiderata into specific
subsets of states that should be preferred or avoided if the criteria is
to be met.

|    Event Precedence ($d$)     | State Subsets to Prefer | State Subsets to Avoid |
|:-----------------------------:|:-----------------------:|:----------------------:|
| $\mathbf{V} \prec \mathbf{X}$ |          ${Vx}$         |         ${vX}$         |
| $\mathbf{V} \prec \mathbf{A}$ |         ${Va}$          |         ${vA}$         |
| $\mathbf{V} \prec \mathbf{P}$ |         ${Vp}$          |         ${vP}$         |
| $\mathbf{P} \prec \mathbf{X}$ |         ${Px}$          |         ${pX}$         |
| $\mathbf{F} \prec \mathbf{X}$ |         ${VFx}$         |        ${fdX}$         |
| $\mathbf{P} \prec \mathbf{A}$ |         ${Pa}$          |         ${pA}$         |
| $\mathbf{F} \prec \mathbf{A}$ |         ${VFa}$         |        ${fdA}$         |
| $\mathbf{F} \prec \mathbf{P}$ |         ${VFp}$         |        ${fdP}$         |
| $\mathbf{D} \prec \mathbf{X}$ |        ${VFDx}$         |         ${dX}$         |
| $\mathbf{X} \prec \mathbf{A}$ |         ${Xa}$          |         ${xA}$         |
| $\mathbf{D} \prec \mathbf{A}$ |        ${VFDa}$         |         ${dA}$         |
| $\mathbf{D} \prec \mathbf{P}$ |        ${VFDp}$         |         ${dP}$         |

## A partial order over possible histories

Given the desired preferences over orderings of transitions
($\mathbb{D}$ in *Formalizing Desirable Orderings* above,  we can construct
a partial ordering over all possible histories $\mathcal{H}$, as defined in
[\[eq:ordering\]](#eq:ordering){== TODO fix ref to eq:ordering ==}. This partial order requires a formal
definition of which desiderata are met by a given history, provided by
*Formalizing Desirable Histories* below.

!!! note "Formalizing Desirable Histories"

    $$\mathbb{D}^{h} \stackrel{\mathsf{def}}{=}\{ d \in \mathbb{D} \textrm{ such that } d \textrm{ is true for } h \} \textrm{, for } h \in \mathcal{H}$$
    
    where $d\left(\sigma_1,\sigma_2,\prec\right)$  is true for $h$ if and only if:

    $$\exists \sigma_i, \sigma_j \in h \textrm{ such that } \sigma_i = 
    \sigma_1 \textrm{ and } \sigma_j = \sigma_2 \textrm{ and } h 
    \textrm {satisfies the relation } d\left(\sigma_i,\sigma_j,\prec\right) $$

    The pre-order relation $>$ is defined over $\mathcal{H}$ as:
    
    $$(\mathcal{H},\leq_{H}) \stackrel{\mathsf{def}}{=}\forall h_a, h_b \in \mathcal{H}$$
    
    it is the case that $h_b \leq_{H} h_a$
    if and only if $\mathbb{D}^{h_b} \subseteq \mathbb{D}^{h_a}$

A visualization of the resulting partially ordered set, or poset,
$(\mathcal{H},\leq_{H})$ is shown as a Hasse Diagram in Figure
[3.1](#fig:poset){== TODO fix ref to fig:poset ==}. Hasse
Diagrams represent the transitive reduction of a poset. Each node in the
diagram represents an individual history $h_a$ from
Table [3.1](#tab:possible_histories){== TODO fix ref to tab:possible_histories ==}; labels correspond to the index of
the table. Figure [3.1](#fig:poset){== TODO fix ref to fig:poset ==} follows
[\[eq:ordering\]](#eq:ordering){== TODO fix ref to eq:ordering ==}, in that $h_a$ is higher in the order than
$h_b$ when $h_a$ contains all the desiderata from $h_b$ and at least one
more. Histories that do not share a path are incomparable (formally, two
histories incomparable if both
$\mathbb{D}^{h_a} \not\supset \mathbb{D}^{h_b}$ and
$\mathbb{D}^{h_a} \not\subset \mathbb{D}^{h_b}$). The diagram flows from
least desirable histories at the bottom to most desirable at the top.
This model satisfies **RQ1**; §[4](#sec:reasoning){== TODO fix ref to sec:reasoning ==} and
§[5](#sec:skill_luck){== TODO fix ref to sec:skill_luck ==}
will demonstrate that the model is amenable to analysis and
§[6.2.2](#sec:mpcvd criteria){== TODO fix ref to sec:mpcvd criteria ==} will lay out the criteria for extending
it to cover MPCVD.

The poset $(\mathcal{H},\leq_{H})$, has as its upper bound
$$h_{69} = (\mathbf{V}, \mathbf{F}, \mathbf{D}, \mathbf{P}, \mathbf{X}, \mathbf{A})$$
while its lower bound is
$$h_{0} = (\mathbf{A}, \mathbf{X}, \mathbf{P}, \mathbf{V}, \mathbf{F}, \mathbf{D}).$$

| $row \prec col$ | $\mathbf{V}$ | $\mathbf{F}$ | $\mathbf{D}$ | $\mathbf{P}$ | $\mathbf{X}$ | $\mathbf{A}$ |
|:---------------:|:------------:|:------------:|:------------:|:------------:|:------------:|:------------:|
|  $\mathbf{V}$   |  impossible  |   required   |   required   |   desired    |   desired    |   desired    |
|  $\mathbf{F}$   |  impossible  |  impossible  |   required   |   desired    |   desired    |   desired    |
|  $\mathbf{D}$   |  impossible  |  impossible  |  impossible  |   desired    |   desired    |   desired    |
|  $\mathbf{P}$   |  undesired   |  undesired   |  undesired   |  impossible  |   desired    |   desired    |
|  $\mathbf{X}$   |  undesired   |  undesired   |  undesired   |  undesired   |  impossible  |   desired    |
|  $\mathbf{A}$   |  undesired   |  undesired   |  undesired   |  undesired   |  undesired   |  impossible  |

  : Ordered pairs of events where ${row} \prec {col}$ (Key: - =
  impossible, r = required, d = desired, u = undesired)
:::

Thus far, we have made no assertions about the relative desirability of
any two desiderata (that is, $d_i,d_j \in \mathbb{D}$ where $i \neq j$).
In the next section we will expand the model to include a partial order
over our desiderata, but for now it is sufficient to note that any
simple ordering over $\mathbb{D}$ would remain compatible with the
partial order given in
[\[eq:ordering\]](#eq:ordering){== TODO fix ref to eq:ordering ==}. In fact, a total order on $\mathbb{D}$ would
create a linear extension of the poset defined here, whereas a partial
order on $\mathbb{D}$ would result in a more constrained poset of which
this poset would be a subset.

{== TODO add Hasse Diagram ==}

![The Lattice of Possible CVD Histories: A Hasse Diagram of the partial
ordering $(\mathcal{H}, \leq_{H})$ of $h_a \in \mathcal{H}$ given
$\mathbb{D}$ as defined in
[\[eq:ordering\]](#eq:ordering){== TODO fix ref to eq:ordering ==}. The diagram flows from least desirable
histories at the bottom to most desirable at the top. Histories that do
not share a path are incomparable. Labels indicate the index (row
number) $a$ of $h_a$ in Table
[3.1](#tab:possible_histories){== TODO fix ref to tab:possible_histories ==}.](figures/h_poset.png)
