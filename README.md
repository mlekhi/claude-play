# claude-piece

watches all your claude code sessions. when every session is busy (thinking/working), it plays an episode of one pace. pauses instantly when any session needs your input.

```
┌─────────────────┐     state files      ┌──────────────┐    IPC socket    ┌─────┐
│ claude code cli │ ──── hooks ────────▶  │ claude-piece  │ ──────────────▶ │ mpv │
│ (n sessions)    │   write to disk       │   daemon      │  pause/resume   │     │
└─────────────────┘                       └──────────────┘                  └─────┘
```

## how it works

claude code fires hooks on lifecycle events. `claude-piece` listens:

| event | what happens | effect |
|---|---|---|
| you hit enter | session marked `busy` | video keeps playing |
| tool finishes running | session marked `busy` | video keeps playing |
| claude asks for permission | session marked `prompting` | video pauses + hides |
| claude finishes | session marked `idle` | video keeps playing |
| session closes | session file deleted | adjusts automatically |

when **any** session is prompting for input → video pauses and minimizes instantly.
otherwise → video plays.

your playback position is saved between pauses and across restarts.

## prerequisites

- python 3
- [mpv](https://mpv.io/) — `brew install mpv`
- [claude code](https://docs.anthropic.com/en/docs/claude-code)

## setup

```bash
# 1. clone and install
git clone https://github.com/mlekhi/claude-piece.git
cd claude-piece
bash install.sh

# 2. configure your episodes
# edit ~/.claude-piece/config.json (see config section below)

# 3. add hooks to claude code
# the install script prints the exact json — paste it into ~/.claude/settings.json

# 4. run the daemon
.venv/bin/python claude_piece.py
```

## config

edit `~/.claude-piece/config.json`:

### stream urls (no downloads needed)

```json
{
  "source": "urls",
  "urls": [
    "https://your-video-url.com/episode1.mp4",
    "https://your-video-url.com/episode2.mp4"
  ],
  "mode": "idle"
}
```

paste video urls from wherever you watch one pace. mpv streams them directly — nothing gets downloaded.

### local files

```json
{
  "source": "directory",
  "path": "/path/to/one-pace-episodes/",
  "mode": "idle"
}
```

plays files in sorted order. supports mp4, mkv, avi, webm.

## claude code hooks

the install script outputs this for you, but for reference — add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh busy"}]}],
    "PostToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh busy"}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh idle"}]}],
    "Notification": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh prompting"}]}],
    "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh start"}]}],
    "SessionEnd": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-piece-hook.sh end"}]}]
  }
}
```

replace `/absolute/path/to/` with the actual path where you cloned this repo.

## options

| config key | default | description |
|---|---|---|
| `source` | `"directory"` | `"directory"` for local files, `"urls"` for streaming |
| `path` | — | path to episode folder (directory mode) |
| `urls` | `[]` | list of video urls (urls mode) |
| `mode` | `"idle"` | `"idle"` = play unless prompting, `"always-busy"` = play only when all sessions are busy |

## how state tracking works

```
~/.claude-piece/
├── config.json          # your episode config
├── playback.json        # current episode + position (auto-managed)
└── sessions/
    ├── <session-id>.json  # one file per active claude code session
    └── ...
```

each session file contains `{"state": "busy"|"idle"|"prompting", ...}`. the daemon watches this directory for changes and reacts instantly via [watchdog](https://github.com/gorakhargosh/watchdog). stale sessions (crashed without cleanup) are automatically pruned.
