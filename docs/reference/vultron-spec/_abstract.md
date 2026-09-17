## Abstract

The Vultron Protocol coordinates vulnerability disclosure among multiple
organizations. Participants exchange asynchronous messages and track the case
across four dimensions of shared state, realized as five state machines. Any
number of organizations may take part in a single case.

Coordination is scoped to the case rather than to a system: the case-management
role is held per case, and different cases may be managed by different actors. No
single service holds every case. Within a case, one participant holds write
authority over the case's shared state, so that concurrent claims resolve to one
answer.

---
