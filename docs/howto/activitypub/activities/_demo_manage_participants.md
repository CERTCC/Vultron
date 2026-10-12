!!! example "Try it: `vultron-demo manage-participants`"

    ```bash
    vultron-demo manage-participants
    ```

    Or with Docker Compose:

    ```bash
    DEMO=manage-participants docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario runs invite, accept, status update, removal, and reinstatement, then the rejection path.
