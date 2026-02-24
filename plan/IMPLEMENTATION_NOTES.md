# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## 2024-02-24 Consider internal vs public representation of key object classes

Our `VulnerabilityCase` object currently representing a custom type of
ActivityStreams object, which allows us to easily translate from the python
pydantic data model to ActivityStreams JSON for message payloads. However,
this design has a few drawbacks, including that it tightly couples our internal representation of
a case to the ActivityStreams format. Where this comes up is in custom
fields like `case_status` and `participant_status` (which will eventually
need to be pluralized to reflect the fact that they are append-only lists
and not single data structures), and the `notes` field, which is also
intended to be an append-only list of note objects. In ActivityStreams, the
way to represent these structures for transport is to use a `Collection` of
objects, or more commonly object references (which is basically a `Link` in
ActivityStreams that acts as a pointer to the actual object. However, in
running code it may make more sense for these to be represented as
lists of pointers to the actual objects, and in data storage they might be
represented as something like a join table or just list of IDs that can be  
resolved at runtime. (Note that we prefer to make things work with no-sql
document or object storage, so we want to avoid designs that require complex
joins or relational database patterns).

The main takeaway here is that we may need to consider a translation layer
between "objects we exchange with others" (wire format) and "objects we use 
internally and persist in our data layer". This is a common pattern in software design, we just
haven't had to address it yet because our prototype started from the
ActivityStreams message format side. This will become increasingly important
as we continue to refine the system, and it may be worth considering sooner
rather than later to avoid having to refactor the core data model later on.
Establishing good patterns early on will help us maintain a clean separation
of concerns and make it easier to evolve the system over time.

---
