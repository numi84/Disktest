"""
Logging-System für DiskTest
Schreibt Logs in Datei und stellt Formatierung bereit
"""
import os
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """Log-Levels für verschiedene Nachrichtentypen"""
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class DiskTestLogger:
    """
    Logger für DiskTest

    Schreibt Logs in Datei mit Format: [HH:MM:SS] LEVEL   Message
    Log-Datei: disktest_YYYYMMDD_HHMMSS.log
    """

    def __init__(self, log_dir: str = None):
        """
        Initialisiert den Logger

        Args:
            log_dir: Verzeichnis für Log-Dateien (Standard: aktuelles Verzeichnis)
        """
        if log_dir is None:
            log_dir = os.getcwd()

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log-Dateiname mit Timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = f"disktest_{timestamp}.log"
        self.log_path = self.log_dir / self.log_filename

        # Log-Datei initialisieren
        self._write_header()

    def _write_header(self):
        """Schreibt Header in Log-Datei"""
        with open(self.log_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"DiskTest - Log gestartet: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

    def _format_message(self, level: LogLevel, message: str) -> str:
        """
        Formatiert eine Log-Nachricht

        Args:
            level: Log-Level
            message: Nachricht

        Returns:
            str: Formatierte Nachricht
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Level auf 7 Zeichen aufgefüllt für Ausrichtung
        level_str = level.value.ljust(7)
        return f"[{timestamp}] {level_str} {message}"

    def _write_to_file(self, formatted_message: str):
        """
        Schreibt Nachricht in Log-Datei

        Args:
            formatted_message: Bereits formatierte Nachricht
        """
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(formatted_message + "\n")
        except Exception as e:
            print(f"Fehler beim Schreiben in Log-Datei: {e}")

    def info(self, message: str):
        """
        Schreibt INFO-Level Nachricht

        Args:
            message: Log-Nachricht
        """
        formatted = self._format_message(LogLevel.INFO, message)
        self._write_to_file(formatted)

    def success(self, message: str):
        """
        Schreibt SUCCESS-Level Nachricht

        Args:
            message: Log-Nachricht
        """
        formatted = self._format_message(LogLevel.SUCCESS, message)
        self._write_to_file(formatted)

    def warning(self, message: str):
        """
        Schreibt WARNING-Level Nachricht

        Args:
            message: Log-Nachricht
        """
        formatted = self._format_message(LogLevel.WARNING, message)
        self._write_to_file(formatted)

    def error(self, message: str):
        """
        Schreibt ERROR-Level Nachricht

        Args:
            message: Log-Nachricht
        """
        formatted = self._format_message(LogLevel.ERROR, message)
        self._write_to_file(formatted)

    def separator(self, char: str = "-", length: int = 80):
        """
        Schreibt Trennlinie in Log

        Args:
            char: Zeichen für Trennlinie (Standard: "-")
            length: Länge der Trennlinie (Standard: 80)
        """
        self._write_to_file(char * length)

    def section(self, title: str):
        """
        Schreibt Abschnitts-Header

        Args:
            title: Titel des Abschnitts
        """
        self._write_to_file("")
        self._write_to_file("=" * 80)
        self._write_to_file(f"  {title}")
        self._write_to_file("=" * 80)

    def get_log_path(self) -> str:
        """
        Gibt Pfad zur Log-Datei zurück

        Returns:
            str: Absoluter Pfad zur Log-Datei
        """
        return str(self.log_path.absolute())

    def get_log_filename(self) -> str:
        """
        Gibt Dateinamen der Log-Datei zurück

        Returns:
            str: Dateiname der Log-Datei
        """
        return self.log_filename

    def __repr__(self):
        return f"DiskTestLogger(log_path={self.log_path})"


class LogEntry:
    """
    Repräsentiert einen einzelnen Log-Eintrag

    Wird für GUI-Anzeige verwendet
    """

    def __init__(self, level: LogLevel, message: str, timestamp: Optional[datetime] = None):
        """
        Erstellt einen Log-Eintrag

        Args:
            level: Log-Level
            message: Nachricht
            timestamp: Zeitstempel (Standard: jetzt)
        """
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()

    def format(self, include_date: bool = False) -> str:
        """
        Formatiert den Log-Eintrag

        Args:
            include_date: Datum mit ausgeben (Standard: nur Zeit)

        Returns:
            str: Formatierter Log-Eintrag
        """
        if include_date:
            time_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = self.timestamp.strftime("%H:%M:%S")

        level_str = self.level.value.ljust(7)
        return f"[{time_str}] {level_str} {self.message}"

    def __str__(self):
        return self.format()

    def __repr__(self):
        return f"LogEntry({self.level}, {self.message!r}, {self.timestamp})"
