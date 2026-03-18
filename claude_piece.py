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
        # Skip if mpv is mid-launch to avoid double-open
        if self.mpv._launching:
            return

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
