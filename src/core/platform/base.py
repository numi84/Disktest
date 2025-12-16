"""
Platform-Abstraktion fuer OS-spezifische I/O Operationen.

Dieses Modul definiert das Interface fuer plattform-spezifische Operationen
wie Direct I/O, Cache-Flush und Sektor-Groessen-Ermittlung.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, Optional
import logging


class PlatformIO(ABC):
    """
    Abstrakte Basisklasse fuer plattform-spezifische I/O Operationen.

    Diese Klasse definiert das Interface das von Windows- und POSIX-
    Implementierungen implementiert werden muss.
    """

    def __init__(self, buffer_size: int = 64 * 1024 * 1024):
        """
        Initialisiert Platform I/O.

        Args:
            buffer_size: Buffer-Groesse fuer I/O Operationen in Bytes
        """
        self.buffer_size = buffer_size
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def open_file_direct(self, filepath: Path, mode: str = 'rb') -> Optional[IO]:
        """
        Oeffnet Datei mit direktem Disk-Zugriff (bypass cache wenn moeglich).

        Args:
            filepath: Pfad zur Datei
            mode: Oeffnungsmodus ('rb' fuer Lesen, 'wb' fuer Schreiben)

        Returns:
            File-Objekt oder None bei Fehler
        """
        pass

    @abstractmethod
    def flush_file_cache(self, filepath: Path) -> bool:
        """
        Leert OS-Cache fuer eine Datei.

        Wichtig fuer echte Disk-Verifikation: Ohne Cache-Flush wuerde
        die Verifikation vom RAM-Cache lesen statt von der physischen Disk.

        Args:
            filepath: Pfad zur Datei

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        pass

    @abstractmethod
    def get_sector_size(self, filepath: Path) -> int:
        """
        Ermittelt Sektor-Groesse des Laufwerks.

        Wichtig fuer Direct I/O: Buffer-Adressen, Read/Write-Groessen und
        File-Offsets muessen an Sektor-Grenzen ausgerichtet sein.

        Args:
            filepath: Datei auf dem Laufwerk

        Returns:
            Sektor-Groesse in Bytes (typisch 512 oder 4096)
        """
        pass

    @abstractmethod
    def is_direct_io_available(self) -> bool:
        """
        Prueft ob Direct I/O verfuegbar ist.

        Returns:
            True wenn Direct I/O unterstuetzt wird
        """
        pass
