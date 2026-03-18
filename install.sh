#!/bin/bash
# install.sh — Set up claude-piece hooks and config
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_PATH="$SCRIPT_DIR/claude-piece-hook.sh"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
CONFIG_DIR="$HOME/.claude-piece"

echo "=== claude-piece installer ==="

# Set up venv and install deps
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

# Make hook executable
chmod +x "$HOOK_PATH"

# Create config dir
mkdir -p "$CONFIG_DIR/sessions"

# Create default config if missing
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" <<'CONF'
{
  "source": "directory",
  "path": "/path/to/one-pace-episodes/",
  "play_when_no_sessions": true
}
CONF
    echo "Created default config at $CONFIG_DIR/config.json"
    echo "  -> Edit the 'path' to point to your One Pace episodes!"
fi

# Show hooks to add
echo ""
echo "Add the following to your ~/.claude/settings.json under \"hooks\":"
echo ""
cat <<EOF
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "$HOOK_PATH busy"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "$HOOK_PATH active"}]}],
    "SessionStart": [{"hooks": [{"type": "command", "command": "$HOOK_PATH start"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "$HOOK_PATH end"}]}]
  }
}
EOF

echo ""
echo "Done! Run: $VENV_DIR/bin/python $SCRIPT_DIR/claude_piece.py"
