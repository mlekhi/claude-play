# claude-piece Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daemon that watches Claude Code sessions via hooks and plays One Pace episodes in mpv when all sessions are busy.

**Architecture:** Claude Code hooks write session state to files in `~/.claude-piece/sessions/`. A Python daemon watches that directory and controls mpv via JSON IPC over a Unix socket. On macOS, osascript handles window minimize/unminimize.

**Tech Stack:** Python 3, watchdog (filesystem monitoring), mpv (video playback), Claude Code hooks (shell scripts)

---

### Task 1: Project scaffolding + hook script

**Files:**
- Create: `claude-piece-hook.sh`
- Create: `requirements.txt`
- Create: `README.md`

**Step 1: Create requirements.txt**

```
watchdog>=3.0.0
```

**Step 2: Create the hook script**

Create `claude-piece-hook.sh` — a shell script that reads Claude Code hook JSON from stdin, extracts `session_id`, and writes/deletes state files in `~/.claude-piece/sessions/`.

```bash
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
    active|start)
        echo "{\"state\": \"active\", \"pid\": $$, \"updated\": $(date +%s)}" > "$SESSION_FILE"
        ;;
    end)
        rm -f "$SESSION_FILE"
        ;;
esac

exit 0
```

**Step 3: Create README.md**

```markdown
# claude-piece

Watches all your Claude Code sessions. When every session is busy (thinking/working),
it plays an episode of One Pace. Pauses instantly when any session needs your input.

```
┌─────────────────┐     state files      ┌──────────────┐    IPC socket    ┌─────┐
│ Claude Code CLI │ ──── hooks ────────▶  │ claude-piece  │ ──────────────▶ │ mpv │
│ (N sessions)    │   write to disk       │   daemon      │  pause/resume   │     │
└─────────────────┘                       └──────────────┘                  └─────┘
```

## Prerequisites

- Python 3
- mpv (`brew install mpv`)
- Claude Code

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Make the hook script executable: `chmod +x claude-piece-hook.sh`
3. Configure Claude Code hooks (see below)
4. Create config: `~/.claude-piece/config.json`
5. Run the daemon: `python claude_piece.py`

## Claude Code Hooks

Add to `~/.claude/settings.json`:

\```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh busy"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh active"}]}],
    "SessionStart": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh start"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh end"}]}]
  }
}
\```

## Config

Create `~/.claude-piece/config.json`:

\```json
{
  "source": "directory",
  "path": "/path/to/one-pace-episodes/",
  "play_when_no_sessions": true
}
\```
```

**Step 4: Commit**

```bash
git add requirements.txt claude-piece-hook.sh README.md
git commit -m "feat: add project scaffolding and hook script"
```

---

### Task 2: mpv controller module

**Files:**
- Create: `mpv_controller.py`

**Step 1: Write the mpv controller**

A Python class that manages mpv: launching, pausing, resuming, seeking, loading files, detecting EOF, and minimizing/unminimizing the window via osascript.

```python
import socket
import json
import subprocess
import os
import time


class MpvController:
    SOCKET_PATH = "/tmp/claude-piece-mpv.sock"

    def __init__(self):
        self.sock = None
        self.process = None
        self._buf = b""

    def launch(self, filepath):
        """Launch mpv with IPC enabled, playing the given file."""
        if self.process and self.process.poll() is None:
            return  # already running

        # Clean up stale socket
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)

        self.process = subprocess.Popen([
            "mpv",
            f"--input-ipc-server={self.SOCKET_PATH}",
            "--no-terminal",
            "--force-window=yes",
            "--keep-open=yes",
            "--pause",
            filepath,
        ])

        # Wait for socket to appear
        for _ in range(50):
            if os.path.exists(self.SOCKET_PATH):
                break
            time.sleep(0.1)

        self._connect()

    def _connect(self):
        """Connect to the mpv IPC socket."""
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.SOCKET_PATH)
        self.sock.settimeout(1.0)
        self._buf = b""

    def _send(self, command):
        """Send a command to mpv and return the response."""
        if not self.sock:
            return None
        payload = json.dumps({"command": command}) + "\n"
        try:
            self.sock.sendall(payload.encode("utf-8"))
            return self._read_response()
        except (BrokenPipeError, ConnectionError, OSError):
            return None

    def _read_response(self):
        """Read a command response, skipping event messages."""
        while True:
            if b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                if "event" not in msg and "error" in msg:
                    return msg
                continue
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not chunk:
                return None
            self._buf += chunk

    def pause(self):
        self._send(["set_property", "pause", True])

    def resume(self):
        self._send(["set_property", "pause", False])

    def get_position(self):
        resp = self._send(["get_property", "playback-time"])
        if resp and resp.get("error") == "success":
            return resp.get("data", 0)
        return 0

    def seek(self, position):
        self._send(["seek", position, "absolute"])

    def load_file(self, filepath):
        self._send(["loadfile", filepath, "replace"])

    def is_eof(self):
        resp = self._send(["get_property", "eof-reached"])
        if resp and resp.get("error") == "success":
            return resp.get("data", False)
        return False

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def minimize(self):
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to tell process "mpv" '
            'to set value of attribute "AXMinimized" of every window to true'
        ], capture_output=True)

    def unminimize(self):
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to tell process "mpv" '
            'to set value of attribute "AXMinimized" of every window to false'
        ], capture_output=True)

    def quit(self):
        self._send(["quit"])
        if self.process:
            self.process.wait(timeout=5)
        if self.sock:
            self.sock.close()
            self.sock = None
```

**Step 2: Commit**

```bash
git add mpv_controller.py
git commit -m "feat: add mpv controller with IPC pause/resume/minimize"
```

---

### Task 3: Session state manager

**Files:**
- Create: `session_manager.py`

**Step 1: Write the session manager**

Reads session state files, evaluates whether all sessions are busy, and cleans up stale sessions.

```python
import json
import os
import glob
import time


class SessionManager:
    def __init__(self, sessions_dir=None):
        self.sessions_dir = sessions_dir or os.path.expanduser("~/.claude-piece/sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)

    def get_sessions(self):
        """Read all session state files and return a list of session dicts."""
        sessions = []
        for filepath in glob.glob(os.path.join(self.sessions_dir, "*.json")):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                data["session_id"] = os.path.basename(filepath).replace(".json", "")
                data["filepath"] = filepath
                sessions.append(data)
            except (json.JSONDecodeError, IOError):
                continue
        return sessions

    def cleanup_stale(self, max_age=3600):
        """Remove session files older than max_age seconds or with dead PIDs."""
        now = time.time()
        for session in self.get_sessions():
            updated = session.get("updated", 0)
            pid = session.get("pid")

            stale_by_time = (now - updated) > max_age
            stale_by_pid = pid and not self._pid_alive(pid)

            if stale_by_time or stale_by_pid:
                try:
                    os.remove(session["filepath"])
                except OSError:
                    pass

    def all_busy(self):
        """Return True if all sessions are busy (or there are no sessions)."""
        sessions = self.get_sessions()
        if not sessions:
            return True
        return all(s.get("state") == "busy" for s in sessions)

    def has_sessions(self):
        """Return True if there are any tracked sessions."""
        return len(self.get_sessions()) > 0

    @staticmethod
    def _pid_alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
```

**Step 2: Commit**

```bash
git add session_manager.py
git commit -m "feat: add session state manager with stale cleanup"
```

---

### Task 4: Main daemon

**Files:**
- Create: `claude_piece.py`

**Step 1: Write the main daemon**

Ties everything together: watches the sessions directory, evaluates state, controls mpv.

```python
#!/usr/bin/env python3
"""claude-piece: Watch Claude Code sessions, play One Pace when all are busy."""

import json
import os
import sys
import signal
import time
import glob

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from mpv_controller import MpvController
from session_manager import SessionManager


CONFIG_DIR = os.path.expanduser("~/.claude-piece")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PLAYBACK_FILE = os.path.join(CONFIG_DIR, "playback.json")


def load_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        print(f"No config found at {CONFIG_FILE}")
        print('Create it with: {{"source": "directory", "path": "/path/to/episodes/", "play_when_no_sessions": true}}')
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


def get_episodes(config):
    source = config.get("source", "directory")
    if source == "directory":
        path = config["path"]
        extensions = (".mp4", ".mkv", ".avi", ".webm")
        files = sorted([
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith(extensions)
        ])
        return files
    elif source == "urls":
        return config.get("urls", [])
    return []


def load_playback():
    if os.path.exists(PLAYBACK_FILE):
        with open(PLAYBACK_FILE) as f:
            return json.load(f)
    return {"episode_index": 0, "position": 0.0}


def save_playback(data):
    with open(PLAYBACK_FILE, "w") as f:
        json.dump(data, f)


class SessionChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_created(self, event):
        if event.src_path.endswith(".json"):
            self.callback()

    def on_modified(self, event):
        if event.src_path.endswith(".json"):
            self.callback()

    def on_deleted(self, event):
        if event.src_path.endswith(".json"):
            self.callback()


class ClaudePiece:
    def __init__(self):
        self.config = load_config()
        self.episodes = get_episodes(self.config)
        self.playback = load_playback()
        self.session_mgr = SessionManager()
        self.mpv = MpvController()
        self.playing = False
        self.last_cleanup = time.time()

        if not self.episodes:
            print("No episodes found. Check your config.")
            sys.exit(1)

        print(f"Found {len(self.episodes)} episodes")
        print(f"Resuming from episode {self.playback['episode_index']} at {self.playback['position']:.1f}s")

    def evaluate(self):
        """Check session states and play/pause accordingly."""
        # Periodic stale cleanup
        now = time.time()
        if now - self.last_cleanup > 60:
            self.session_mgr.cleanup_stale()
            self.last_cleanup = now

        all_busy = self.session_mgr.all_busy()
        has_sessions = self.session_mgr.has_sessions()
        play_no_sessions = self.config.get("play_when_no_sessions", True)

        should_play = all_busy and (has_sessions or play_no_sessions)

        if should_play and not self.playing:
            self._start_playing()
        elif not should_play and self.playing:
            self._stop_playing()

    def _start_playing(self):
        idx = self.playback["episode_index"]
        if idx >= len(self.episodes):
            print("All episodes watched!")
            return

        episode = self.episodes[idx]
        print(f"Playing: {os.path.basename(episode)}")

        if not self.mpv.is_running():
            self.mpv.launch(episode)
            if self.playback["position"] > 0:
                self.mpv.seek(self.playback["position"])

        self.mpv.unminimize()
        self.mpv.resume()
        self.playing = True

    def _stop_playing(self):
        if self.mpv.is_running():
            # Save position before pausing
            pos = self.mpv.get_position()
            if pos:
                self.playback["position"] = pos
                save_playback(self.playback)

            self.mpv.pause()
            self.mpv.minimize()

        self.playing = False
        print("Paused — session needs input")

    def _check_episode_advance(self):
        """Check if current episode finished and advance to next."""
        if not self.mpv.is_running() or not self.playing:
            return
        if self.mpv.is_eof():
            self.playback["episode_index"] += 1
            self.playback["position"] = 0.0
            save_playback(self.playback)

            idx = self.playback["episode_index"]
            if idx < len(self.episodes):
                episode = self.episodes[idx]
                print(f"Next episode: {os.path.basename(episode)}")
                self.mpv.load_file(episode)
                self.mpv.resume()
            else:
                print("All episodes watched!")
                self.playing = False

    def run(self):
        handler = SessionChangeHandler(self.evaluate)
        observer = Observer()
        observer.schedule(handler, self.session_mgr.sessions_dir, recursive=False)
        observer.start()

        print("claude-piece daemon running. Watching for Claude Code sessions...")
        self.evaluate()  # Initial check

        def shutdown(sig, frame):
            print("\nShutting down...")
            if self.mpv.is_running():
                pos = self.mpv.get_position()
                if pos:
                    self.playback["position"] = pos
                    save_playback(self.playback)
                self.mpv.quit()
            observer.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        while True:
            self._check_episode_advance()
            time.sleep(2)


if __name__ == "__main__":
    ClaudePiece().run()
```

**Step 2: Commit**

```bash
git add claude_piece.py
git commit -m "feat: add main daemon with session watching and mpv control"
```

---

### Task 5: Install script

**Files:**
- Create: `install.sh`

**Step 1: Write install script**

Automates setup: installs deps, makes hook executable, injects hooks into Claude Code settings.

```bash
#!/bin/bash
# install.sh — Set up claude-piece hooks and config
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_PATH="$SCRIPT_DIR/claude-piece-hook.sh"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
CONFIG_DIR="$HOME/.claude-piece"

echo "=== claude-piece installer ==="

# Install Python deps
echo "Installing Python dependencies..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

# Make hook executable
chmod +x "$HOOK_PATH"

# Create config dir
mkdir -p "$CONFIG_DIR/sessions"

# Create default config if missing
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo '{
  "source": "directory",
  "path": "/path/to/one-pace-episodes/",
  "play_when_no_sessions": true
}' > "$CONFIG_DIR/config.json"
    echo "Created default config at $CONFIG_DIR/config.json"
    echo "  -> Edit the 'path' to point to your One Pace episodes!"
fi

# Add hooks to Claude Code settings
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
echo "Done! Run: python3 $SCRIPT_DIR/claude_piece.py"
```

**Step 2: Commit**

```bash
git add install.sh
git commit -m "feat: add install script for hooks and config setup"
```
