# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

receive-report-demo-1  | 2026-02-19 16:52:45,944 INFO Initializing inboxes and outboxes for actors...
receive-report-demo-1  | 2026-02-19 16:52:45,944 ERROR Demo 3 failed: 'ActorIO for actor_id finndervul already exists, set `force=True` to override.'
receive-report-demo-1  | Traceback (most recent call last):
receive-report-demo-1  |   File "/app/vultron/scripts/receive_report_demo.py", line 832, in main
receive-report-demo-1  |     finder, vendor, coordinator = setup_clean_environment(client)
receive-report-demo-1  |                                   ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
receive-report-demo-1  |   File "/app/vultron/scripts/receive_report_demo.py", line 778, in setup_clean_environment
receive-report-demo-1  |     init_actor_ios([finder, vendor, coordinator])
receive-report-demo-1  |     ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
receive-report-demo-1  |   File "/app/vultron/scripts/receive_report_demo.py", line 215, in init_actor_ios
receive-report-demo-1  |     init_actor_io(actor.as_id)
receive-report-demo-1  |     ~~~~~~~~~~~~~^^^^^^^^^^^^^
receive-report-demo-1  |   File "/app/vultron/api/v2/data/actor_io.py", line 66, in wrapper
receive-report-demo-1  |     return func(resolved_actor_id, *args, **kwargs)
receive-report-demo-1  |   File "/app/vultron/api/v2/data/actor_io.py", line 85, in init_actor_io
receive-report-demo-1  |     raise KeyError(
receive-report-demo-1  |         f"ActorIO for actor_id {actor_id} already exists, set `force=True` to override."
receive-report-demo-1  |     )
receive-report-demo-1  | KeyError: 'ActorIO for actor_id finndervul already exists, set `force=True` to override.'
receive-report-demo-1  | 2026-02-19 16:52:45,946 INFO ================================================================================
receive-report-demo-1  | 2026-02-19 16:52:45,946 INFO ALL DEMOS COMPLETE
receive-report-demo-1  | 2026-02-19 16:52:45,947 INFO ================================================================================
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR 
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR ================================================================================
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR ERROR SUMMARY
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR ================================================================================
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR Total demos: 3
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR Failed demos: 2
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR Successful demos: 1
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR 
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR Demo 2: Invalidate Report:
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR   'ActorIO for actor_id finndervul already exists, set `force=True` to override.'
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR 
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR Demo 3: Invalidate and Close Report:
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR   'ActorIO for actor_id finndervul already exists, set `force=True` to override.'
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR 
receive-report-demo-1  | 2026-02-19 16:52:45,947 ERROR ================================================================================

---