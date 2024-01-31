# Related Work

Numerous models of the vulnerability life cycle and
CVD have been proposed.

- [Arbaugh, Fithen, and McHugh](https://doi.org/10.1109/2.889093)
provide a descriptive model of the
life cycle of vulnerabilities from inception to attacks and remediation, which we refined with those of
[Frei et al.](https://doi.org/10.1007/978-1-4419-6967-5_6), and [Bilge et al.](https://doi.org/10.1145/2382196.2382284) to form the
basis of this model as described in
§[2.1](#sec:events){== TODO fix ref to sec:events ==}.
- We also found
[Lewis' literature review of vulnerability lifecycle models](http://dspace.lib.cranfield.ac.uk/handle/1826/12665) to
be useful.

Prescriptive models of the CVD process have also been proposed.

- [Christey
and Wysopal's 2002 IETF draft](https://datatracker.ietf.org/doc/html/draft-christey-wysopal-vuln-disclosure-00)
laid out a process for responsible
disclosure geared towards prescribing roles, responsibilities for
researchers, vendors, customers, and the security community.

- The [NIAC Vulnerability Disclosure Framework](https://www.dhs.gov/xlibrary/assets/vdwgreport.pdf)
also prescribed a process for coordinating the disclosure and
remediation of vulnerabilities.

- The [CERT Guide to Coordinated Vulnerability Disclosure](https://vuls.cert.org/confluence/display/CVD) provides a practical overview of
the CVD process.
- ISO/IEC 29147 describes standard externally-facing processes for vulnerability disclosure from the
perspective of a vendor receiving vulnerability reports, while ISO/IEC
30111 describes internal vulnerability handling processes within a
vendor{== TODO replace ref with link ==} [@ISO29147; @ISO30111].
- The FIRST *PSIRT Services Framework* provides a practical
description of the capabilities common to vulnerability response within
vendor organizations [@first2020psirt]{== TODO replace ref with link ==}.
- The FIRST *Guidelines
and Practices for Multi-Party Vulnerability Coordination and Disclosure*
provides a number of scenarios for MPCVD [@first2020mpcvd]{== TODO replace ref with link ==}. Many of these
scenarios can be mapped directly to the histories $h \in H$ described in
§[6.2](#sec:mpcvd){== TODO fix ref to sec:mpcvd ==}.

- Benchmarking CVD
capability is the topic of the VCMM from Luta Security [@luta2020]{== TODO replace ref with link ==}. The
VCMM addresses
five capability areas: organizational, engineering, communications,
analytics, and incentives. Of these, our model is perhaps most relevant
to the analytics capability, and the metrics described in
§[5](#sec:skill_luck){== TODO fix ref to sec:skill_luck ==}
could be used to inform an organization's assessment of progress in this
dimension. Concise description of case states using the model presented
here could also be used to improve the communications dimension of the
VCMM.

System dynamics and agent based models have been applied to the
interactions between the vulnerability discovery, disclosure, and
remediation processes.

- Ellis et al. analyzed the composition of the
labor market for bug bounty programs, finding that a small core of
high-volume reporters earn most of the bounties while a much larger
group are infrequent low-volume reporters [@ellis2018fixing]{== TODO replace ref with link ==}.
- Lewis
modeled the interaction of social and economic factors in the global
vulnerability discovery and disclosure system [The global vulnerability discovery and disclosure system: a thematic system dynamics approach](http://dspace.lib.cranfield.ac.uk/handle/1826/12665) by P. S. Lewis.{== TODO replace ref with link ==}. The
key systemic themes identified include:

> Perception of Punishment; Vendor Interactions; Disclosure Stance;
> Ethical Considerations; Economic factors for Discovery and Disclosure
> and Emergence of New Vulnerability Markets

- Moore and Householder modeled cooperative aspects of the
MPCVD process,
noting, \"it appears that adjusting the embargo period to increase the
likelihood that patches can be developed by most vendors just in time is
a good strategy for reducing cost\"[@moore2019multi]{== TODO replace ref with link ==}.

Economic analysis of CVD has also been done.

- Arora et al. explored the CVD process
from an economic and social welfare
perspective [@arora2005economics; @arora2006does; @arora2006research; @arora2008optimal; @arora2010competition; @arora2010empirical]{== TODO replace ref with link ==}.
- More recently, so did Silfversten [@silfversten2018economics]{== TODO replace ref with link ==}.
- Cavusoglu and Cavusoglu model the mechanisms involved in motivating vendors to
produce and release patches [@cavusoglu2007efficiency]{== TODO replace ref with link ==}.
- Ellis et al.
examined the dynamics of labor market for bug bounties both within and
across CVD programs
[@ellis2018fixing]{== TODO replace ref with link ==}.
- Pupillo et al. explored the policy implications of
CVD in Europe [@pupillo2018software]{== TODO replace ref with link ==}.
- A model for prioritizing vulnerability response
that considers $\mathbf{X}$ and $\mathbf{A}$, among other impact
factors, can be found in Spring et al. [@spring2020ssvc]{== TODO replace ref with link ==}.

Other work has examined the timing of events in the lifecycle, sometimes
with implications for forecasting.

- Ozment and Schechter examined the
rate of vulnerability reports as software ages [@ozment2006milk]{== TODO replace ref with link ==}.
- Bilge
and Dumitraş studied 18 vulnerabilities in which
${pa} \xrightarrow{\mathbf{A}} {pA} \xrightarrow{\mathbf{P}} {PA}$,
finding a lag of over 300 days [Bilge et al.](https://doi.org/10.1145/2382196.2382284){== TODO replace ref with link ==}.
- Jacobs et al.
proposed an Exploit Prediction Scoring System [@jacobs2020epss]{== TODO replace ref with link ==}, which
could provide insight into the relative frequencies of

$$\begin{aligned}
{vfda} \xrightarrow{\mathbf{V}} {Va} \xrightarrow{\mathbf{A}} {VA}
&\textrm{ vs. }
{vfda} \xrightarrow{\mathbf{A}} {vA} \xrightarrow{\mathbf{V}} {VA} \\
{fda} \xrightarrow{\mathbf{F}} {Fa} \xrightarrow{\mathbf{A}} {FA}
&\textrm{ vs. }
{fda} \xrightarrow{\mathbf{A}} {fA} \xrightarrow{\mathbf{F}} {FA}
\end{aligned}$$

and possibly other transitions.

Future work might apply similar measurements of state subset populations
over time to put better bounds on state transition probabilities than
our simplified assumption of uniformity. Some possible starting points
for such analysis follow.

- Householder et al. found that only about 5% of vulnerabilities have
public exploits available via commodity tools. However, for those that
do, the median lag between transitions in
${px} \xrightarrow{\mathbf{P}} {Px} \xrightarrow{\mathbf{X}} {PX}$ was 2
days [@householder2020historical]{== TODO replace ref with link ==}.
- Frei et al. describe the timing of many of the events here, including
$\mathbf{F}$, $\mathbf{D}$, $\mathbf{X}$, $\mathbf{P}$, and the elapsed
time between them for the period 2000-2007 across a wide swath of
industry [Frei et al.](http://dx.doi.org/10.1007/978-1-4419-6967-5_6){== TODO replace ref with link ==}. Their analysis finds that
${px} \xrightarrow{\mathbf{X}} {pX} \xrightarrow{\mathbf{P}} {PX}$ in
15% of the vulnerabilities they analyzed, leaving 85% on the
${px} \xrightarrow{\mathbf{P}} {Px} \xrightarrow{\mathbf{X}} {PX}$ path.
Similarly, they report that a patch is available on or before the date
of public awareness in 43% of vulnerabilities. In other words, they find
that ${fp} \xrightarrow{\mathbf{F}} {Fp} \xrightarrow{\mathbf{P}} {FP}$
43% of the time, implying that
${fp} \xrightarrow{\mathbf{P}} {fP} \xrightarrow{\mathbf{F}} {FP}$ 57%
of the time.
