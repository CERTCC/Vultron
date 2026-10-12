!!! example "Try it: `vultron-demo acknowledge`"

    ```bash
    vultron-demo acknowledge
    ```

    Or with Docker Compose:

    ```bash
    DEMO=acknowledge docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario runs all three paths: acknowledge only, acknowledge then validate, and acknowledge then invalidate.
