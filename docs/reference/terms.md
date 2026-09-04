# Terms and Definitions

This page defines the Coordinated Vulnerability Disclosure (CVD) stakeholder roles and case terms used throughout this documentation.
The canonical source for Vultron domain terminology is the [Glossary](glossary.md).
This page covers the subset of terms that map onto the [*CERT Guide to Coordinated Vulnerability Disclosure*](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"} and the relevant ISO standards, together with the synonyms those sources use.

## CVD Roles

The role names below follow the *CERT Guide to Coordinated Vulnerability Disclosure*.
Each corresponds to a `CVDRole` value in the protocol, except where noted.

!!! info "Reporter"

    The individual or organization that notifies the vendor of the
    vulnerability

*Reporter* is the protocol-salient role for vulnerability discovery: the protocol is concerned with who reported a vulnerability, not with who found it.

!!! info "Finder"

    The individual or organization that identifies the vulnerability

*Finder* is not a distinct protocol role (ADR-0078).
An actor that discovers a vulnerability and reports it holds the *Reporter* role.
An actor that discovers a vulnerability without reporting it is recorded in the report content or in case notes, as metadata rather than as a role.

!!! info "Vendor (Supplier)"

    The individual or organization that created or maintains the
    vulnerable product

The *Vendor* role is synonymous with the *Supplier* role as it appears in [Stakeholder-Specific Vulnerability Categorization (SSVC)](https://github.com/CERTCC/SSVC){:target="_blank"} Version 2 and above.

!!! info "Deployer (User)"

    The individual or organization that must deploy a patch or take
    other remediation action

The *Deployer* role is synonymous with the *User* role in
[ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html){:target="_blank"}
and
[ISO/IEC 30111:2019](https://www.iso.org/standard/69725.html){:target="_blank"}.
The other roles are named consistent with those standards.

!!! info "Coordinator"

    An individual or organization that facilitates the coordinated
    response process

!!! info "Observer"

    A case participant with no vendor fix-and-deployment obligations

*Observer* is the base role — the lowest non-null privilege set — and is admitted through the standard invitation and acceptance flow (ADR-0057).

## Exploit Publisher

This documentation adds one stakeholder role that the *CVD Guide* does not define, and that is expected in a future version of that guide.

!!! info "Exploit Publisher"

    An individual or organization that publishes exploits

*Exploit Publisher* has no corresponding `CVDRole` value.
It describes a behavior the protocol constrains rather than a role a participant holds: an Exploit Publisher participating in a pre-public case is expected to comply with the protocol, and to withhold exploit code while an embargo is active.

An Exploit Publisher may also be a Finder, Reporter, Coordinator, or Vendor, and often is.
A vendor that produces tools for cybersecurity red teams can hold several roles at once: Reporter, Vendor, Coordinator, and Exploit Publisher.

## Units of Work

Three further terms name the units of work in the CVD process.

!!! info "CVD Case (Case)"

    The unit of work for the overall CVD process for a specific vulnerability
    spanning the individual CVD Case Participants and their respective processes

!!! info "CVD Case Participant (Participant)"

    An actor holding one or more CVD Roles in a Case

!!! info "Vulnerability Report (Report)"

    The unit of work for an individual Case Participant's [Report Management (RM) process](../topics/process_models/rm/index.md)

[Case Object](../howto/case_object.md) contains a diagram of the relationships between CVD Cases, Participants, and Reports.
