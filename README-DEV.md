# Vultron Developer Readme

This README provides instructions for developers who want to work on the Vultron project.
If you count yourself among them, welcome aboard!

> [!TIP] Help us improve this document.
> If there's something you would have found useful to know when you started,
please consider contributing to this document.

## Run unit tests in a Docker Container

The Vultron package includes a suite of tests. You can run them in a Docker container as follows:

```shell
cd docker
docker-compose up test
```

## Run a *Vultrabot* demo

*Vultrabot* was an early demo for a Vultron protocol demonstration script.
You can run it in a Docker container as follows:

```shell
cd docker
docker-compose up vultrabot-demo
```

What you'll see is a Vultron behavior tree interacting with itself,
emitting and responding to events in the form of Vultron message types.
It's not actually sending any messages, the demo is just responding to the
message types sent and received. But it's a reasonable demonstration of
the protocol behaviors in response to changing conditions as a case evolves.
Each run of the demo will be different, as the behavior tree has
some randomness in its decision-making.

## Run the Vultron API in a Docker Container with Hot Reloading

We're actively working on the Vultron API, and you can run it in a Docker container
with hot reloading as follows:

```shell
cd docker
docker-compose up api-dev
```

Then browse to <http://localhost:7999>

If you make changes to the code, the server will automatically reload.
You can stop the server with Ctrl-C.
Because we're mounting the vultron directory into the container,
you can edit the code on your host machine and see the changes reflected
in the container, but be aware that some changes may require a restart of the container.

## Run the Vultron site locally

You can run a local copy of the Vultron documentation site in a Docker container as follows:

```shell
cd docker
docker-compose up docs
```

Then browse to <http://localhost:8000>

The "real" site lives at <https://certcc.github.io/Vultron/>

## Set up local development hooks

After cloning, install the git hooks used in this project:

```shell
# Code quality hooks (black, markdownlint, flake8, spec/ADR validators)
pre-commit install

```

Do **not** install the graphify git hooks — see "Knowledge graph" below for why.

## Knowledge graph (graphify)

The `graphify-out/` knowledge graph is a single derived artifact of `origin/main`,
built by **one** authority and mounted **read-only** into every dev slot.

Do **not** run `graphify hook install`. Those hooks rebuild the entire graph
(incremental AST extraction *plus* a full re-cluster of the whole graph) on every
commit and every branch switch. With several slots running at once — and, worse,
on the **uncapped** host clone — that saturates the machine for minutes. Building
is centralized instead:

```shell
# Rebuild the shared graph on demand (CPU-capped, from origin/main). Running
# slots pick up the new graph on their next restart.
./start-dev.sh --build-graph
```

Inside a slot, `graph.json` is mounted read-only, so agents can
`graphify query`/`path`/`explain` but cannot trigger a rebuild. The query flow's
scratch (`.vocab.txt`, `memory/`) writes to a throwaway in-container `graphify-out/`
and is discarded on teardown.

If you previously ran `graphify hook install` in your host checkout, remove it —
the host hooks run with no CPU cap and are the worst offender:

```shell
graphify hook uninstall   # run once in your ~/dev/<repo> host checkout
```

Two caveats:

- `core.hooksPath` **replaces** the hooks directory wholesale, which is why
  `.githooks/pre-commit` and `.githooks/post-checkout` forward to the shared hooks.
  Without those forwarders, `pre-commit` (black, flake8, markdownlint) silently
  stops running in that worktree.
- The rebuild covers code files only (AST, no LLM). It re-runs community detection,
  so descriptive community names may be replaced by hub-node symbol names. Run
  `/graphify . --update` to refresh doc coverage and community labels.

`.graphifyignore` excludes `plan/history/` from the graph: those 1000+ append-only
archive entries are historical narrative that add weakly-connected nodes and distort
community detection.
