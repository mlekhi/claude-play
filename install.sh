#!/bin/bash
# install.sh — Set up claude-play hooks and config
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_PATH="$SCRIPT_DIR/claude-play-hook.sh"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
CONFIG_DIR="$HOME/.claude-play"

echo "=== claude-play installer ==="

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
    echo "  -> Edit the 'path' to point to your your video files!"
fi

# Show hooks to add
echo ""
echo "Add the following to your ~/.claude/settings.json under \"hooks\":"
echo ""
cat <<EOF
{
  "hooks": {
    "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOOK_PATH busy"}]}],
    "PostToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOOK_PATH busy"}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOOK_PATH idle"}]}],
    "PermissionRequest": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOOK_PATH prompting"}]}],
    "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOOK_PATH start"}]}],
    "SessionEnd": [{"matcher": "", "hooks": [{"type": "command", "command": "$HOOK_PATH end"}]}]
  }
}
EOF

echo ""
echo "Done! Run: $VENV_DIR/bin/python $SCRIPT_DIR/claude_play.py"
