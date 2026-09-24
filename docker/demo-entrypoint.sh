#!/bin/bash
# Entrypoint for the unified Vultron demo container (DC-04-001, DC-04-002).
#
# If VULTRON_ACTOR_NAME or VULTRON_SEED_CONFIG is set, run the seed command
# first to bootstrap actor records in the DataLayer before any demo runs.
#
# When the DEMO environment variable is set, run that sub-command
# non-interactively and exit.  Otherwise, display available demos and
# drop into an interactive shell so the user can run `vultron-demo <name>`.

set -e

# Run seed if actor configuration is provided.
if [ -n "${VULTRON_ACTOR_NAME}" ] || [ -n "${VULTRON_SEED_CONFIG}" ]; then
    echo "Seeding actor records..."
    vultron-demo seed
fi

if [ -n "${DEMO}" ]; then
    exec vultron-demo ${DEMO}
fi

# Interactive mode: show available commands then open a shell.
echo ""
echo "Vultron Demo Container"
echo "======================"
echo "Run a demo with:  vultron-demo <name>"
echo ""
vultron-demo --help
echo ""
exec bash
