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

# --- Persistent data volume ---
DATA="$HOME/.data"
sudo chown "$(id -u):$(id -g)" "$DATA" 2>/dev/null || true
mkdir -p "$DATA/claude" "$DATA/shell-history"

# Symlink ~/.claude to persistent volume
if [ -d "$HOME/.claude" ] && [ ! -L "$HOME/.claude" ]; then
    if [ -z "$(ls -A "$DATA/claude" 2>/dev/null)" ]; then
        cp -a "$HOME/.claude/." "$DATA/claude/"
    fi
    rm -rf "$HOME/.claude"
fi
ln -sfn "$DATA/claude" "$HOME/.claude"

# Persist ~/.claude.json on the volume
if [ ! -f "$HOME/.claude/claude.json" ]; then
    echo '{}' > "$HOME/.claude/claude.json"
fi
ln -sf "$HOME/.claude/claude.json" "$HOME/.claude.json"

# --- Persistent shell history ---
touch "$DATA/shell-history/.bash_history" "$DATA/shell-history/.zsh_history"

if ! grep -q 'HISTFILE=.*\.data' "$HOME/.bashrc" 2>/dev/null; then
    echo 'export HISTFILE="$HOME/.data/shell-history/.bash_history"' >> "$HOME/.bashrc"
fi
if [ -f "$HOME/.zshrc" ] && ! grep -q 'HISTFILE=.*\.data' "$HOME/.zshrc" 2>/dev/null; then
    echo 'export HISTFILE="$HOME/.data/shell-history/.zsh_history"' >> "$HOME/.zshrc"
fi

# Claude Code installs to ~/.local/bin and registers it in .bashrc, but we use zsh
if ! grep -q 'local/bin' "$HOME/.zshrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
fi

# --- tmux configuration ---
cat > "$HOME/.tmux.conf" <<'EOF'
set -g default-terminal "tmux-256color"
set -s extended-keys on
set -as terminal-features ',xterm-256color:extkeys'
set -g history-limit 50000
set -g mouse on
set -g default-shell /bin/zsh
EOF

# --- User-level skills ---
# Point ~/.claude/skills at the Mac host user skills mounted by start.sh.
# Project skills (.claude/skills/ in the working tree) are auto-discovered by Claude Code separately.
if [ -d "$HOME/.agents/skills" ]; then
    ln -sfn "$HOME/.agents/skills" "$HOME/.data/claude/skills"
fi

echo ""
echo "Post-create complete. Run 'claude' to start Claude Code."
