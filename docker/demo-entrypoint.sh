#!/bin/bash
# Entrypoint for the unified Vultron demo container (DC-04-001, DC-04-002).
#
# When the DEMO environment variable is set, run that sub-command
# non-interactively and exit.  Otherwise, display available demos and
# drop into an interactive shell so the user can run `vultron-demo <name>`.

set -e

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
