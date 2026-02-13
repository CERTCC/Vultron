# Priorities

Finishing `scripts/receive_report_demo.py` is the top priority.
The intent of the demo script is to demonstrate the process as described in 
`docs/howto/activitypub/activities/report_vulnerability.md`.
Note that some of the steps in that process are not yet implemented, so there
is still work to be done to finish the demo script. Also note that different
steps in the demo would not make sense to implement in exact sequence, as you
are unlikely to want to "accept", "tentative reject", and "reject" the same
report offer. So it might make more sense to either implement a mechanism to 
reset the state of a report offer, or to implement the three different
outcomes as separate demonstrations that can be run independently. For example,
you might create three different offers, with different IDs, and then accept
one, tentatively reject one, and reject one.


Features that primarily serve to improve production-readiness are lower priority
than any of the above.