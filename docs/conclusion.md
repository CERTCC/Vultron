# Conclusion {#ch:conclusion}

!!! note "TODO"
    - [ ] regex replace acronym pointers with the acronym
    - [ ] replace first use of an acronym on a page with its expansion (if not already done)
    - [ ] OR replace acronym usage with link to where it's defined
    - [ ] reproduce diagrams using mermaid
    - [ ] replace text about figures to reflect mermaid diagrams
    - [ ] replace latex tables with markdown tables
    - [ ] replace some equations with diagrams (especially for equations describing state changes)
    - [ ] move latex math definitions into note blocks `???+ note _title_` to offset from text
    - [ ] move MUST SHOULD MAY etc statements into note blocks with empty title `!!! note ""` to offset from text
    - [ ] revise cross-references to be links to appropriate files/sections
    - [ ] replace latex citations with markdown citations (not sure how to do this yet)
    - [ ] review text for flow and readability as a web page
    - [ ] add section headings as needed for visual distinction
    - [ ] add links to other sections as needed
    - [ ] add links to external resources as needed
    - [ ] replace phrases like `this report` or `this section` with `this page` or similar
    - [ ] add `above` or `below` for in-page cross-references if appropriate (or just link to the section)
    - [ ] reduce formality of language as needed
    - [ ] move diagrams to separate files and `include-markdown` them

In this report, we described a proposal for an
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} protocol in
the interest of improving the interoperability of the world's
[CVD]{acronym-label="CVD" acronym-form="singular+short"} processes. Our
working name for this protocol is *Vultron*, intended to evoke the
coordination and cooperation required to assemble five robot lions and
their pilots into an ad hoc collective entity in defense against a
shared adversary.

Our proposal is built on three primary processes, each modeled as
[DFAs]{acronym-label="DFA" acronym-form="plural+short"}:

1.  the [RM]{acronym-label="RM" acronym-form="singular+short"} process
    model in
    §[\[sec:report_management\]](#sec:report_management){reference-type="ref"
    reference="sec:report_management"}

2.  the [EM]{acronym-label="EM" acronym-form="singular+short"} process
    model in §[\[ch:embargo\]](#ch:embargo){reference-type="ref"
    reference="ch:embargo"}

3.  the [CS]{acronym-label="CS" acronym-form="singular+short"} process
    model in §[\[sec:model\]](#sec:model){reference-type="ref"
    reference="sec:model"}, as originally described by Householder and
    Spring  [@householder2021state]

We discussed the interactions between these three
[DFAs]{acronym-label="DFA" acronym-form="plural+short"} in
§[\[ch:interactions\]](#ch:interactions){reference-type="ref"
reference="ch:interactions"}. Then, we combined them into a single
formal [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
protocol in
§[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"}, which we concluded with an example of
the proposed protocol in action.

We modeled the behavior of an individual [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} Participant in
§[\[ch:behavior_trees\]](#ch:behavior_trees){reference-type="ref"
reference="ch:behavior_trees"} as a nested set of Behavior Trees. The
modularity of Behavior Trees allows for various Participants to be
modeled as agents, which serves two purposes. First, it identifies
increased automation of portions of the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} process, improving the potential for
human-machine hybrid [CVD]{acronym-label="CVD"
acronym-form="singular+short"} processes in the future. Second, it
provides a means to model Participant behaviors in software, which can
facilitate [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
process simulation and optimization at a scale previously unknown.

The implementation notes in
§[\[ch:implementation notes\]](#ch:implementation notes){reference-type="ref"
reference="ch:implementation notes"} and the future work outlined in
§[\[ch:future_work\]](#ch:future_work){reference-type="ref"
reference="ch:future_work"} set an agenda for
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process
improvement research and development for the near future.

Finally, the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol proposed in this report---in
conjunction with the *CERT Guide to Coordinated Vulnerability
Disclosure* [@householder2017cert; @cert2019cvd] and
*[SSVC]{acronym-label="SSVC"
acronym-form="singular+short"}* [@spring2019ssvc; @spring2020ssvc; @spring2021ssvc]---is
intended to paint as complete a picture as possible of the
[CERT/CC]{acronym-label="CERT/CC" acronym-form="singular+short"}'s
current understanding of how [CVD]{acronym-label="CVD"
acronym-form="singular+short"} should be performed.

Ready to form Vultron!
