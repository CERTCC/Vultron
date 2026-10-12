!!! example "Try it: `vultron-demo report-with-embargo` — the negotiated path"

    ```bash
    vultron-demo report-with-embargo
    ```

    Or with Docker Compose:

    ```bash
    DEMO=report-with-embargo docker compose -f docker/docker-compose.yml run --rm demo
    ```

    Every other demo reaches an active embargo by the default path, where the Reporter states no terms and tacitly accepts the recipient's default.
    This one exercises the **negotiated** path (EP-04-003): the Reporter proposes terms with the submission, and the run shows which terms became active, which were left pending as a revision, and that the case owner's default stays active until it decides whether to accept the longer terms (EP-09-006).
    It runs three times: the Reporter proposes shorter than the recipient's default, longer than it, and against a recipient that has published no default at all.
