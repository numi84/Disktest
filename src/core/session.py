"""
Session-Management für DiskTest
Speichert und lädt den Test-Zustand für Pause/Resume-Funktionalität
"""
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


@dataclass
class SessionData:
    """
    Repräsentiert den kompletten Zustand einer Test-Session

    Wird als JSON gespeichert für Pause/Resume und Session-Wiederherstellung
    """
    # Konfiguration
    target_path: str
    file_size_gb: float
    total_size_gb: float
    file_count: int

    # Aktueller Fortschritt
    current_pattern_index: int  # 0-4 (Index in PATTERN_SEQUENCE)
    current_file_index: int     # 0 bis file_count-1
    current_phase: str          # "write" oder "verify"
    current_chunk_index: int    # Position in aktueller Datei

    # Reproduzierbarkeit
    random_seed: int            # Seed für Random-Muster

    # Fehler-Tracking
    errors: List[Dict] = field(default_factory=list)

    # Zeitstempel
    start_time: str = ""        # ISO-Format
    elapsed_seconds: float = 0.0

    # Metadaten
    version: int = 1            # Session-Format-Version

    def __post_init__(self):
        """Initialisiert start_time wenn leer"""
        if not self.start_time:
            self.start_time = datetime.now().isoformat()

    def add_error(self, file: str, pattern: str, phase: str, message: str):
        """
        Fügt einen Fehler zur Fehler-Liste hinzu

        Args:
            file: Dateiname
            pattern: Muster-Typ (z.B. "FF", "AA")
            phase: Phase ("write" oder "verify")
            message: Fehler-Beschreibung
        """
        error = {
            "file": file,
            "pattern": pattern,
            "phase": phase,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.errors.append(error)

    def get_progress_percentage(self) -> float:
        """
        Berechnet den Gesamtfortschritt in Prozent

        Returns:
            float: Fortschritt 0-100
        """
        # Pro Muster: Schreiben + Verifizieren = 2 Phasen
        # 5 Muster × 2 Phasen = 10 Phasen gesamt
        total_phases = 10

        # Aktuelle Phase berechnen
        current_phase_num = (self.current_pattern_index * 2)
        if self.current_phase == "verify":
            current_phase_num += 1

        # Fortschritt innerhalb der aktuellen Phase
        if self.file_count > 0:
            phase_progress = self.current_file_index / self.file_count
        else:
            phase_progress = 0

        # Gesamtfortschritt
        overall_progress = (current_phase_num + phase_progress) / total_phases * 100
        return min(100.0, max(0.0, overall_progress))

    def get_elapsed_time_formatted(self) -> str:
        """
        Formatiert die verstrichene Zeit

        Returns:
            str: Zeit im Format "Xh Ym Zs"
        """
        seconds = int(self.elapsed_seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def to_dict(self) -> dict:
        """
        Konvertiert SessionData zu Dictionary

        Returns:
            dict: Session-Daten als Dictionary
        """
        return asdict(self)


class SessionManager:
    """
    Verwaltet Session-Speicherung und -Laden

    Session-Datei: disktest_session.json
    """

    SESSION_FILENAME = "disktest_session.json"

    def __init__(self, session_dir: str = None):
        """
        Initialisiert den SessionManager

        Args:
            session_dir: Verzeichnis für Session-Datei (Standard: aktuelles Verzeichnis)
        """
        if session_dir is None:
            session_dir = "."

        self.session_dir = Path(session_dir)
        self.session_path = self.session_dir / self.SESSION_FILENAME

    def save(self, data: SessionData):
        """
        Speichert Session-Daten als JSON

        Args:
            data: Zu speichernde Session-Daten

        Raises:
            IOError: Wenn Speichern fehlschlägt
        """
        try:
            session_dict = data.to_dict()

            with open(self.session_path, 'w', encoding='utf-8') as f:
                json.dump(session_dict, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise IOError(f"Fehler beim Speichern der Session: {e}")

    def load(self) -> Optional[SessionData]:
        """
        Lädt Session-Daten aus JSON

        Returns:
            SessionData: Geladene Session-Daten oder None wenn nicht vorhanden

        Raises:
            IOError: Wenn Laden fehlschlägt
            ValueError: Wenn JSON-Format ungültig ist
        """
        if not self.exists():
            return None

        try:
            with open(self.session_path, 'r', encoding='utf-8') as f:
                session_dict = json.load(f)

            # Version prüfen
            version = session_dict.get('version', 1)
            if version != 1:
                raise ValueError(f"Unbekannte Session-Version: {version}")

            # SessionData erstellen
            # errors ist bereits eine Liste, muss nicht konvertiert werden
            return SessionData(**session_dict)

        except json.JSONDecodeError as e:
            raise ValueError(f"Ungültiges JSON-Format in Session-Datei: {e}")
        except Exception as e:
            raise IOError(f"Fehler beim Laden der Session: {e}")

    def exists(self) -> bool:
        """
        Prüft ob Session-Datei existiert

        Returns:
            bool: True wenn Session-Datei vorhanden
        """
        return self.session_path.exists()

    def delete(self):
        """
        Löscht die Session-Datei

        Raises:
            IOError: Wenn Löschen fehlschlägt
        """
        if self.exists():
            try:
                self.session_path.unlink()
            except Exception as e:
                raise IOError(f"Fehler beim Löschen der Session: {e}")

    def get_session_path(self) -> str:
        """
        Gibt Pfad zur Session-Datei zurück

        Returns:
            str: Absoluter Pfad zur Session-Datei
        """
        return str(self.session_path.absolute())

    def get_session_info(self) -> Optional[Dict]:
        """
        Gibt Kurzinformationen über gespeicherte Session zurück

        Returns:
            dict: Session-Info oder None wenn nicht vorhanden
        """
        if not self.exists():
            return None

        try:
            data = self.load()
            if data is None:
                return None

            return {
                'target_path': data.target_path,
                'progress_percent': data.get_progress_percentage(),
                'pattern_index': data.current_pattern_index,
                'file_index': data.current_file_index,
                'error_count': len(data.errors),
                'elapsed_time': data.get_elapsed_time_formatted(),
                'start_time': data.start_time
            }
        except Exception:
            return None

    def __repr__(self):
        return f"SessionManager(session_path={self.session_path})"
