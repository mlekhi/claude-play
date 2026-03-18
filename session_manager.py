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
