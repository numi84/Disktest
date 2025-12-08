"""
DiskTest - Windows Desktop-Anwendung für nicht-destruktive Festplattentests
Einstiegspunkt der Anwendung
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from gui import MainWindow


def main():
    """Hauptfunktion"""
    # High-DPI Support ist in Qt6 standardmäßig aktiviert
    app = QApplication(sys.argv)

    # Anwendungsinfos
    app.setApplicationName("DiskTest")
    app.setOrganizationName("DiskTest")
    app.setApplicationVersion("1.0.0")

    # Hauptfenster erstellen und anzeigen
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
