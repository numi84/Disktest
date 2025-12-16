"""
Settings-Controller - Verwaltet App-Einstellungen

Verantwortlich für:
- QSettings laden/speichern
- Recent Sessions verwalten
- User-Präferenzen
"""

import os
import json
from typing import List
from datetime import datetime

from PySide6.QtCore import QSettings


class SettingsController:
    """
    Controller für persistente Einstellungen.

    Verwaltet alle QSettings-Zugriffe und Recent Sessions.
    """

    def __init__(self):
        """Initialisiert den Settings-Controller."""
        self.settings = QSettings("DiskTest", "DiskTest")

    # --- Last Path ---

    def get_last_path(self) -> str:
        """
        Lädt den zuletzt verwendeten Pfad.

        Returns:
            str: Zuletzt verwendeter Pfad oder leerer String
        """
        return self.settings.value("last_target_path", "")

    def save_last_path(self, path: str) -> None:
        """
        Speichert den verwendeten Pfad.

        Args:
            path: Zu speichernder Pfad
        """
        if path and os.path.exists(path):
            self.settings.setValue("last_target_path", path)

    # --- Recent Sessions ---

    def get_recent_sessions(self, max_count: int = 10) -> List[dict]:
        """
        Lädt die Liste der Recent Sessions.

        Args:
            max_count: Maximale Anzahl zurückzugebender Sessions

        Returns:
            Liste von Session-Dictionaries mit 'path' und 'last_used'
        """
        recent_sessions = self.settings.value("recent_sessions", "[]")
        try:
            sessions_list = json.loads(recent_sessions)
            return sessions_list[:max_count]
        except (json.JSONDecodeError, TypeError):
            return []

    def get_recent_session_paths(self, max_count: int = 10) -> List[str]:
        """
        Lädt nur die Pfade der zuletzt verwendeten Sessions.

        Args:
            max_count: Maximale Anzahl zurückzugebender Pfade

        Returns:
            Liste von Pfaden
        """
        sessions = self.get_recent_sessions(max_count)
        return [s.get('path') for s in sessions if s.get('path')]

    def add_recent_session(self, path: str) -> None:
        """
        Fügt einen Pfad zur Recent Sessions Liste hinzu.

        Der Pfad wird am Anfang eingefügt. Duplikate werden entfernt.

        Args:
            path: Hinzuzufügender Pfad
        """
        sessions_list = self.get_recent_sessions()

        # Entferne Pfad falls bereits vorhanden
        sessions_list = [s for s in sessions_list if s.get('path') != path]

        # Füge neuen Pfad am Anfang ein
        sessions_list.insert(0, {
            'path': path,
            'last_used': datetime.now().isoformat()
        })

        # Begrenze auf max Einträge
        max_recent = self.get_int("recent_sessions_max", 10)
        sessions_list = sessions_list[:max_recent]

        # Speichere
        self.settings.setValue("recent_sessions", json.dumps(sessions_list))

    # --- Session Scan Settings ---

    def is_session_scan_enabled(self) -> bool:
        """
        Prüft ob Multi-Session-Scan aktiviert ist.

        Returns:
            True wenn aktiviert
        """
        return self.get_bool("session_scan_enabled", True)

    def get_session_scan_depth(self) -> str:
        """
        Gibt die Scan-Tiefe zurück.

        Returns:
            "root_only", "one_level" oder "two_levels"
        """
        return self.settings.value("session_scan_depth", "one_level")

    def get_session_scan_timeout_ms(self) -> int:
        """
        Gibt das Scan-Timeout in Millisekunden zurück.

        Returns:
            Timeout in ms
        """
        return self.get_int("session_scan_timeout_ms", 5000)

    # --- Generic Getters ---

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Lädt einen Boolean-Wert aus den Settings.

        Args:
            key: Setting-Schlüssel
            default: Standardwert

        Returns:
            Gespeicherter oder Standardwert
        """
        return self.settings.value(key, default, type=bool)

    def get_int(self, key: str, default: int = 0) -> int:
        """
        Lädt einen Integer-Wert aus den Settings.

        Args:
            key: Setting-Schlüssel
            default: Standardwert

        Returns:
            Gespeicherter oder Standardwert
        """
        return self.settings.value(key, default, type=int)

    def get_string(self, key: str, default: str = "") -> str:
        """
        Lädt einen String-Wert aus den Settings.

        Args:
            key: Setting-Schlüssel
            default: Standardwert

        Returns:
            Gespeicherter oder Standardwert
        """
        return self.settings.value(key, default)

    # --- Generic Setters ---

    def set_value(self, key: str, value) -> None:
        """
        Speichert einen Wert in den Settings.

        Args:
            key: Setting-Schlüssel
            value: Zu speichernder Wert
        """
        self.settings.setValue(key, value)
