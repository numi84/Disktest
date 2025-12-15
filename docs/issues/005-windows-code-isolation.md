# Issue #005: Windows-spezifischer Code isolieren

## Priorität: 🟡 Mittel

## Beschreibung
Windows-spezifischer Code (ctypes, WinAPI) ist direkt in `test_engine.py` eingebettet, was:
- Code-Lesbarkeit erschwert
- Testing kompliziert macht
- Plattform-unabhängigen Code vermischt

## Betroffene Dateien
- `src/core/test_engine.py:606-641` (NO_BUFFERING File-Opening)
- `src/core/test_engine.py:793-824` (Cache-Flush)

## Aktueller Code

### Problem 1: File-Opening mit 35 Zeilen Windows-Code
```python
# test_engine.py:604-641
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    # ... weitere 30 Zeilen Windows-Code

    handle = kernel32.CreateFileW(...)
    fd = msvcrt.open_osfhandle(...)
    f = os.fdopen(fd, 'rb', self.IO_BUFFER_SIZE)
else:
    f = open(filepath, 'rb', buffering=self.IO_BUFFER_SIZE)
```

### Problem 2: Cache-Flush mit 30 Zeilen Windows-Code
```python
# test_engine.py:793-824
if sys.platform == 'win32':
    import ctypes
    # ... 25 Zeilen Windows-Code
    psapi.EmptyWorkingSet(current_process)
else:
    # Linux
    os.posix_fadvise(fd, 0, 0, 4)
```

## Lösungsvorschlag: Platform-Module

### Neue Struktur
```
src/core/platform/
├── __init__.py
├── base.py           # Abstract base classes
├── windows.py        # Windows-Implementierung
└── posix.py          # Linux/Unix-Implementierung
```

### 1. base.py - Abstract Interface

```python
"""
Platform-abstraction für OS-spezifische Operationen
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, Optional

class PlatformIO(ABC):
    """Abstract base class für plattform-spezifische I/O Operationen"""

    @abstractmethod
    def open_file_direct(self, filepath: Path, mode: str = 'rb') -> Optional[IO]:
        """
        Öffnet Datei mit direktem Disk-Zugriff (bypass cache wenn möglich)

        Args:
            filepath: Pfad zur Datei
            mode: Öffnungsmodus ('rb', 'wb', etc.)

        Returns:
            File-Objekt oder None bei Fehler
        """
        pass

    @abstractmethod
    def flush_file_cache(self, filepath: Path) -> bool:
        """
        Leert OS-Cache für eine Datei

        Args:
            filepath: Pfad zur Datei

        Returns:
            True wenn erfolgreich
        """
        pass

    @abstractmethod
    def get_sector_size(self, filepath: Path) -> int:
        """
        Ermittelt Sektor-Größe des Laufwerks

        Args:
            filepath: Datei auf dem Laufwerk

        Returns:
            Sektor-Größe in Bytes
        """
        pass

    @abstractmethod
    def is_direct_io_available(self) -> bool:
        """
        Prüft ob Direct I/O verfügbar ist

        Returns:
            True wenn Direct I/O unterstützt wird
        """
        pass
```

### 2. windows.py - Windows-Implementierung

```python
"""
Windows-spezifische I/O Implementierung
"""
import os
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import IO, Optional
import logging

from .base import PlatformIO

logger = logging.getLogger(__name__)


class WindowsIO(PlatformIO):
    """Windows-Implementierung für Direct I/O und Cache-Management"""

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
        Initialisiert Windows I/O

        Args:
            buffer_size: Buffer-Größe für I/O Operationen
        """
        self.buffer_size = buffer_size
        self.kernel32 = ctypes.windll.kernel32
        self.psapi = ctypes.windll.psapi

    def open_file_direct(self, filepath: Path, mode: str = 'rb') -> Optional[IO]:
        """
        Öffnet Datei mit FILE_FLAG_NO_BUFFERING

        Args:
            filepath: Pfad zur Datei
            mode: 'rb' (Read) oder 'wb' (Write)

        Returns:
            File-Objekt oder None bei Fehler
        """
        try:
            # Access-Flags basierend auf Modus
            if 'r' in mode:
                access = self.GENERIC_READ
                creation = self.OPEN_EXISTING
            elif 'w' in mode:
                access = self.GENERIC_WRITE
                creation = self.CREATE_ALWAYS
            else:
                logger.error(f"Ungültiger Modus: {mode}")
                return None

            # Öffne mit NO_BUFFERING für direkten Disk-Zugriff
            handle = self.kernel32.CreateFileW(
                str(filepath),
                access,
                self.FILE_SHARE_READ | self.FILE_SHARE_WRITE,
                None,
                creation,
                self.FILE_FLAG_NO_BUFFERING | self.FILE_FLAG_SEQUENTIAL_SCAN,
                None
            )

            # Prüfe auf Fehler
            if handle == self.INVALID_HANDLE_VALUE or handle == 0xFFFFFFFF:
                error_code = self.kernel32.GetLastError()
                logger.warning(f"CreateFileW fehlgeschlagen: Error {error_code}")
                return None

            # Validiere Sector-Alignment
            sector_size = self.get_sector_size(filepath)
            if self.buffer_size % sector_size != 0:
                logger.warning(
                    f"Buffer-Größe {self.buffer_size} nicht aligned zu "
                    f"Sector-Größe {sector_size}"
                )
                self.kernel32.CloseHandle(handle)
                return None

            # Konvertiere Windows-Handle zu Python-File-Descriptor
            import msvcrt
            if 'r' in mode:
                flags = os.O_RDONLY | os.O_BINARY
            else:
                flags = os.O_WRONLY | os.O_BINARY

            fd = msvcrt.open_osfhandle(handle, flags)

            # Erstelle File-Objekt (unbuffered für NO_BUFFERING)
            f = os.fdopen(fd, mode, 0)  # buffering=0
            return f

        except Exception as e:
            logger.error(f"Fehler beim Öffnen von {filepath}: {e}")
            return None

    def flush_file_cache(self, filepath: Path) -> bool:
        """
        Leert Windows File-Cache

        Strategie:
        1. EmptyWorkingSet() - Leert Prozess-Cache
        2. FlushFileBuffers() - Schreibt Änderungen auf Disk
        3. Wartezeit für OS-Cache-Management

        Args:
            filepath: Pfad zur Datei

        Returns:
            True wenn erfolgreich
        """
        try:
            # 1. Working Set leeren
            current_process = self.kernel32.GetCurrentProcess()
            result = self.psapi.EmptyWorkingSet(current_process)

            if not result:
                logger.warning("EmptyWorkingSet fehlgeschlagen")

            # 2. File-Buffer flushen
            handle = self.kernel32.CreateFileW(
                str(filepath),
                self.GENERIC_READ,
                self.FILE_SHARE_READ | self.FILE_SHARE_WRITE,
                None,
                self.OPEN_EXISTING,
                0,
                None
            )

            if handle != self.INVALID_HANDLE_VALUE and handle != 0xFFFFFFFF:
                self.kernel32.FlushFileBuffers(handle)
                self.kernel32.CloseHandle(handle)

            # 3. Warte damit OS Cache leeren kann
            time.sleep(0.5)

            logger.debug(f"Cache geflusht für {filepath.name}")
            return True

        except Exception as e:
            logger.warning(f"Cache-Flush fehlgeschlagen für {filepath}: {e}")
            return False

    def get_sector_size(self, filepath: Path) -> int:
        """
        Ermittelt Sektor-Größe des Laufwerks

        Args:
            filepath: Datei auf dem Laufwerk

        Returns:
            Sektor-Größe in Bytes (Standard: 4096)
        """
        try:
            # Extrahiere Laufwerksbuchstaben
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
                logger.debug(f"Sektor-Größe für {drive_letter}: {sector_size} Bytes")
                return sector_size

        except Exception as e:
            logger.warning(f"Konnte Sektor-Größe nicht ermitteln: {e}")

        # Default: 4096 Bytes (gängig für moderne HDDs/SSDs)
        return 4096

    def is_direct_io_available(self) -> bool:
        """
        Prüft ob FILE_FLAG_NO_BUFFERING verfügbar ist

        Returns:
            True (immer verfügbar unter Windows)
        """
        return True
```

### 3. posix.py - Linux/Unix-Implementierung

```python
"""
POSIX-spezifische I/O Implementierung (Linux, macOS, etc.)
"""
import os
from pathlib import Path
from typing import IO, Optional
import logging

from .base import PlatformIO

logger = logging.getLogger(__name__)


class PosixIO(PlatformIO):
    """POSIX-Implementierung für Direct I/O"""

    def __init__(self, buffer_size: int = 64 * 1024 * 1024):
        self.buffer_size = buffer_size

    def open_file_direct(self, filepath: Path, mode: str = 'rb') -> Optional[IO]:
        """
        Öffnet Datei mit O_DIRECT (falls verfügbar)

        Note: O_DIRECT unter Linux ist komplex und nicht immer verfügbar
        Fallback: Standard-I/O
        """
        try:
            # O_DIRECT ist nicht portable - nutze Standard-I/O
            # Für echtes Direct I/O: mmap oder io_uring verwenden
            return open(filepath, mode, buffering=self.buffer_size)
        except Exception as e:
            logger.error(f"Fehler beim Öffnen von {filepath}: {e}")
            return None

    def flush_file_cache(self, filepath: Path) -> bool:
        """
        Leert POSIX File-Cache mit posix_fadvise
        """
        try:
            fd = os.open(str(filepath), os.O_RDONLY)
            try:
                # POSIX_FADV_DONTNEED = 4
                # Teilt Kernel mit dass Daten nicht mehr benötigt werden
                os.posix_fadvise(fd, 0, 0, 4)
                logger.debug(f"Cache geflusht für {filepath.name}")
                return True
            finally:
                os.close(fd)
        except Exception as e:
            logger.warning(f"Cache-Flush fehlgeschlagen für {filepath}: {e}")
            return False

    def get_sector_size(self, filepath: Path) -> int:
        """Ermittelt Sektor-Größe (meist 512 oder 4096)"""
        try:
            # Linux: ioctl BLKSSZGET
            # Für Einfachheit: Default
            pass
        except Exception:
            pass

        return 4096

    def is_direct_io_available(self) -> bool:
        """O_DIRECT ist verfügbar aber komplex zu nutzen"""
        return hasattr(os, 'O_DIRECT')
```

### 4. __init__.py - Factory

```python
"""
Platform I/O Factory
"""
import sys
from .base import PlatformIO
from .windows import WindowsIO
from .posix import PosixIO


def get_platform_io(buffer_size: int = 64 * 1024 * 1024) -> PlatformIO:
    """
    Factory-Methode für plattform-spezifisches I/O

    Args:
        buffer_size: Buffer-Größe für I/O

    Returns:
        PlatformIO-Implementierung für aktuelles OS
    """
    if sys.platform == 'win32':
        return WindowsIO(buffer_size)
    else:
        return PosixIO(buffer_size)


__all__ = ['PlatformIO', 'get_platform_io']
```

### 5. test_engine.py - Verwendung

```python
# test_engine.py
from core.platform import get_platform_io

class TestEngine(QThread):
    def __init__(self, config: TestConfig):
        super().__init__()
        # ...

        # Platform I/O initialisieren
        self.platform_io = get_platform_io(self.IO_BUFFER_SIZE)

    def _verify_file(self, filepath: Path, generator: PatternGenerator) -> bool:
        """Verifiziert eine einzelne Testdatei"""
        # ...

        # Cache-Flush - jetzt plattform-unabhängig!
        self.platform_io.flush_file_cache(filepath)

        try:
            # Versuche Direct I/O
            f = self.platform_io.open_file_direct(filepath, 'rb')

            if f is None:
                # Fallback: Standard-I/O
                self.logger.warning(f"{filepath.name} - Direct I/O nicht verfügbar")
                f = open(filepath, 'rb', buffering=self.IO_BUFFER_SIZE)

            with f:
                # ... Verifikations-Logik (unverändert)
```

## Vorteile

1. ✅ **Lesbarkeit:** test_engine.py hat keine Windows-spezifischen Details mehr
2. ✅ **Testbarkeit:** PlatformIO kann gemockt werden
3. ✅ **Erweiterbarkeit:** Neue Plattformen einfach hinzufügen (z.B. macOS-spezifisch)
4. ✅ **Wartbarkeit:** Windows-Code an einem Ort
5. ✅ **Wiederverwendbarkeit:** platform-Module können in anderen Projekten genutzt werden

## Migration

1. Erstelle `src/core/platform/` Struktur
2. Implementiere `windows.py` mit existierendem Code
3. Implementiere `posix.py` (einfach)
4. Erstelle Factory in `__init__.py`
5. Refaktoriere `test_engine.py`:
   - Ersetze `if sys.platform == 'win32':` durch `self.platform_io.flush_file_cache()`
   - Entferne ctypes-Imports
6. Tests hinzufügen für PlatformIO

## Testing

```python
# test_platform_io.py
import pytest
from core.platform import get_platform_io
from core.platform.windows import WindowsIO
from core.platform.posix import PosixIO

def test_factory_returns_correct_platform():
    """Test dass Factory richtige Platform-Implementierung zurückgibt"""
    io = get_platform_io()

    if sys.platform == 'win32':
        assert isinstance(io, WindowsIO)
    else:
        assert isinstance(io, PosixIO)

def test_windows_direct_io(tmp_path):
    """Test Windows Direct I/O"""
    if sys.platform != 'win32':
        pytest.skip("Windows-only test")

    io = WindowsIO()
    test_file = tmp_path / "test.dat"

    # Schreibe Testdatei
    with open(test_file, 'wb') as f:
        f.write(b'X' * 4096)  # Sector-aligned

    # Öffne mit Direct I/O
    f = io.open_file_direct(test_file, 'rb')
    assert f is not None

    data = f.read(4096)
    assert data == b'X' * 4096
    f.close()
```

## Zeitaufwand
- Struktur erstellen: 30 Min
- windows.py implementieren: 2 Stunden
- posix.py implementieren: 1 Stunde
- test_engine.py refactoren: 1 Stunde
- Tests schreiben: 1 Stunde
**Gesamt:** ~5-6 Stunden
