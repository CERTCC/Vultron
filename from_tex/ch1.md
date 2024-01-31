# Introduction

Software vulnerabilities remain pervasive. To date, there is little
evidence that we are anywhere close to equilibrium between the
introduction and elimination of vulnerabilities in deployed systems. The
practice of CVD
emerged as part of a growing consensus to develop normative behaviors in
response to the persistent fact of vulnerable software. Yet while the
basic principles of CVD have been established
[@christey2002responsible; @ISO29147; @householder2017cert; @ncsc2018cvd],
there has been limited work to measure the efficacy of
CVD programs,
especially at the scale of industry benchmarks. ISO 29147 [@ISO29147]
sets out the goals of vulnerability disclosure:

> a\) ensuring that identified vulnerabilities are addressed;\
> b) minimizing the risk from vulnerabilities;\
> c) providing users with sufficient information to evaluate risks from
> vulnerabilities to their systems;\
> d) setting expectations to promote positive communication and
> coordination among involved parties.

Meanwhile, the use of third party libraries and shared code components
across vendors and their products creates a need to coordinate across
those parties whenever a vulnerability is found in a shared component.
While it can be difficult for stakeholders to ascertain the prevalence
of components across products---and efforts such as the
NTIA's
SBOM [@ntia_sbom]
are working to address the informational aspects of that problem---our
concern here is the coordination of multiple parties in responding to
the vulnerability.

MPCVD is a more
complex form of CVD, involving the necessity to coordinate
numerous stakeholders in the process of recognizing and fixing
vulnerable products. Initial guidance from the
FIRST acknowledges
the additional complexity that can arise in
MPCVD
cases [@first2020mpcvd]. The need for MPCVD arises from the complexities of the
software supply chain. Its importance was illustrated by the Senate
hearings about the Meltdown and Spectre
vulnerabilities [@wired2018senate]. Nevertheless, the goals of
CVD apply to
MPCVD, as the
latter is a generalization of the former.

The difficulty of MPCVD derives from the diversity of its
stakeholders: different software vendors have different development
budgets, schedules, tempos, and analysis capabilities to help them
isolate, understand, and fix vulnerabilities. Additionally, they face
diverse customer support expectations and obligations, plus an
increasing variety of regulatory regimes governing some stakeholders but
not others. For these reasons and many others, practitioners of
MPCVD highlight
*fairness* as a core difficulty in coordinating disclosures across
vendors [CERT Guide to CVD](https://vuls.cert.org/confluence/display/CVD).

With the goal of minimizing the societal harm that results from the
existence of a vulnerability in multiple products spread across multiple
vendors, our motivating question is, "What does *fair* mean in
MPCVD?"
Optimizing MPCVD
directly is not currently possible, as we lack a utility function to map
from the events that occur in a given case to the impact that case has
on the world. While this document does not fully address that problem,
it sets out a number of steps toward a solution. We seek a way to sort
MPCVD cases into
better outcomes or worse outcomes. Ideally, the sorting criteria should
based on unambiguous principles that are agreed upon and intelligible by
all interested parties. Further, we seek a way to measure relevant
features across MPCVD cases. Feature observability is a key
factor: our measurement needs to be simple and repeatable without overly
relying on proprietary or easily hidden information.

While a definition of *fairness* in MPCVD is a responsibility for the broader
community, we focus on evaluating the skill of the coordinator. We
expect this contributes to fairness based on the EthicsfIRST principles
of ethics for incident response teams promoted by
FIRST
[@first2019ethics].[^1] To that end, our research questions are:

RQ1

:   : Construct a model of CVD states amenable to analysis and also
    future generalization to MPCVD.

RQ2

:   : What is a reasonable baseline expectation for ordering of events
    in the model of CVD?

RQ3

:   : Given this baseline and model, does CVD as observed "in the wild" demonstrate
    skillful behavior?

This paper primarily focuses on the simpler case of
CVD, with some
initial thoughts towards extending it to MPCVD. This focus provides an opportunity for
incremental analysis of the success of the model; more detailed
MPCVD modeling
can follow in future work.

## Approach

The CERT/CC has
a goal to improve the MPCVD process. Improvement involves automation.
The creation of VINCE[^2] is a significant step toward this goal, as it
has helped us to recognize gaps in our own processes surrounding the
MPCVD services we
provide. As part of the SEI at CMU, we also recognize that automation is
made better when we can formalize process descriptions. In this report,
we construct a toy model of the CVD process with the interest of a better
understanding of how it might be formalized.

Our intent with this report is not to provide a complete solution to
automate either CVD
or MPCVD. Rather,
this report is an attempt to systematize the basics in a way that can be
extended by future work toward the specification of protocols that
facilitate the automation of coordination tasks within
MPCVD.

The model presented here provides a foundation on which we might build
an MPCVD
protocol. While we stop well short of a full protocol spec, we feel that
this report contributes to improved understanding of the problems that
such a protocol would need to address. And although an actual protocol
would need to support a far more complicated process (i.e., the
coordination and resolution of actual MPCVD cases), our contention is that we should
be able to derive and learn quite a few of the basics from this toy
model. A protocol that works on the toy model might not work in the real
world. But any proposed real-world protocol should probably work on the
toy model. The model is intended to be a sort of minimum acceptance test
for any future protocol---if a proposed MPCVD process doesn't improve outcomes even in
the toy model, one might wonder what it *is* doing.

## Organization of This Document

We begin by deriving a model of all possible CVD case states and histories from first
principles in §[2](#sec:model){== TODO fix ref to sec:model ==} and §[3](#sec:poss_hist){== TODO fix ref to sec:poss_hist ==}, organizing those histories into a partial
ordering based on a set of desired criteria in
§[4](#sec:reasoning){== TODO fix ref to sec:reasoning ==}. We
then compute a baseline expectation for the frequency of each desired
criteria and propose a new set of performance indicators to measure the
efficacy of CVD
practices based on the differentiation of skill and luck in observation
data in §[5](#sec:skill_luck){== TODO fix ref to sec:skill_luck ==}. As a proof of concept, we apply these
indicators to a variety of longitudinal observations of
CVD practice and
find evidence of significant skill to be prevalent. In
§[6](#sec:discussion){== TODO fix ref to sec:discussion ==},
we explore some of the implications and uses of such a model in any
CVD case before
extending it to MPCVD. The remainder of that section offers
reflections on how this model and its accompanying performance
indicators could be used by various stakeholders (vendors, system
owners, coordinators, and governments) to interpret the quality of their
CVD and
MPCVD practices
We continue with a review of related work in
§[7](#sec:related_work){== TODO fix ref to sec:related_work ==}, future work in
§[8](#sec:limitationsAnd){== TODO fix ref to sec:limitationsAnd ==}, and give our conclusions in
§[9](#sec:conclusion){== TODO fix ref to sec:conclusion ==}.

An appendix summarizing each state in the model in conjunction with the
discussion in §[6](#sec:discussion){== TODO fix ref to sec:discussion ==} is also provided.
