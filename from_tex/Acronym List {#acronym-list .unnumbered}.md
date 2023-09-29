# Acronym List {#acronym-list .unnumbered}

::: acronym
\[ATT&CK\]Adversarial Tactics, Techniques, and Common Knowledge
\[CNA\][CVE]{acronym-label="CVE" acronym-form="singular+short"}
Numbering Authority \[CNAs\][CVE]{acronym-label="CVE"
acronym-form="singular+short"} Numbering Authorities \[IODEF+\]Incident
Object Description Exchange Format Extensions

\[SANS Institute\]Sysadmin, Audit, Network, and Security Institute
\[US-CERT\][US]{acronym-label="US" acronym-form="singular+abbrv"}
Computer Emergency Readiness Team
:::

[^1]: Specifically, skill in our model will align with fulfilling the
    duty of coordinated vulnerability disclosure, duty of
    confidentiality, duty to inform, duty to team ability, and duty of
    evidence-based reasoning.

[^2]: CERT/CC Vulnerability Information and Coordination Environment
    (VINCE). <https://www.kb.cert.org/vince/>

[^3]: Although we do believe there is some value in exploit publication
    because it allows defenders to develop detection controls (e.g., in
    the form of behavioral patterns or signatures). Even if those
    detection mechanisms are imperfect, it seems better that they be in
    place prior to adversaries using them than the opposite.

[^4]: <https://www.zerodayinitiative.com/blog>. The ZDI blog posts were
    more directly useful than the monthly Microsoft security updates
    because ZDI had already condensed the counts of how many
    vulnerabilities were known ($\mathbf{P}$) or exploited
    ($\mathbf{A}$) prior to their fix readiness $\mathbf{F}$. Retrieving
    this data from Microsoft's published vulnerability information
    requires collecting it from all the individual vulnerabilities
    patched each month. We are grateful to ZDI for providing this
    summary and saving us the effort.

[^5]: Borrowing the terminology of quantum mechanics

[^6]: On the other hand, some vendors might actually prefer public
    awareness before fix deployment even if they have the ability to
    deploy fixes, for example in support of transparency or trust
    building. In that case, $\mathbb{D_V} \not\subseteq \mathbb{D}$, and
    some portions of the analysis presented here may not apply.

[^7]: "Silent patches" can obviously occur when vendors fix a
    vulnerability but do not make that fact known. In principle, silent
    patches could achieve $\mathbf{D} \prec \mathbf{P}$ even in
    traditional COTS or OSS distribution models. However, in practice
    silent patches result in poor deployment rates precisely because
    they lack an explicit imperative to deploy the fix.

[^8]: A [CVD]{acronym-label="CVD" acronym-form="singular+short"} embargo
    is analogous to a news embargo used in journalism, often in the
    context of scientific publications. Like [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} embargoes, the use of scientific news
    embargoes is not without controversy.
    [@angell1991ingelfinger; @delkic2018embargo; @oransky2016embargo]

[^9]: It is of course appropriate to use discretion as to how much
    detail is released.

[^10]: Public awareness notwithstanding, an engaged adversary can begin
    using a public exploit as soon as it becomes available.

[^11]: The phrase *zero day* means many things to many people. We
    provide more formal definitions in
    §[6.5](#sec:defining_common_terms){reference-type="ref"
    reference="sec:defining_common_terms"}

[^12]: User concentration is one way to think about risk, but it is not
    the only way. Value density, as defined in [@spring2020ssvc] is
    another.

[^13]: We also admit our omission from consideration of whether
    utilitarianism is even the best way to approach these problems; and
    if it is, which variety of utilitarianism may be best suited. Such
    topics, while both interesting and relevant, lie too far afield from
    our main topic for us to to them justice here. We direct interested
    readers toward [@sep-utilitarianism-history] as an introduction to
    the general topic.

[^14]: https://ethicsfirst.org/
