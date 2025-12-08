"""
Testskript für GUI-Komponenten

Demonstriert die verschiedenen Widgets und Dialoge.
"""

import sys
from pathlib import Path

# Füge src zum Python-Path hinzu
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Qt

from gui import (
    MainWindow,
    SessionRestoreDialog,
    DeleteFilesDialog,
    StopConfirmationDialog,
    ErrorDetailDialog
)


class TestWindow(QWidget):
    """Test-Fenster mit Buttons zum Öffnen der verschiedenen Dialoge."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DiskTest GUI Test")
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # Button für Session-Wiederherstellung Dialog
        session_btn = QPushButton("Session-Wiederherstellung Dialog")
        session_btn.clicked.connect(self.show_session_dialog)
        layout.addWidget(session_btn)

        # Button für Dateien löschen Dialog
        delete_btn = QPushButton("Dateien löschen Dialog")
        delete_btn.clicked.connect(self.show_delete_dialog)
        layout.addWidget(delete_btn)

        # Button für Stop-Bestätigung Dialog
        stop_btn = QPushButton("Stop-Bestätigung Dialog")
        stop_btn.clicked.connect(self.show_stop_dialog)
        layout.addWidget(stop_btn)

        # Button für Fehler-Detail Dialog
        error_btn = QPushButton("Fehler-Detail Dialog")
        error_btn.clicked.connect(self.show_error_dialog)
        layout.addWidget(error_btn)

        layout.addStretch()

        # Button für Hauptfenster
        main_btn = QPushButton("Hauptfenster öffnen")
        main_btn.clicked.connect(self.show_main_window)
        main_btn.setStyleSheet("font-weight: bold; background-color: #0078d4; color: white; padding: 10px;")
        layout.addWidget(main_btn)

    def show_session_dialog(self):
        """Zeigt den Session-Wiederherstellung Dialog."""
        session_info = {
            'target_path': 'D:\\',
            'progress': 42,
            'pattern_index': 1,
            'pattern_name': '0xFF',
            'error_count': 0
        }

        dialog = SessionRestoreDialog(session_info, self)
        result = dialog.exec()

        if result == SessionRestoreDialog.RESULT_RESUME:
            print("User wählte: Fortsetzen")
        elif result == SessionRestoreDialog.RESULT_NEW_TEST:
            print("User wählte: Neuer Test")
        else:
            print("User wählte: Abbrechen")

    def show_delete_dialog(self):
        """Zeigt den Dateien löschen Dialog."""
        dialog = DeleteFilesDialog("D:\\", 50, 50.0, self)
        result = dialog.exec()

        if result == DeleteFilesDialog.DialogCode.Accepted:
            print("User bestätigte Löschung")
        else:
            print("User brach ab")

    def show_stop_dialog(self):
        """Zeigt den Stop-Bestätigung Dialog."""
        dialog = StopConfirmationDialog(self)
        result = dialog.exec()

        if result == StopConfirmationDialog.DialogCode.Accepted:
            print("User bestätigte Abbruch")
        else:
            print("User brach ab")

    def show_error_dialog(self):
        """Zeigt den Fehler-Detail Dialog."""
        errors = [
            {
                'filename': 'disktest_023.dat',
                'pattern': '0xFF',
                'phase': 'Verifizierung',
                'details': 'Daten stimmen nicht überein (Chunk 156)'
            },
            {
                'filename': 'disktest_041.dat',
                'pattern': '0xAA',
                'phase': 'Schreiben',
                'details': 'Schreibfehler - Zugriff verweigert'
            },
            {
                'filename': 'disktest_048.dat',
                'pattern': '0x55',
                'phase': 'Verifizierung',
                'details': 'Lesefehlter - CRC-Fehler'
            }
        ]

        dialog = ErrorDetailDialog(errors, self)
        dialog.exec()

    def show_main_window(self):
        """Zeigt das Hauptfenster."""
        self.main_window = MainWindow()
        self.main_window.show()

        # Beispiel-Werte setzen
        self.main_window.config_widget.path_edit.setText("D:\\")
        self.main_window.progress_widget.set_progress(42)
        self.main_window.progress_widget.set_time_remaining("2h 15m")
        self.main_window.progress_widget.set_pattern("2/5 (0xFF)")
        self.main_window.progress_widget.set_phase("Verifizieren")
        self.main_window.progress_widget.set_file("23/50 (disktest_023.dat)")
        self.main_window.progress_widget.set_speed("185.3 MB/s")
        self.main_window.progress_widget.set_error_count(0)

        # Beispiel-Logs hinzufügen
        self.main_window.log_widget.add_log("14:30:22", "INFO", "Test gestartet - Ziel: D:\\")
        self.main_window.log_widget.add_log("14:30:22", "INFO", "Konfiguration: 50 Dateien à 1 GB")
        self.main_window.log_widget.add_log("14:35:44", "SUCCESS", "disktest_001.dat - 0x00 - Schreiben OK")
        self.main_window.log_widget.add_log("14:40:12", "SUCCESS", "disktest_001.dat - 0x00 - Verifizierung OK")
        self.main_window.log_widget.add_log("14:45:33", "SUCCESS", "disktest_002.dat - 0x00 - Schreiben OK")
        self.main_window.log_widget.add_log("14:50:55", "WARNING", "Geschwindigkeit unter Durchschnitt")
        self.main_window.log_widget.add_log("14:55:12", "ERROR", "disktest_023.dat - Verifizierung FEHLGESCHLAGEN")


def main():
    """Hauptfunktion"""
    app = QApplication(sys.argv)

    app.setApplicationName("DiskTest GUI Test")
    app.setApplicationVersion("1.0.0")

    window = TestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
