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

    Dateinamen-Schema: disktest_001.dat, disktest_0001.dat, ... (dynamische Stellenzahl)
    """

    # Dateiname-Präfix und -Suffix
    FILE_PREFIX = "disktest_"
    FILE_SUFFIX = ".dat"
    # Glob-Pattern für Testdateien
    FILE_GLOB_PATTERN = f"{FILE_PREFIX}*{FILE_SUFFIX}"

    def __init__(self, target_path: str, file_size_gb: float, file_count: int = None):
        """
        Initialisiert den FileManager

        Args:
            target_path: Zielpfad für Testdateien
            file_size_gb: Größe einer einzelnen Testdatei in GB
            file_count: Optional - Anzahl Dateien zur Berechnung der Stellenzahl

        Raises:
            ValueError: Wenn Parameter ungültig sind
        """
        # Validierung Dateigröße
        if file_size_gb <= 0:
            raise ValueError(f"Dateigröße muss größer als 0 sein, ist: {file_size_gb}")

        if file_size_gb > 10240:  # 10 TB Limit
            raise ValueError(f"Dateigröße zu groß (max 10 TB), ist: {file_size_gb} GB")

        self.target_path = Path(target_path)
        self.file_size_gb = file_size_gb
        self.file_size_bytes = int(file_size_gb * 1024 * 1024 * 1024)

        # Stellenzahl dynamisch berechnen (min 3, max 6)
        # 3 Stellen: 1-999 Dateien
        # 4 Stellen: 1000-9999 Dateien
        # 5 Stellen: 10000-99999 Dateien
        # 6 Stellen: 100000-999999 Dateien
        if file_count is not None:
            self._digits = self._calculate_digits(file_count)
        else:
            # Default: 3 Stellen (abwärtskompatibel)
            self._digits = 3

        # Validierung Pfad
        if not self.target_path.exists():
            raise ValueError(f"Pfad existiert nicht: {target_path}")
        if not self.target_path.is_dir():
            raise ValueError(f"Pfad ist kein Verzeichnis: {target_path}")

    def _calculate_digits(self, file_count: int) -> int:
        """
        Berechnet die benötigte Stellenzahl für Dateinamen

        Args:
            file_count: Anzahl der Dateien

        Returns:
            int: Stellenzahl (3-6)
        """
        if file_count < 1000:
            return 3
        elif file_count < 10000:
            return 4
        elif file_count < 100000:
            return 5
        else:
            return 6

    def calculate_file_count(self, total_size_gb: float) -> int:
        """
        Berechnet die Anzahl der benötigten Testdateien

        Args:
            total_size_gb: Gewünschte Gesamtgröße des Tests in GB

        Returns:
            int: Anzahl der Testdateien (mindestens 1)

        Raises:
            ValueError: Wenn total_size_gb ungültig ist
        """
        if total_size_gb <= 0:
            raise ValueError(f"Gesamtgröße muss größer als 0 sein, ist: {total_size_gb}")

        if total_size_gb > 1000000:  # 1 PB Limit (1000 TB)
            raise ValueError(f"Gesamtgröße zu groß (max 1 PB), ist: {total_size_gb} GB")

        # file_size_gb wurde bereits im Constructor validiert, also kein Division-by-Zero möglich
        count = int(total_size_gb / self.file_size_gb)
        # Mindestens 1 Datei
        count = max(1, count)

        # Limit auf 999999 Dateien (6-stellig)
        if count > 999999:
            raise ValueError(
                f"Zu viele Dateien ({count}), max 999999\n"
                f"Tipp: Nutze größere Dateigrößen statt mehr Dateien"
            )

        return count

    def get_file_path(self, index: int) -> Path:
        """
        Generiert den Pfad für eine Testdatei

        Args:
            index: Index der Datei (0-basiert)

        Returns:
            Path: Vollständiger Pfad zur Testdatei

        Raises:
            ValueError: Wenn Index außerhalb des gültigen Bereichs
        """
        if index < 0:
            raise ValueError(f"Index muss >= 0 sein, ist: {index}")

        max_index = (10 ** self._digits) - 1
        if index >= max_index:
            raise ValueError(
                f"Index zu groß (max {max_index - 1} für {self._digits}-stellige Nummern), ist: {index}\n"
                f"Tipp: Nutze größere Dateigrößen statt mehr Dateien"
            )

        # Index ist 0-basiert, aber Dateinamen starten bei 001 (bzw. 0001, 00001, etc.)
        filename = f"{self.FILE_PREFIX}{index + 1:0{self._digits}d}{self.FILE_SUFFIX}"
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

    def migrate_old_filenames(self, file_count: int) -> tuple[int, int]:
        """
        Migriert alte Dateinamen zu neuem Schema mit anderer Stellenzahl

        Prüft ob vorhandene Dateien eine andere Stellenzahl haben.
        Falls ja, werden alle Dateien auf die neue Stellenzahl umbenannt.

        Args:
            file_count: Anzahl erwarteter Dateien

        Returns:
            tuple: (Anzahl umbenannte Dateien, Anzahl Fehler)
        """
        renamed = 0
        errors = 0

        # Finde alle vorhandenen Dateien
        existing_files = list(self.target_path.glob(self.FILE_GLOB_PATTERN))

        if not existing_files:
            return (0, 0)

        # Erkenne Stellenzahl der ersten Datei (alle sollten gleich sein)
        first_file = existing_files[0]
        index_str = first_file.name[len(self.FILE_PREFIX):-len(self.FILE_SUFFIX)]

        if not index_str.isdigit():
            return (0, 0)

        old_digits = len(index_str)

        # Wenn Stellenzahl bereits korrekt, nichts zu tun
        if old_digits == self._digits:
            return (0, 0)

        logger.info(f"Migration: Erkannte alte Stellenzahl: {old_digits}, neue Stellenzahl: {self._digits}")

        # Migriere alle Dateien
        for old_filepath in existing_files:
            try:
                # Extrahiere Index aus altem Namen
                old_name = old_filepath.name
                index_str = old_name[len(self.FILE_PREFIX):-len(self.FILE_SUFFIX)]

                # Prüfe ob numerisch
                if not index_str.isdigit():
                    continue

                # Nur Dateien mit alter Stellenzahl migrieren
                if len(index_str) != old_digits:
                    continue

                # Parse Index (1-basiert im Dateinamen)
                file_number = int(index_str)

                # Generiere neuen Namen mit neuer Stellenzahl
                new_filename = f"{self.FILE_PREFIX}{file_number:0{self._digits}d}{self.FILE_SUFFIX}"
                new_filepath = self.target_path / new_filename

                # Umbenennen
                old_filepath.rename(new_filepath)
                renamed += 1
                logger.info(f"Datei umbenannt: {old_name} → {new_filename}")

            except Exception as e:
                errors += 1
                logger.error(f"Fehler beim Umbenennen von {old_filepath}: {e}")

        if renamed > 0:
            logger.info(f"Migration abgeschlossen: {renamed} Dateien umbenannt, {errors} Fehler")

        return (renamed, errors)

    def __repr__(self):
        return (f"FileManager(target_path={self.target_path}, "
                f"file_size_gb={self.file_size_gb}, digits={self._digits})")
