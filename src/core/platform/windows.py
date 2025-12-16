"""
Windows-spezifische I/O Implementierung.

Dieses Modul enthaelt alle Windows-spezifischen Operationen wie:
- FILE_FLAG_NO_BUFFERING fuer Direct I/O
- EmptyWorkingSet/FlushFileBuffers fuer Cache-Flush
- GetDiskFreeSpaceW fuer Sektor-Groessen-Ermittlung
"""
import os
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import IO, Optional
import logging

from .base import PlatformIO


class WindowsIO(PlatformIO):
    """
    Windows-Implementierung fuer Direct I/O und Cache-Management.

    Nutzt die Windows API (kernel32.dll, psapi.dll) fuer:
    - CreateFileW mit FILE_FLAG_NO_BUFFERING
    - EmptyWorkingSet zum Leeren des Prozess-Cache
    - FlushFileBuffers zum Schreiben auf Disk
    - GetDiskFreeSpaceW fuer Sektor-Groesse
    """

    # Windows API Konstanten
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    CREATE_ALWAYS = 2
    FILE_FLAG_NO_BUFFERING = 0x20000000
    FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
    FILE_FLAG_WRITE_THROUGH = 0x80000000
    INVALID_HANDLE_VALUE = -1

    def __init__(self, buffer_size: int = 64 * 1024 * 1024):
        """
        Initialisiert Windows I/O.

        Args:
            buffer_size: Buffer-Groesse fuer I/O Operationen
        """
        super().__init__(buffer_size)
        self.logger = logging.getLogger(__name__)

        # Lade Windows DLLs
        self.kernel32 = ctypes.windll.kernel32
        self.psapi = ctypes.windll.psapi

    def open_file_direct(self, filepath: Path, mode: str = 'rb') -> Optional[IO]:
        """
        Oeffnet Datei mit FILE_FLAG_NO_BUFFERING unter Windows.

        FILE_FLAG_NO_BUFFERING umgeht den Windows-Cache und erzwingt direktes
        Lesen von der physischen Disk. Dies ist wichtig fuer die Verifikation.

        Anforderungen:
        - Buffer-Adresse muss sector-aligned sein
        - Read/Write-Groesse muss Vielfaches der Sektor-Groesse sein
        - File-Offset muss sector-aligned sein

        Args:
            filepath: Pfad zur zu oeffnenden Datei
            mode: 'rb' (Read) oder 'wb' (Write)

        Returns:
            File-Objekt oder None bei Fehler
        """
        try:
            # Access-Flags basierend auf Modus
            if 'r' in mode:
                access = self.GENERIC_READ
                creation = self.OPEN_EXISTING
                os_flags = os.O_RDONLY | os.O_BINARY
            elif 'w' in mode:
                access = self.GENERIC_WRITE
                creation = self.CREATE_ALWAYS
                os_flags = os.O_WRONLY | os.O_BINARY
            else:
                self.logger.error(f"Ungueltiger Modus: {mode}")
                return None

            # Oeffne mit NO_BUFFERING fuer direktes Disk-I/O
            handle = self.kernel32.CreateFileW(
                str(filepath),
                access,
                self.FILE_SHARE_READ | self.FILE_SHARE_WRITE,
                None,
                creation,
                self.FILE_FLAG_NO_BUFFERING | self.FILE_FLAG_SEQUENTIAL_SCAN,
                None
            )

            # Korrekte INVALID_HANDLE_VALUE Pruefung
            # Windows kann -1 (signed) oder 0xFFFFFFFF (unsigned) zurueckgeben
            if handle == self.INVALID_HANDLE_VALUE or handle == 0xFFFFFFFF or handle == 0:
                self.logger.debug(f"{filepath.name} - CreateFileW fehlgeschlagen (INVALID_HANDLE)")
                return None

            # Pruefe Sektor-Groesse und validiere Buffer-Groesse
            sector_size = self.get_sector_size(filepath)

            if self.buffer_size % sector_size != 0:
                self.logger.warning(
                    f"Buffer-Groesse {self.buffer_size} nicht aligned zu "
                    f"Sektor-Groesse {sector_size}"
                )
                self.kernel32.CloseHandle(handle)
                return None

            # Konvertiere Windows-Handle zu Python-File
            import msvcrt
            fd = msvcrt.open_osfhandle(handle, os_flags)

            # Verwende unbuffered I/O (buffering=0) fuer NO_BUFFERING
            # Wichtig: Bei buffering>0 koennte Python's interner Buffer nicht aligned sein
            f = os.fdopen(fd, mode, 0)
            return f

        except Exception as e:
            self.logger.warning(f"NO_BUFFERING fehlgeschlagen: {e}")
            return None

    def flush_file_cache(self, filepath: Path) -> bool:
        """
        Leert Windows File-Cache.

        Strategie:
        1. EmptyWorkingSet() - Leert den RAM-Cache des Prozesses
        2. FlushFileBuffers() - Forciert Schreiben von File-Buffern auf Disk
        3. Ausreichend Zeit warten (0.5s) fuer asynchrone Cache-Operationen

        Args:
            filepath: Pfad zur Datei

        Returns:
            True wenn erfolgreich
        """
        try:
            # 1. Leere Working Set des eigenen Prozesses
            # Dies gibt den RAM-Cache unseres Prozesses frei
            current_process = self.kernel32.GetCurrentProcess()
            result = self.psapi.EmptyWorkingSet(current_process)

            if not result:
                self.logger.warning("EmptyWorkingSet fehlgeschlagen")

            # 2. File-Buffer explizit flushen
            # Oeffne Datei mit GENERIC_READ fuer nicht-destruktiven Zugriff
            handle = self.kernel32.CreateFileW(
                str(filepath),
                self.GENERIC_READ,
                0,  # Exclusive access
                None,
                self.OPEN_EXISTING,
                0,
                None
            )

            # FlushFileBuffers nur wenn Handle gueltig ist
            if handle != self.INVALID_HANDLE_VALUE and handle != 0:
                self.kernel32.FlushFileBuffers(handle)
                self.kernel32.CloseHandle(handle)

            # 3. Warte ausreichend lange damit OS Cache wirklich geleert wird
            # EmptyWorkingSet() ist asynchron - 0.5s Wartezeit ist konservativ
            time.sleep(0.5)

            self.logger.debug(f"Cache-Flush durchgefuehrt fuer {filepath.name}")
            return True

        except Exception as e:
            self.logger.warning(f"Cache-Flush fehlgeschlagen fuer {filepath}: {e}")
            return False

    def get_sector_size(self, filepath: Path) -> int:
        """
        Ermittelt die Sektor-Groesse des Laufwerks.

        Wichtig fuer FILE_FLAG_NO_BUFFERING: Windows erfordert dass Buffer-Adressen,
        Read/Write-Groessen und File-Offsets an Sektor-Grenzen ausgerichtet sind.

        Args:
            filepath: Pfad zur Datei auf dem Ziellaufwerk

        Returns:
            Sektor-Groesse in Bytes (typisch 512 oder 4096)
        """
        try:
            # Extrahiere Laufwerksbuchstaben (z.B. "C:" -> "C:\\")
            drive_letter = str(filepath.resolve().drive)
            if not drive_letter.endswith('\\'):
                drive_letter += '\\'

            sectors_per_cluster = ctypes.c_ulonglong()
            bytes_per_sector = ctypes.c_ulonglong()
            free_clusters = ctypes.c_ulonglong()
            total_clusters = ctypes.c_ulonglong()

            result = self.kernel32.GetDiskFreeSpaceW(
                drive_letter,
                ctypes.byref(sectors_per_cluster),
                ctypes.byref(bytes_per_sector),
                ctypes.byref(free_clusters),
                ctypes.byref(total_clusters)
            )

            if result:
                sector_size = int(bytes_per_sector.value)
                self.logger.debug(f"Laufwerk {drive_letter} Sektor-Groesse: {sector_size} Bytes")
                return sector_size

        except Exception as e:
            self.logger.warning(f"Konnte Sektor-Groesse nicht ermitteln: {e}")

        # Default: 4096 Bytes (gaengig fuer moderne HDDs/SSDs)
        return 4096

    def is_direct_io_available(self) -> bool:
        """
        Prueft ob FILE_FLAG_NO_BUFFERING verfuegbar ist.

        Returns:
            True (immer verfuegbar unter Windows)
        """
        return True
