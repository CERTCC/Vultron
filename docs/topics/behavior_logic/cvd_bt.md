## CVD Behavior Tree {#sec:cvd_bt}

We begin at the root node of the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Behavior Tree shown in Figure
[\[fig:bt_cvd_process\]](#fig:bt_cvd_process){reference-type="ref"
reference="fig:bt_cvd_process"}. The root node is a simple loop that
continues until an interrupt condition is met, representing the idea
that the [CVD]{acronym-label="CVD" acronym-form="singular+short"}
practice is meant to be continuous. In other words, we are intentionally
not specifying the interrupt condition.

The main sequence is comprised of four main tasks:

-   *Discover vulnerability.* Although not all Participants have the
    ability or motive to discover vulnerabilities, we include it as a
    task here to call out its importance to the overall
    [CVD]{acronym-label="CVD" acronym-form="singular+short"} process. We
    show in §[1.2](#sec:receive_reports_bt){reference-type="ref"
    reference="sec:receive_reports_bt"} that this task returns *Success*
    regardless of whether a vulnerability is found to allow execution to
    pass to the next task.

-   *Receive messages*. All coordination in [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} between Participants is done through
    the exchange of messages, regardless of how those messages are
    conveyed, stored, or presented. The receive messages task represents
    the Participant's response to receiving the various messages defined
    in Chapter
    [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
    reference="sec:formal_protocol"}. Due to the degree of detail
    required to cover all the various message types, decomposition of
    this task node is deferred until
    §[1.6](#sec:receive messages){reference-type="ref"
    reference="sec:receive messages"} so we can cover the next two items
    first.

-   *Report management.* This task embodies the [RM]{acronym-label="RM"
    acronym-form="singular+short"} process described in Chapter
    [\[sec:report_management\]](#sec:report_management){reference-type="ref"
    reference="sec:report_management"} as integrated into the
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    protocol of Chapter
    [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
    reference="sec:formal_protocol"}. The [RM]{acronym-label="RM"
    acronym-form="singular+short"} Behavior Tree is described in
    §[1.3](#sec:rm_bt){reference-type="ref" reference="sec:rm_bt"}.

-   *Embargo management.* Similarly, this task represents the
    [EM]{acronym-label="EM" acronym-form="singular+short"} process from
    Chapter [\[ch:embargo\]](#ch:embargo){reference-type="ref"
    reference="ch:embargo"} as integrated into the
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    protocol of Chapter
    [\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
    reference="sec:formal_protocol"}. The [EM]{acronym-label="EM"
    acronym-form="singular+short"} Behavior Tree is decomposed in
    §[1.4](#sec:em_bt){reference-type="ref" reference="sec:em_bt"}

A further breakdown of a number of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} tasks that fall outside the scope of the
formal [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
protocol of Chapter
[\[sec:formal_protocol\]](#sec:formal_protocol){reference-type="ref"
reference="sec:formal_protocol"} can be found in
§[1.5](#sec:do_work){reference-type="ref" reference="sec:do_work"}. In
that section, we examine a number of behaviors that Participants may
include as part of the work they do for reports in the $Accepted$
[RM]{acronym-label="RM" acronym-form="singular+short"} state
($q^{rm}\in A$).

Behaviors and state changes resulting from changes to the
[CS]{acronym-label="CS" acronym-form="singular+short"} model are
scattered throughout the other Behavior Trees where relevant.

