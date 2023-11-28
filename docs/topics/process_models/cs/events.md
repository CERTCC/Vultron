# Events in a Vulnerability Lifecycle

{% include-markdown "../../../includes/not_normative.md" %}

Our goal is to create a toy model of the MPCVD process that can shed light on the more
complicated real thing. We begin by building up a state map of what
FIRST refers to as bilateral CVD [@first2020mpcvd], which we will later
expand into the MPCVD space. We start by defining a set of
events of interest. We then use these to construct model states and the
transitions between them.

## Define Events

The goal of this section is to establish a model of events that affect
the outcomes of vulnerability disclosure. Our model builds on previous
models of the vulnerability lifecycle, specifically those of Arbaugh et
al. [@arbaugh2000windows], Frei et al. [@frei2010modeling], and Bilge
and et al. [@bilge2012before]. A more thorough literature review of
vulnerability lifecycle models can be found in [@lewis2017global]. We
are primarily interested in events that are usually observable to the
stakeholders of a CVD case. Stakeholders include software
vendors, vulnerability finder/reporters, coordinators, and
deployers [@householder2017cert]. A summary of this model comparison is
shown in the Table below.

| Arbaugh et al.[@arbaugh2000windows] | Frei et al.[@frei2010modeling] | Bilge et al. [@bilge2012before] | Our Model |
| ----------------------------------- | ------------------------------ | ------------------------------- | --------- |
| Birth                               | creation ($t_{creat}$)         | introduced ($t_c$)              | (implied) |
| Discovery                           | discovery ($t_{disco}$)        | n/a                             | (implied) |
| Disclosure                          | n/a                            | discovered by vendor ($t_d$)    | ($\mathbf{V}$) |
| n/a | patch availability ($t_{patch}$) | n/a | Fix Ready ($\mathbf{F}$) |
| Fix Release | n/a | patch released ($t_p$) | Fix Ready and Public Awareness |
| Publication | public disclosure ($t_{discl}$) | disclosed publicly ($t_0$) | Public Awareness ($\mathbf{P}$) |
| n/a | patch installation ($t_{insta}$) | patch deployment completed ($t_a$) | Fix Deployed ($\mathbf{D}$) |
| Exploit Automation | exploit availability ($t_{explo}$) | Exploit released in wild ($t_e$) | n/a |
| Exploit Automation | n/a | n/a | Exploit Public ($\mathbf{X}$) |
| Exploit Automation | n/a | n/a | Attacks Observed ($\mathbf{A}$) |
| n/a | n/a | anti-virus signatures released ($t_s$) | n/a |

Vulnerability Lifecycle Events: Comparing Models. Symbols for our model are defined in §[2.4](#sec:transitions){== TODO fix ref to sec:transitions ==}.

Since we are modeling only the disclosure process, we assume the
vulnerability both exists and is known to at least someone. Therefore we
ignore the *birth* (*creation*, *introduced*) and *discovery* states as
they are implied at the beginning of all possible vulnerability
disclosure histories. We also omit the *anti-virus signatures released*
event from [@bilge2012before] since we are not attempting to model
vulnerability management operations in detail.

### Vendor Awareness

The first event we are interested in modeling is *Vendor Awareness*.
This event corresponds to *Disclosure* in [@arbaugh2000windows] and
*vulnerability discovered by vendor* in [@bilge2012before] (this event
is not modeled in [@frei2010modeling]). In the interest of model
simplicity, we are not concerned with *how* the vendor came to find out
about the vulnerability's existence---whether it was found via internal
testing, reported by a security researcher, or noticed as the result of
incident analysis.

### Public Awareness

The second event we include is *Public Awareness* of the vulnerability.
This event corresponds to *Publication* in [@arbaugh2000windows], *time
of public disclosure* in [@frei2010modeling], and *vulnerability
disclosed publicly* in [@bilge2012before]. The public might find out
about a vulnerability through the vendor's announcement of a fix, a news
report about a security breach, a conference presentation by a
researcher, by comparing released software versions as
in [@xu2020patch; @xiao2020mvp], or a variety of other means. As above,
we are primarily concerned with the occurrence of the event itself
rather than the details of *how* the public awareness event arises.

### Fix Readiness and Deployment
The third event we address is *Fix Readiness*, by which we refer to the
vendor's creation and possession of a fix that *could* be deployed to a
vulnerable system, *if* the system owner knew of its existence. Here we
differ somewhat
from [@arbaugh2000windows; @frei2010modeling; @bilge2012before] in that
their models address the *release* of the fix rather than its
*readiness* for release.

The reason for this distinction will be made clear, but first we must
mention that *Fix Deployed* is simply that: the fix exists, and it has
been deployed.

We chose to include the *Fix Ready*, *Fix Deployed*, and *Public
Awareness* events so that our model could better accommodate two common
modes of modern software deployment:

-   *shrinkwrap* - The traditional distribution mode in which the vendor
    and deployer are distinct entities and deployers must be made aware
    of the fix before it can be deployed. In this case, which
    corresponds to the previously mentioned *fix release* event, both
    fix readiness and public awareness are necessary for the fix to be
    deployed.

-   *SaaS* - A more recent delivery mode in which the vendor also plays
    the role of deployer. In this distribution mode, fix readiness can
    lead directly to fix deployed with no dependency on public
    awareness.

We note that so-called *silent fixes* by vendors can sometimes result in
a fix being deployed without public awareness even if the vendor is not
the deployer. Thus, it is possible (but unlikely) for *fix deployed* to
occur before *public awareness* even in the *shrinkwrap* case above. It
is also possible, and somewhat more likely, for *public awareness* to
occur before *fix deployed* in the *SaaS* case as well.

### Exploit Public and Attacks Observed
We diverge
from [@arbaugh2000windows; @frei2010modeling; @bilge2012before] again in
our treatment of exploits and attacks. Because attacks and exploit
publication are often discretely observable events, the broader concept
of *exploit automation* in [@arbaugh2000windows] is insufficiently
precise for our use. Both [@frei2010modeling; @bilge2012before] focus on
the availability of exploits rather than attacks, but the observability
of their chosen events is hampered by attackers' incentives to maintain
stealth. Frei et al. [@frei2010modeling] uses *exploit availability*,
whereas Bilge et al. [@bilge2012before] calls it *exploit released in
wild*. Both refer to the state in which an exploit is known to exist.
This can arise for at least two distinct reasons, which we wish to
differentiate:

-   *exploit public*---the method of exploitation for a vulnerability
    was made public in sufficient detail to be reproduced by others.
    Posting PoC
    code to a widely available site or including the exploit in a
    commonly available exploit tool meets this criteria; privately held
    exploits do not.

-   *attacks observed*---the vulnerability was observed to be exploited
    in attacks. This case requires evidence that the vulnerability was
    exploited; we can then presume the existence of an exploit
    regardless of its availability to the public. Analysis of malware
    from an incident might meet *attacks observed* but not *exploit
    public*, depending on how closely the attacker holds the malware.
    Use of a public exploit in an attack meets both *exploit public* and
    *attacks observed*.

Therefore, while we appreciate the existence of a hidden *exploit
exists* event as causal predecessor of both *exploit public* and
*attacks observed*, we assert no causal relationship between exploit
public and attacks observed in our model. We make this choice in the
interest of observability. The *exploit exists* event is difficult to
consistently observe independently. Its occurrence is nearly always
inferred from the observation of either *exploit public* or *attacks
observed*.

Further discussion of related work can be found in
§[7](#sec:related_work){== TODO fix ref to sec:related_work ==}.
