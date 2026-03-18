# claude-piece Design

A daemon that watches all Claude Code sessions and plays One Pace episodes whenever every session is busy (thinking/working) — pausing instantly when any session needs user input.

## Architecture

```
┌─────────────────┐     state files      ┌──────────────┐    IPC socket    ┌─────┐
│ Claude Code CLI │ ──── hooks ────────▶  │ claude-piece  │ ──────────────▶ │ mpv │
│ (N sessions)    │   write to disk       │   daemon      │  pause/resume   │     │
└─────────────────┘                       └──────────────┘                  └─────┘
```

Three components:

1. **Hook scripts** — shell scripts triggered by Claude Code lifecycle events, write session state to `~/.claude-piece/sessions/<session_id>.json`
2. **Daemon** (`claude-piece`) — Python process that watches the sessions directory, evaluates whether all sessions are busy, and controls mpv
3. **mpv** — video player controlled via JSON IPC over a Unix socket

## State Model

Each Claude Code session is in one of two states:

- `busy` — Claude is thinking/working, user is free to watch
- `active` — Claude is waiting for user input, user should be typing

**Playback rule:** Play video when ALL tracked sessions are `busy` OR there are zero sessions. Pause and hide the moment ANY session becomes `active`.

## Hook Configuration

Four hooks configured in `~/.claude/settings.json`:

| Event | Meaning | State Written |
|---|---|---|
| `UserPromptSubmit` | User hit enter, Claude will now think | `busy` |
| `Stop` | Claude finished, waiting for user | `active` |
| `SessionStart` | New session opened | `active` |
| `SessionEnd` | Session closed | Delete session file |

Each hook runs a script that reads `session_id` from stdin JSON and writes/deletes a session file:

```json
{"state": "busy", "pid": 54321, "updated": 1710700000}
```

The PID is stored so the daemon can clean up stale sessions if a session crashes without firing `SessionEnd`.

## Daemon Logic

1. **Watch** `~/.claude-piece/sessions/` for file changes (using `watchdog` library, event-driven)
2. **On any change**, read all session files and evaluate:
   - Zero sessions → play video
   - ALL sessions `busy` → play/resume video
   - ANY session `active` → pause + hide mpv window
3. **Stale session cleanup** — periodically check if PIDs in session files are still alive, delete dead ones
4. **Episode tracking** — persist current episode index + playback position to `~/.claude-piece/playback.json`

```json
{"episode_index": 3, "position": 847.2}
```

When an episode finishes, auto-advance to the next one.

## mpv Control

Launch mpv with `--input-ipc-server=/tmp/claude-piece-mpv.sock`.

Control via JSON IPC:
- **Pause:** `{"command": ["set_property", "pause", true]}`
- **Resume:** `{"command": ["set_property", "pause", false]}`
- **Seek:** `{"command": ["seek", 847.2, "absolute"]}`
- **Get position:** `{"command": ["get_property", "playback-time"]}`
- **Hide on pause:** `osascript` to minimize the mpv window on macOS
- **Show on resume:** unminimize via `osascript`, then resume playback

## Video Source Config

```json
{
  "source": "directory",
  "path": "/path/to/one-pace-episodes/",
  "play_when_no_sessions": true
}
```

Two modes:
- `"source": "directory"` — folder of video files, played in sorted order
- `"source": "urls"` — list of URLs that mpv + yt-dlp can stream

## Tech Stack

- **Python 3** — daemon, file watching, mpv IPC
- **watchdog** — filesystem event monitoring
- **mpv** — video playback (`brew install mpv`)
- **Shell scripts** — hook handlers
