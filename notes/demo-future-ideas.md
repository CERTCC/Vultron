---
title: Future Demo Ideas
status: draft
description: >
  Speculative future demo scenarios and multi-actor workflow ideas for the
  Vultron prototype.
---

# Future Demo Ideas

## Two-Actor Demo: Finder, Vendor coordinate in separate containers

Two actors, a finder and vendor, running in separate containers,
communicating through the Vultron Protocol. Finder reports vulnerability to
Vendor, and Finder proposes embargo, vendor accepts report, accepts embargo
creates case, adds report and embargo to case, adds finder as case
participant, adds two vulnerabilities to the case based on the report.
They exchange a few messages back and forth, maybe including a draft CVE
record or something like that. This will be a good demo for showing the basic
Vultron Protocol interactions and the behavior tree implementation.

## Three-Actor Demo: Finder, Vendor, Coordinator coordinate in separate containers

A three-actor demo (finder, vendor, coordinator). Finder reports to
coordinator. Coordinator creates case, adds finder as participant.
Coordinator has a default embargo policy that it applies to all cases.
Coordinator proposes embargo to finder, finder accepts. Coordinator adds
embargo to case. Coordinator invites Vendor to case, vendor tentatively
rejects (invalidates the report) with a message back to the Coordinator
asking a question. The Coordinator relays the question to the Finder.
Finder responds to Coordinator, Coordinator replies to vendor with the
Finder's response. Vendor accepts the report and the embargo and becomes
a participant in the case. A few messages are exchanged between the three
actors within the context of the case, including a draft CVE record that
they refine together. The Vendor announces to the case that they have
published, which triggers a case status update reflecting public
awareness. Finder reports they have published as well. Then the
coordinator closes the case.

## MultiParty Demo: Two-Actor expands to Coordinator and more Vendors

A demo in which the process initially looks like scenario 1 above and an
embargo is established, but
then the vendor realizes they need the assistance of a coordinator to get
more vendors engaged. They offer the coordinator the opportunity to take
over the case, and the coordinator accepts. The coordinator becomes the
new case owner, and the original finder and vendor remain participants.
The coordinator then invites two more vendors to the case with the
existing embargo. They accept and become participants. One of the added
vendors asks for the embargo to be extended, which triggers a discussion
between the participants, and they agree to extend the embargo in
principle. The coordinator triggers the case actor to propose a new
embargo with the agreed to terms. Participants agree to the new embargo.
They exchange a few more messages, the coordinator creates a CVE record
and distributes it for refinement. Coordinator and Finder announce
publication, followed quickly by the original vendor and the two added vendors.
The coordinator then closes the case.

Each of these demos would need to show actors running in independent
containers, communicating through the Vultron Protocol, with the CaseActor
managing the case state and enforcing the rules around who can do what within
the case.
CaseActor is probably also a "spin up on demand" container that gets
instantiated when a case is created.
