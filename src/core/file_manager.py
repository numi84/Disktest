"""
Testdatei-Verwaltung für DiskTest
Verwaltet Erstellung, Zugriff und Löschung der Testdateien
"""
import logging
import os
import shutil
from pathlib import Path
from typing import List

# Modul-Logger
logger = logging.getLogger(__name__)


class FileManager:
    """
    Verwaltet die Testdateien

    Dateinamen-Schema: disktest_001.dat, disktest_002.dat, ...
    """

    # Dateiname-Präfix und -Suffix
    FILE_PREFIX = "disktest_"
    FILE_SUFFIX = ".dat"
    # Glob-Pattern für Testdateien
    FILE_GLOB_PATTERN = f"{FILE_PREFIX}*{FILE_SUFFIX}"

    def __init__(self, target_path: str, file_size_gb: float):
        """
        Initialisiert den FileManager

        Args:
            target_path: Zielpfad für Testdateien
            file_size_gb: Größe einer einzelnen Testdatei in GB
        """
        self.target_path = Path(target_path)
        self.file_size_gb = file_size_gb
        self.file_size_bytes = int(file_size_gb * 1024 * 1024 * 1024)

        # Validierung
        if not self.target_path.exists():
            raise ValueError(f"Pfad existiert nicht: {target_path}")
        if not self.target_path.is_dir():
            raise ValueError(f"Pfad ist kein Verzeichnis: {target_path}")

    def calculate_file_count(self, total_size_gb: float) -> int:
        """
        Berechnet die Anzahl der benötigten Testdateien

        Args:
            total_size_gb: Gewünschte Gesamtgröße des Tests in GB

        Returns:
            int: Anzahl der Testdateien
        """
        if total_size_gb <= 0:
            raise ValueError("Gesamtgröße muss größer als 0 sein")

        count = int(total_size_gb / self.file_size_gb)
        # Mindestens 1 Datei
        return max(1, count)

    def get_file_path(self, index: int) -> Path:
        """
        Generiert den Pfad für eine Testdatei

        Args:
            index: Index der Datei (0-basiert)

        Returns:
            Path: Vollständiger Pfad zur Testdatei
        """
        # Index ist 0-basiert, aber Dateinamen starten bei 001
        filename = f"{self.FILE_PREFIX}{index + 1:03d}{self.FILE_SUFFIX}"
        return self.target_path / filename

    def get_all_file_paths(self, file_count: int) -> List[Path]:
        """
        Generiert Pfade für alle Testdateien

        Args:
            file_count: Anzahl der Testdateien

        Returns:
            List[Path]: Liste aller Testdatei-Pfade
        """
        return [self.get_file_path(i) for i in range(file_count)]

    def delete_test_files(self) -> tuple[int, int]:
        """
        Löscht alle Testdateien im Zielpfad

        Returns:
            tuple: (Anzahl gelöschte Dateien, Anzahl Fehler)
        """
        deleted = 0
        errors = 0

        # Suche alle disktest_*.dat Dateien
        for filepath in self.target_path.glob(self.FILE_GLOB_PATTERN):
            try:
                filepath.unlink()
                deleted += 1
            except Exception as e:
                errors += 1
                logger.error(f"Fehler beim Löschen von {filepath}: {e}")

        return deleted, errors

    def get_free_space(self) -> int:
        """
        Ermittelt freien Speicherplatz im Zielpfad

        Returns:
            int: Freier Speicherplatz in Bytes
        """
        stat = shutil.disk_usage(self.target_path)
        return stat.free

    def get_total_space(self) -> int:
        """
        Ermittelt gesamten Speicherplatz im Zielpfad

        Returns:
            int: Gesamter Speicherplatz in Bytes
        """
        stat = shutil.disk_usage(self.target_path)
        return stat.total

    def files_exist(self) -> bool:
        """
        Prüft ob Testdateien existieren

        Returns:
            bool: True wenn mindestens eine Testdatei existiert
        """
        return any(self.target_path.glob(self.FILE_GLOB_PATTERN))

    def count_existing_files(self) -> int:
        """
        Zählt existierende Testdateien

        Returns:
            int: Anzahl existierender Testdateien
        """
        return len(list(self.target_path.glob(self.FILE_GLOB_PATTERN)))

    def get_existing_files_size(self) -> int:
        """
        Berechnet Gesamtgröße existierender Testdateien

        Returns:
            int: Größe in Bytes
        """
        total_size = 0
        for filepath in self.target_path.glob(self.FILE_GLOB_PATTERN):
            try:
                total_size += filepath.stat().st_size
            except Exception as e:
                logger.warning(f"Konnte Dateigröße nicht ermitteln für {filepath}: {e}")
        return total_size

    def __repr__(self):
        return (f"FileManager(target_path={self.target_path}, "
                f"file_size_gb={self.file_size_gb})")
