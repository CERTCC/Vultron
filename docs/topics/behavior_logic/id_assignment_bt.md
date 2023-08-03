## CVE ID Assignment Behavior {#sec:assign_id_bt}

Many CVD
practitioners want to assign identifiers to the vulnerabilities they
coordinate. The most common of these is a CVE ID, so we provide an example CVE ID
Assignment Behavior Tree, shown in Figure
[\[fig:bt_cve_assignment\]](#fig:bt_cve_assignment){reference-type="ref"
reference="fig:bt_cve_assignment"}. While this tree is constructed
around the CVE ID
assignment process, it could be easily adapted to any other identifier
process as well.

The goal is to end with an ID assigned. If that has not yet happened,
the first check is whether the vulnerability is in scope for an ID
assignment. If it is, the Participant might be able to assign IDs
directly, assuming they are a CNA and the vulnerability meets the criteria
for assigning IDs.

Otherwise, if the Participant is not a CNA, they will have to request an ID from a
CNA.

Should both assignment branches fail, the behavior fails. Otherwise, as
long as one of them succeeds, the behavior succeeds.

