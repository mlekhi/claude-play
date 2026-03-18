#!/bin/bash
# claude-piece-hook.sh — Claude Code hook that tracks session state
# Usage: claude-piece-hook.sh <state>
# Where state is: busy, active, start, end
#
# Receives JSON on stdin from Claude Code with session_id, etc.

STATE="$1"
SESSIONS_DIR="$HOME/.claude-piece/sessions"
mkdir -p "$SESSIONS_DIR"

# Read JSON from stdin
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
    exit 0
fi

SESSION_FILE="$SESSIONS_DIR/$SESSION_ID.json"

case "$STATE" in
    busy)
        echo "{\"state\": \"busy\", \"pid\": $$, \"updated\": $(date +%s)}" > "$SESSION_FILE"
        ;;
    idle|start)
        echo "{\"state\": \"idle\", \"pid\": $$, \"updated\": $(date +%s)}" > "$SESSION_FILE"
        ;;
    prompting)
        echo "{\"state\": \"prompting\", \"pid\": $$, \"updated\": $(date +%s)}" > "$SESSION_FILE"
        ;;
    end)
        rm -f "$SESSION_FILE"
        ;;
esac

exit 0
