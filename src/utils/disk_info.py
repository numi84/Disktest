"""
Laufwerksinformationen für DiskTest
Stellt Informationen über Laufwerke und Speicherplatz bereit
"""
import os
import shutil
from pathlib import Path
from typing import Optional


class DiskInfo:
    """
    Utility-Klasse für Laufwerksinformationen

    Alle Methoden sind statisch und können ohne Instanziierung aufgerufen werden.
    """

    @staticmethod
    def get_free_space(path: str) -> int:
        """
        Ermittelt freien Speicherplatz

        Args:
            path: Pfad zum Laufwerk/Verzeichnis

        Returns:
            int: Freier Speicherplatz in Bytes

        Raises:
            ValueError: Wenn Pfad ungültig ist
        """
        if not DiskInfo.is_valid_path(path):
            raise ValueError(f"Ungültiger Pfad: {path}")

        stat = shutil.disk_usage(path)
        return stat.free

    @staticmethod
    def get_total_space(path: str) -> int:
        """
        Ermittelt gesamten Speicherplatz

        Args:
            path: Pfad zum Laufwerk/Verzeichnis

        Returns:
            int: Gesamter Speicherplatz in Bytes

        Raises:
            ValueError: Wenn Pfad ungültig ist
        """
        if not DiskInfo.is_valid_path(path):
            raise ValueError(f"Ungültiger Pfad: {path}")

        stat = shutil.disk_usage(path)
        return stat.total

    @staticmethod
    def get_used_space(path: str) -> int:
        """
        Ermittelt verwendeten Speicherplatz

        Args:
            path: Pfad zum Laufwerk/Verzeichnis

        Returns:
            int: Verwendeter Speicherplatz in Bytes

        Raises:
            ValueError: Wenn Pfad ungültig ist
        """
        if not DiskInfo.is_valid_path(path):
            raise ValueError(f"Ungültiger Pfad: {path}")

        stat = shutil.disk_usage(path)
        return stat.used

    @staticmethod
    def get_drive_letter(path: str) -> Optional[str]:
        """
        Extrahiert den Laufwerksbuchstaben aus einem Pfad (Windows)

        Args:
            path: Pfad zum Laufwerk/Verzeichnis

        Returns:
            str: Laufwerksbuchstabe (z.B. "C") oder None wenn nicht ermittelbar
        """
        try:
            abs_path = os.path.abspath(path)
            # Unter Windows: Erster Teil vor Doppelpunkt
            if os.name == 'nt' and len(abs_path) >= 2 and abs_path[1] == ':':
                return abs_path[0].upper()
        except Exception:
            pass
        return None

    @staticmethod
    def is_valid_path(path: str) -> bool:
        """
        Prüft ob ein Pfad existiert und zugreifbar ist

        Args:
            path: Zu prüfender Pfad

        Returns:
            bool: True wenn Pfad existiert und zugreifbar
        """
        try:
            path_obj = Path(path)
            return path_obj.exists()
        except Exception:
            return False

    @staticmethod
    def is_writable(path: str) -> bool:
        """
        Prüft ob ein Pfad beschreibbar ist

        Args:
            path: Zu prüfender Pfad

        Returns:
            bool: True wenn Pfad beschreibbar ist
        """
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return False

            # Test-Datei erstellen und löschen
            test_file = path_obj / ".disktest_write_test"
            try:
                test_file.touch()
                test_file.unlink()
                return True
            except Exception:
                return False
        except Exception:
            return False

    @staticmethod
    def format_bytes(bytes_value: int, decimals: int = 1) -> str:
        """
        Formatiert Bytes in lesbares Format (KB, MB, GB, TB)

        Args:
            bytes_value: Anzahl Bytes
            decimals: Anzahl Dezimalstellen (Standard: 1)

        Returns:
            str: Formatierter String (z.B. "1.5 GB")
        """
        if bytes_value < 0:
            return "0 B"

        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        unit_index = 0

        value = float(bytes_value)
        while value >= 1024.0 and unit_index < len(units) - 1:
            value /= 1024.0
            unit_index += 1

        # Ganzzahlen ohne Dezimalstellen, sonst mit
        if value == int(value):
            return f"{int(value)} {units[unit_index]}"
        else:
            return f"{value:.{decimals}f} {units[unit_index]}"

    @staticmethod
    def format_bytes_per_second(bytes_per_sec: float, decimals: int = 1) -> str:
        """
        Formatiert Bytes/Sekunde in lesbares Format (KB/s, MB/s, GB/s)

        Args:
            bytes_per_sec: Bytes pro Sekunde
            decimals: Anzahl Dezimalstellen (Standard: 1)

        Returns:
            str: Formatierter String (z.B. "185.3 MB/s")
        """
        if bytes_per_sec < 0:
            return "0 B/s"

        units = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s']
        unit_index = 0

        value = float(bytes_per_sec)
        while value >= 1024.0 and unit_index < len(units) - 1:
            value /= 1024.0
            unit_index += 1

        return f"{value:.{decimals}f} {units[unit_index]}"

    @staticmethod
    def get_disk_info_summary(path: str) -> dict:
        """
        Ermittelt vollständige Disk-Informationen

        Args:
            path: Pfad zum Laufwerk/Verzeichnis

        Returns:
            dict: Dictionary mit allen Informationen
        """
        try:
            return {
                'path': path,
                'exists': DiskInfo.is_valid_path(path),
                'writable': DiskInfo.is_writable(path),
                'drive_letter': DiskInfo.get_drive_letter(path),
                'total_bytes': DiskInfo.get_total_space(path),
                'free_bytes': DiskInfo.get_free_space(path),
                'used_bytes': DiskInfo.get_used_space(path),
                'total_formatted': DiskInfo.format_bytes(DiskInfo.get_total_space(path)),
                'free_formatted': DiskInfo.format_bytes(DiskInfo.get_free_space(path)),
                'used_formatted': DiskInfo.format_bytes(DiskInfo.get_used_space(path))
            }
        except Exception as e:
            return {
                'path': path,
                'exists': False,
                'error': str(e)
            }
