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

# Knowledge graph hooks (rebuilds graphify-out/ after commits and branch switches)
# Optional — requires graphify: pip install graphifyy
graphify hook install
```

The graphify hooks run in the background and only fire when `graphify-out/` already
exists (i.e., after you've run `/graphify .` at least once). They won't interfere
with the pre-commit hooks or slow down your commits.
