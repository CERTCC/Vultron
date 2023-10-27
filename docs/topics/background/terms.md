# Terms and Definitions

Throughout this documentation, we refer to CVD Roles from the [*CERT Guide to Coordinated
Vulnerability Disclosure*](https://vuls.cert.org/confluence/display/CVD):

!!! info "Finder"

    The individual or organization that identifies the vulnerability

!!! info "Reporter"

    The individual or organization that notifies the vendor of the
    vulnerability

!!! info "Vendor (Supplier)"

    The individual or organization that created or maintains the
    vulnerable product

The *Vendor* role is synonymous with the *Supplier* role as it appears
in [SSVC](https://github.com/CERTCC/SSVC) Version 2 and above.

!!! info "Deployer (User)"

    The individual or organization that must deploy a patch or take
    other remediation action

The *Deployer* role is synonymous with the *User* role in
[ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html)
and
[ISO/IEC 30111:2019](https://www.iso.org/standard/69725.html),
while the other roles are named consistent with those standards.

!!! info "Coordinator"

    An individual or organization that facilitates the coordinated
    response process

We also add a new role in this documentation, which we expect to incorporate
into a future version of the *CVD Guide*:

!!! info "Exploit Publisher"

    An individual or organization that publishes exploits

Exploit Publishers might be the same as Finders, Reporters, Coordinators, or
Vendors, but this is not guaranteed.
For example, Vendors that produce tools for Cybersecurity Red Teams might play a combination
of roles: Finder, Reporter, Vendor, Coordinator, and/or Exploit Publisher.

Finally, we have a few additional terms to define:

!!! info "CVD Case (Case)"

    The unit of work for the overall CVD process for a specific vulnerability
    spanning the individual CVD Case Participants and their respective processes

!!! info "CVD Case Participant (Participant)"

    Finder, Vendor, Coordinator, Deployer, etc., as defined above

!!! info "Vulnerability Report (Report)"

    The unit of work for an individual Case Participant's [Report Management (RM) process](../process_models/rm/index.md)

A diagram showing the relationship between CVD Cases, Participants, and Reports can be
found in [Case Object](../../howto/case_object.md).
