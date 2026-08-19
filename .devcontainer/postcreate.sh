#!/bin/bash
# Runs once after first container creation.
set -euo pipefail

echo "=== Post-create setup ==="
echo ""

# Update Claude Code to latest
echo "Updating Claude Code..."
claude update || true

# Pure prompt for zsh
mkdir -p "$HOME/.zsh"
if [ ! -d "$HOME/.zsh/pure" ]; then
    git clone https://github.com/sindresorhus/pure.git "$HOME/.zsh/pure"
fi
if ! grep -q 'pure' "$HOME/.zshrc" 2>/dev/null; then
    cat >> "$HOME/.zshrc" <<'EOF'

# Pure prompt
FPATH=$HOME/.zsh/pure:$FPATH
autoload -U promptinit; promptinit
prompt pure
EOF
fi

# Claude Code installs to ~/.local/bin and registers it in .bashrc, but we use zsh
if ! grep -q 'local/bin' "$HOME/.zshrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
fi

# Auto-start tmux on login if not already inside a tmux session
if ! grep -q 'TMUX' "$HOME/.zshrc" 2>/dev/null; then
    cat >> "$HOME/.zshrc" <<'EOF'

# Auto-start tmux on login
if [ -z "$TMUX" ]; then exec tmux new-session -s main; fi
EOF
fi

# --- tmux configuration ---
cat > "$HOME/.tmux.conf" <<'EOF'
set -g default-terminal "tmux-256color"
set -s extended-keys on
set -as terminal-features ',xterm-256color:extkeys'
set -g history-limit 50000
set -g mouse on
set -g default-shell /bin/zsh

# OSC 52 doesn't pass through docker exec, so we use a clipboard bridge socket
# mounted from the host (see start-dev.sh and scripts/clipboard-bridge.sh).
# pbcopy (~/.local/bin/pbcopy) writes to /tmp/clipboard.sock when present.
set -g set-clipboard off
bind-key -T copy-mode    MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel "pbcopy"
bind-key -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel "pbcopy"
EOF

# --- clipboard bridge client ---
# Writes tmux selections to the Unix socket mounted from the Mac host.
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/pbcopy" <<'EOF'
#!/usr/bin/env python3
import sys, socket, os
sock = '/tmp/clipboard.sock'
if not os.path.exists(sock):
    sys.exit(0)
data = sys.stdin.buffer.read()
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
    s.connect(sock)
    s.sendall(data)
EOF
chmod +x "$HOME/.local/bin/pbcopy"

# Wire user-level skills into Claude Code's discovery path.
# start-dev.sh mounts the host's ~/.agents/skills into the container at
# ~/.agents/skills. Claude Code looks for skills under ~/.claude/skills, so
# create the symlink if the mount landed and the link doesn't already exist.
if [ -d "$HOME/.agents/skills" ] && [ ! -e "$HOME/.claude/skills" ]; then
    ln -s "$HOME/.agents/skills" "$HOME/.claude/skills"
fi

echo ""
echo "Post-create complete. Run 'claude' to start Claude Code."
