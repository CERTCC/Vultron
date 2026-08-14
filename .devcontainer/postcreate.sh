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
set -g set-clipboard on
set -g default-shell /bin/zsh
EOF

# ~/.claude is a bind-mount of the host's ~/.claude — the host manages its own
# skills symlink. Nothing to do here.

echo ""
echo "Post-create complete. Run 'claude' to start Claude Code."
