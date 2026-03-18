# claude-play

watches all your claude code sessions. plays videos when every session is idle — pauses instantly when any session needs your input.

```
┌─────────────────┐     state files      ┌──────────────┐    IPC socket    ┌─────┐
│ claude code cli │ ──── hooks ────────▶  │  claude-play  │ ──────────────▶ │ mpv │
│ (n sessions)    │   write to disk       │    daemon     │  pause/resume   │     │
└─────────────────┘                       └──────────────┘                  └─────┘
```

## how it works

claude code fires hooks on lifecycle events. `claude-play` listens:

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

## supported video sources

mpv handles playback, so anything mpv can play works:

| source | example |
|---|---|
| local files | `/path/to/videos/*.mp4` |
| direct file urls | `https://example.com/video.mp4` |
| pixeldrain | `https://pixeldrain.net/api/file/<id>` |
| youtube | `https://youtube.com/watch?v=...` (needs yt-dlp) |
| twitch vods | `https://twitch.tv/videos/...` (needs yt-dlp) |
| gdrive (public) | `https://drive.google.com/file/d/<id>/view` |
| hls streams | `https://example.com/stream.m3u8` |
| any direct url | if it ends in `.mp4`, `.mkv`, `.webm`, etc. — it works |

**tip:** for sites like youtube/twitch, install [yt-dlp](https://github.com/yt-dlp/yt-dlp) and mpv will use it automatically.

## prerequisites

- python 3
- [mpv](https://mpv.io/) — `brew install mpv`
- [claude code](https://docs.anthropic.com/en/docs/claude-code)

## setup

```bash
# 1. clone and install
git clone https://github.com/mlekhi/claude-play.git
cd claude-play
bash install.sh

# 2. configure your videos
# edit ~/.claude-play/config.json (see config section below)

# 3. add hooks to claude code
# the install script prints the exact json — paste it into ~/.claude/settings.json

# 4. run the daemon
.venv/bin/python claude_play.py
```

## config

edit `~/.claude-play/config.json`:

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

paste video urls from wherever you watch. mpv streams them directly — nothing gets downloaded.

### local files

```json
{
  "source": "directory",
  "path": "/path/to/videos/",
  "mode": "idle"
}
```

plays files in sorted order. supports mp4, mkv, avi, webm.

## claude code hooks

the install script outputs this for you, but for reference — add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-play-hook.sh busy"}]}],
    "PostToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-play-hook.sh busy"}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-play-hook.sh idle"}]}],
    "PermissionRequest": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-play-hook.sh prompting"}]}],
    "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-play-hook.sh start"}]}],
    "SessionEnd": [{"matcher": "", "hooks": [{"type": "command", "command": "/absolute/path/to/claude-play-hook.sh end"}]}]
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
~/.claude-play/
├── config.json          # your video config
├── playback.json        # current episode + position (auto-managed)
└── sessions/
    ├── <session-id>.json  # one file per active claude code session
    └── ...
```

each session file contains `{"state": "busy"|"idle"|"prompting", ...}`. the daemon watches this directory for changes and reacts instantly via [watchdog](https://github.com/gorakhargosh/watchdog). stale sessions (crashed without cleanup) are automatically pruned.
