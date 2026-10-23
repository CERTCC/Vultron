## Annex B — Worked Example: Multi-Party CVD [I]

This annex extends Annex A to a case with a coordinator and a second vendor.
It shows the coordinator acting as proxy for the reporter, a participant joining a case that already has an active embargo, and the teardown-publish-close sequence across three parties.

{% include-markdown "../../tutorials/worked_example.md" start="<!-- multi-party-start -->" end="<!-- multi-party-end -->" heading-offset=1 %}

!!! info "Runnable scenarios"
    The reference implementation ships these flows as executable scenarios, which are the most current statement of what it supports:

    - [`rv_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/rv_demo.py) — Reporter → Vendor (two-party)
    - [`rcv_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/rcv_demo.py) — Reporter → Coordinator → Vendor
    - [`rvcv_handoff_demo.py`](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/rvcv_handoff_demo.py) — Coordinator hand-off
    - [scenario inventory](https://github.com/CERTCC/Vultron/blob/main/vultron/demo/scenario/README.md) — the full list
