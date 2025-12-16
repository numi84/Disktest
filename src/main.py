"""
DiskTest - Windows Desktop-Anwendung für nicht-destruktive Festplattentests
Einstiegspunkt der Anwendung
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gui import MainWindow
from gui.styles import AppStyles


def main():
    """Hauptfunktion"""
    # High-DPI Support ist in Qt6 standardmäßig aktiviert
    app = QApplication(sys.argv)

    # Anwendungsinfos
    app.setApplicationName("DiskTest")
    app.setOrganizationName("DiskTest")
    app.setApplicationVersion("1.0.0")

    # Stylesheet anwenden (automatisch Light/Dark Mode)
    app.setStyleSheet(AppStyles.get_main_stylesheet())

    # Hauptfenster erstellen und anzeigen
    window = MainWindow()
    window.show()

    # Aktiviere Fenster im Vordergrund
    from core.platform import get_window_activator
    activate_window = get_window_activator()
    activate_window(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
