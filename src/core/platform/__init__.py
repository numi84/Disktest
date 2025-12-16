"""
Platform I/O Abstraktion.

Dieses Modul stellt eine plattform-unabhaengige Schnittstelle fuer
OS-spezifische I/O Operationen bereit.

Verwendung:
    from core.platform import get_platform_io

    platform_io = get_platform_io(buffer_size=64 * 1024 * 1024)
    platform_io.flush_file_cache(filepath)
    f = platform_io.open_file_direct(filepath, 'rb')
"""
import sys

from .base import PlatformIO


def get_platform_io(buffer_size: int = 64 * 1024 * 1024) -> PlatformIO:
    """
    Factory-Methode fuer plattform-spezifisches I/O.

    Gibt die passende Implementierung fuer das aktuelle Betriebssystem zurueck:
    - Windows: WindowsIO mit FILE_FLAG_NO_BUFFERING, EmptyWorkingSet, etc.
    - Linux/Unix: PosixIO mit posix_fadvise

    Args:
        buffer_size: Buffer-Groesse fuer I/O Operationen in Bytes

    Returns:
        PlatformIO-Implementierung fuer aktuelles OS
    """
    if sys.platform == 'win32':
        from .windows import WindowsIO
        return WindowsIO(buffer_size)
    else:
        from .posix import PosixIO
        return PosixIO(buffer_size)


def get_window_activator():
    """
    Gibt plattform-spezifische Window-Aktivierungs-Funktion zurueck.

    Usage:
        from core.platform import get_window_activator
        activate_window = get_window_activator()
        activate_window(qt_widget)

    Returns:
        Callable die Qt-Widgets im Vordergrund aktivieren kann
    """
    if sys.platform == 'win32':
        from .windows import WindowsIO
        return WindowsIO.activate_qt_window
    else:
        # Fallback fuer andere Plattformen: Nur Qt-Methoden
        def qt_activate(widget):
            widget.activateWindow()
            widget.raise_()
            return True
        return qt_activate


__all__ = ['PlatformIO', 'get_platform_io', 'get_window_activator']
