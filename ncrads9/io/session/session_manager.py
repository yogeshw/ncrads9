# NCRADS9 - NCRA DS9 Visualization Tool
# Copyright (C) 2026 Yogesh Wadadekar
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Session manager for NCRADS9.

Author: Yogesh Wadadekar
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union


class SessionManager:
    """Manager for saving and restoring application sessions."""

    VERSION: str = "1.0"

    def __init__(self, session_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize session manager.

        Args:
            session_dir: Directory for session files. Defaults to ~/.ncrads9/sessions.
        """
        if session_dir is None:
            self.session_dir = Path.home() / ".ncrads9" / "sessions"
        else:
            self.session_dir = Path(session_dir)

        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: dict[str, Any] = {}

    def new_session(self, name: Optional[str] = None) -> str:
        """
        Create a new session.

        Args:
            name: Optional session name.

        Returns:
            Session ID.
        """
        timestamp = datetime.now().isoformat()
        session_id = timestamp.replace(":", "-").replace(".", "-")

        self._current_session = {
            "id": session_id,
            "name": name or f"Session {session_id}",
            "version": self.VERSION,
            "created": timestamp,
            "modified": timestamp,
            "state": {},
        }

        return session_id

    def save_session(
        self,
        session_id: Optional[str] = None,
        state: Optional[dict[str, Any]] = None,
    ) -> Path:
        """
        Save the current session to disk.

        Args:
            session_id: Session ID. Uses current if not provided.
            state: State dictionary to save.

        Returns:
            Path to saved session file.
        """
        if session_id is None:
            session_id = self._current_session.get("id")

        if session_id is None:
            session_id = self.new_session()

        if state is not None:
            self._current_session["state"] = state

        self._current_session["modified"] = datetime.now().isoformat()

        session_path = self.session_dir / f"{session_id}.json"
        with open(session_path, "w") as f:
            json.dump(self._current_session, f, indent=2)

        return session_path

    def load_session(self, session_id: str) -> dict[str, Any]:
        """
        Load a session from disk.

        Args:
            session_id: Session ID to load.

        Returns:
            Session data dictionary.
        """
        session_path = self.session_dir / f"{session_id}.json"

        with open(session_path, "r") as f:
            self._current_session = json.load(f)

        return self._current_session

    def delete_session(self, session_id: str) -> None:
        """
        Delete a session.

        Args:
            session_id: Session ID to delete.
        """
        session_path = self.session_dir / f"{session_id}.json"
        if session_path.exists():
            session_path.unlink()

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all available sessions.

        Returns:
            List of session metadata dictionaries.
        """
        sessions = []
        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file, "r") as f:
                    data = json.load(f)
                    sessions.append({
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "created": data.get("created"),
                        "modified": data.get("modified"),
                    })
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(sessions, key=lambda x: x.get("modified", ""), reverse=True)

    def get_state(self) -> dict[str, Any]:
        """
        Get the current session state.

        Returns:
            State dictionary.
        """
        return self._current_session.get("state", {})

    def set_state(self, key: str, value: Any) -> None:
        """
        Set a value in the session state.

        Args:
            key: State key.
            value: Value to store.
        """
        if "state" not in self._current_session:
            self._current_session["state"] = {}
        self._current_session["state"][key] = value

    def get_autosave_path(self) -> Path:
        """
        Get path for autosave file.

        Returns:
            Path to autosave file.
        """
        return self.session_dir / "autosave.json"

    def autosave(self, state: dict[str, Any]) -> None:
        """
        Save state to autosave file.

        Args:
            state: State to save.
        """
        autosave_data = {
            "version": self.VERSION,
            "timestamp": datetime.now().isoformat(),
            "state": state,
        }
        with open(self.get_autosave_path(), "w") as f:
            json.dump(autosave_data, f)

    def load_autosave(self) -> Optional[dict[str, Any]]:
        """
        Load autosave if available.

        Returns:
            Autosave state or None.
        """
        autosave_path = self.get_autosave_path()
        if autosave_path.exists():
            with open(autosave_path, "r") as f:
                data = json.load(f)
                return data.get("state")
        return None
