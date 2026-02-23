# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

Many of the demo scripts in `vultron/scripts` do not have tested dockerized
implementations. This is a problem because it means that the demos are not yet
self-contained and cannot be run by users without additional setup. See 
`plan/PRIORITIES.md` for more details on the importance of dockerizing the demos.

There may in fact be two problems here:
1) There may not be full pytest coverage for the demo scripts, which means 
   that we cannot be sure they are working as intended.
2) The dockerization of the demo scripts is not complete, which means we
   cannot reliably demonstrate to users that the backend API is working as intended.

---


