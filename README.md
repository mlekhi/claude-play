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
2. Run the installer: `bash install.sh`
3. Edit `~/.claude-piece/config.json` to point to your One Pace episodes
4. Run the daemon: `python claude_piece.py`

## Claude Code Hooks

The install script will show you the hooks to add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh busy"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh active"}]}],
    "SessionStart": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh start"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh end"}]}]
  }
}
```

## Config

Create `~/.claude-piece/config.json`:

```json
{
  "source": "directory",
  "path": "/path/to/one-pace-episodes/",
  "play_when_no_sessions": true
}
```

Two source modes:
- `"directory"` — folder of video files (mp4, mkv, avi, webm), played in sorted order
- `"urls"` — list of URLs that mpv + yt-dlp can stream
