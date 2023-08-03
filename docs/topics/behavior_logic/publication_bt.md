## Publication Behavior {#sec:publication_bt}

The Publication Behavior Tree is shown in Figure
[\[fig:bt_publication\]](#fig:bt_publication){reference-type="ref"
reference="fig:bt_publication"}. It begins by ensuring that the
Participant knows what they intend to publish, followed by a check to
see if that publication has been achieved. Assuming that work remains to
be done, the main publish sequence commences on the right-hand branch.

The process begins with preparation for publication, described in
§[1.5.4.1](#sec:prepare_publication_bt){reference-type="ref"
reference="sec:prepare_publication_bt"}, followed by a pre-publication
embargo check. This behavior is a simple check to ensure that no embargo
remains active prior to publication. Note that the embargo management
process may result in early termination of an existing embargo if the
Participant has sufficient cause to do so. (See the detailed description
of the EM behavior in{== §[1.4](#sec:em_bt){reference-type="ref"
reference="sec:em_bt"} ==}.)

Once these subprocesses complete, the publish task fires, the case state
is updated to $q^{cs} \in P$, and a $CP$ message emits.

### Prepare Publication Behavior {#sec:prepare_publication_bt}

The Prepare Publication Behavior Tree is shown in Figure
[\[fig:bt_prepare_publication\]](#fig:bt_prepare_publication){reference-type="ref"
reference="fig:bt_prepare_publication"}. There are separate branches for
publishing exploits, fixes, and reports. The publish exploit branch
succeeds if either no exploit publication is intended, if it is intended
and ready, or if it can be acquired and prepared for publication. The
publish fix branch succeeds if the Participant does not intend to
publish a fix (e.g., if they are not the Vendor), if a fix is ready, or
if it can be developed and prepared for publication. The publish report
branch is the simplest and succeeds if either no publication is intended
or if the report is ready to go.

Once all three branches have completed, the behavior returns *Success*.

