# Exchange Demos

This sub-package contains individual protocol-fragment demos for the Vultron
CVD workflow.

## What these demos do

Each module in `exchange/` demonstrates a single ActivityStreams message
exchange in isolation. These demos use **direct inbox injection** — they
construct AS2 activities manually and POST them directly to an actor's inbox.
This is intentional: the goal is to illustrate the protocol message semantics
without requiring a full multi-actor deployment.

This technique is sometimes called "spoofing" because the demo is constructing
and delivering messages as if it were the sending actor, bypassing the sending
actor's own outbox. This is appropriate for exchange demos because:

- They focus on *what a message looks like* and *how the receiving actor
  processes it*, not on the full end-to-end delivery pipeline.
- They run against a single API server instance, making them easy to run
  locally or in CI.

## Available exchange demos

| Sub-command              | Script                           | What it demonstrates                            |
|--------------------------|----------------------------------|-------------------------------------------------|
| `receive-report`         | `receive_report_demo.py`         | Receiving and processing a vulnerability report |
| `initialize-case`        | `initialize_case_demo.py`        | Creating and initializing a vulnerability case  |
| `initialize-participant` | `initialize_participant_demo.py` | Initializing a standalone CaseParticipant       |
| `invite-actor`           | `invite_actor_demo.py`           | Inviting an actor to participate in a case      |
| `establish-embargo`      | `establish_embargo_demo.py`      | Establishing a coordinated disclosure embargo   |
| `acknowledge`            | `acknowledge_demo.py`            | Acknowledging receipt of a vulnerability report |
| `status-updates`         | `status_updates_demo.py`         | Posting case status updates and notes           |
| `suggest-actor`          | `suggest_actor_demo.py`          | Suggesting an actor for a case                  |
| `transfer-ownership`     | `transfer_ownership_demo.py`     | Transferring case ownership between actors      |
| `manage-case`            | `manage_case_demo.py`            | Managing report management state transitions    |
| `manage-embargo`         | `manage_embargo_demo.py`         | Managing embargo lifecycle state transitions    |
| `manage-participants`    | `manage_participants_demo.py`    | Adding and removing case participants           |
| `trigger`                | `trigger_demo.py`                | Triggerable behavior endpoint walkthrough       |

## Running exchange demos

All exchange demos are accessible through the unified CLI:

```bash
vultron-demo receive-report
vultron-demo initialize-case
vultron-demo all        # runs every exchange demo in sequence
```

See the parent `README.md` for full setup and Docker instructions.
