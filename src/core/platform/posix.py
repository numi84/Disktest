"""
POSIX-spezifische I/O Implementierung (Linux, macOS, etc.).

Dieses Modul enthaelt POSIX-konforme Operationen fuer:
- Standard I/O (O_DIRECT ist komplex und nicht portabel)
- posix_fadvise fuer Cache-Flush
"""
import os
from pathlib import Path
from typing import IO, Optional
import logging

from .base import PlatformIO


class PosixIO(PlatformIO):
    """
    POSIX-Implementierung fuer I/O Operationen.

    Nutzt Standard POSIX-Funktionen:
    - Standard open() fuer Dateizugriff
    - posix_fadvise mit POSIX_FADV_DONTNEED fuer Cache-Flush
    """

    # POSIX_FADV_DONTNEED = 4
    # Teilt Kernel mit dass Daten nicht mehr benoetigt werden
    POSIX_FADV_DONTNEED = 4

    def __init__(self, buffer_size: int = 64 * 1024 * 1024):
        """
        Initialisiert POSIX I/O.

        Args:
            buffer_size: Buffer-Groesse fuer I/O Operationen
        """
        super().__init__(buffer_size)
        self.logger = logging.getLogger(__name__)

    def open_file_direct(self, filepath: Path, mode: str = 'rb') -> Optional[IO]:
        """
        Oeffnet Datei mit Standard I/O.

        Note: O_DIRECT unter Linux ist komplex (alignment requirements,
        nicht alle Dateisysteme unterstuetzen es) und nicht portabel.
        Fuer echtes Direct I/O waere mmap oder io_uring besser geeignet.

        Da DiskTest primaer fuer Windows entwickelt ist, nutzen wir hier
        einfach Standard I/O mit grossem Buffer.

        Args:
            filepath: Pfad zur Datei
            mode: Oeffnungsmodus ('rb', 'wb', etc.)

        Returns:
            File-Objekt oder None bei Fehler
        """
        try:
            return open(filepath, mode, buffering=self.buffer_size)
        except Exception as e:
            self.logger.error(f"Fehler beim Oeffnen von {filepath}: {e}")
            return None

    def flush_file_cache(self, filepath: Path) -> bool:
        """
        Leert POSIX File-Cache mit posix_fadvise.

        posix_fadvise mit POSIX_FADV_DONTNEED teilt dem Kernel mit,
        dass die angegebenen Seiten nicht mehr benoetigt werden und
        aus dem Page Cache entfernt werden koennen.

        Args:
            filepath: Pfad zur Datei

        Returns:
            True wenn erfolgreich
        """
        try:
            fd = os.open(str(filepath), os.O_RDONLY)
            try:
                # POSIX_FADV_DONTNEED = 4
                # Teilt Kernel mit dass Daten nicht mehr benoetigt werden
                os.posix_fadvise(fd, 0, 0, self.POSIX_FADV_DONTNEED)
                self.logger.debug(f"Cache-Flush durchgefuehrt fuer {filepath.name}")
                return True
            finally:
                os.close(fd)
        except AttributeError:
            # posix_fadvise nicht verfuegbar (z.B. aeltere Python-Versionen, macOS)
            self.logger.warning(
                f"posix_fadvise nicht verfuegbar - Cache-Flush uebersprungen fuer {filepath.name}"
            )
            return False
        except Exception as e:
            self.logger.warning(f"Cache-Flush fehlgeschlagen fuer {filepath}: {e}")
            return False

    def get_sector_size(self, filepath: Path) -> int:
        """
        Ermittelt Sektor-Groesse (meist 512 oder 4096).

        Unter Linux koennte man ioctl BLKSSZGET nutzen, aber das erfordert
        Root-Rechte und Zugriff auf das Block-Device.

        Da DiskTest primaer fuer Windows entwickelt ist, geben wir hier
        einen vernuenftigen Default zurueck.

        Args:
            filepath: Datei auf dem Laufwerk

        Returns:
            Sektor-Groesse in Bytes (Default: 4096)
        """
        # Default: 4096 Bytes (gaengig fuer moderne HDDs/SSDs)
        return 4096

    def is_direct_io_available(self) -> bool:
        """
        Prueft ob O_DIRECT verfuegbar ist.

        Returns:
            True wenn O_DIRECT als Flag existiert
        """
        return hasattr(os, 'O_DIRECT')
