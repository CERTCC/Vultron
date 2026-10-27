Named Docker volumes persist the SQLite databases between runs.
Remove all volumes after a session to start fresh next time:

```bash
docker compose -f docker/docker-compose-multi-actor.yml down -v
```
