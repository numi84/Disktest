"""Dialoge für DiskTest GUI."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox, QMessageBox, QWidget, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon


class SessionRestoreDialog(QDialog):
    """
    Dialog zur Wiederherstellung einer vorherigen Session.

    Zeigt Informationen zur gefundenen Session und bietet Optionen:
    - Fortsetzen
    - Neuer Test
    - Abbrechen
    """

    RESULT_RESUME = 1
    RESULT_NEW_TEST = 2
    RESULT_CANCEL = 0

    def __init__(self, session_info: dict, parent=None):
        """
        Args:
            session_info: Dictionary mit Session-Informationen
                - target_path: Zielpfad
                - progress: Fortschritt in Prozent
                - pattern_index: Aktuelles Muster (0-4)
                - pattern_name: Name des Musters (z.B. '0xFF')
                - error_count: Anzahl Fehler
        """
        super().__init__(parent)
        self.session_info = session_info
        self._setup_ui()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("Vorherige Session gefunden")
        self.setModal(True)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Info-Icon und Text
        header_layout = QHBoxLayout()

        icon_label = QLabel("ℹ")
        icon_label.setStyleSheet("font-size: 32px; color: #0078d4;")
        header_layout.addWidget(icon_label)

        info_text = QLabel("Eine vorherige Test-Session wurde gefunden.")
        info_text.setWordWrap(True)
        header_layout.addWidget(info_text, 1)

        layout.addLayout(header_layout)

        # Session-Details
        details_widget = self._create_details_widget()
        layout.addWidget(details_widget)

        # Frage
        question = QLabel("Möchten Sie den Test fortsetzen?")
        question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(question)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.resume_button = QPushButton("Fortsetzen")
        self.resume_button.setDefault(True)
        self.resume_button.setMinimumWidth(100)
        self.resume_button.clicked.connect(lambda: self.done(self.RESULT_RESUME))
        button_layout.addWidget(self.resume_button)

        self.new_test_button = QPushButton("Neuer Test")
        self.new_test_button.setMinimumWidth(100)
        self.new_test_button.clicked.connect(lambda: self.done(self.RESULT_NEW_TEST))
        button_layout.addWidget(self.new_test_button)

        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.clicked.connect(lambda: self.done(self.RESULT_CANCEL))
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _create_details_widget(self) -> QWidget:
        """Erstellt das Widget mit Session-Details."""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-radius: 5px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # Zielpfad
        path_layout = self._create_detail_row(
            "Zielpfad:",
            self.session_info.get('target_path', '--')
        )
        layout.addLayout(path_layout)

        # Fortschritt
        progress = self.session_info.get('progress', 0)
        progress_layout = self._create_detail_row(
            "Fortschritt:",
            f"{progress}%"
        )
        layout.addLayout(progress_layout)

        # Muster
        pattern_idx = self.session_info.get('pattern_index', 0)
        pattern_name = self.session_info.get('pattern_name', '--')
        muster_layout = self._create_detail_row(
            "Muster:",
            f"{pattern_idx + 1}/5 ({pattern_name})"
        )
        layout.addLayout(muster_layout)

        # Fehler
        errors = self.session_info.get('error_count', 0)
        error_layout = self._create_detail_row(
            "Fehler:",
            str(errors)
        )
        layout.addLayout(error_layout)

        return widget

    def _create_detail_row(self, label_text: str, value_text: str) -> QHBoxLayout:
        """Hilfsfunktion zum Erstellen einer Detail-Zeile."""
        row_layout = QHBoxLayout()

        label = QLabel(label_text)
        label.setMinimumWidth(100)
        label.setStyleSheet("font-weight: bold;")
        row_layout.addWidget(label)

        value = QLabel(value_text)
        row_layout.addWidget(value, 1)

        return row_layout


class DeleteFilesDialog(QDialog):
    """
    Dialog zur Bestätigung der Testdatei-Löschung.

    Zeigt Informationen über zu löschende Dateien und fordert Bestätigung.
    """

    def __init__(self, target_path: str, file_count: int, total_size_gb: float, parent=None):
        """
        Args:
            target_path: Pfad wo Dateien liegen
            file_count: Anzahl der Testdateien
            total_size_gb: Gesamtgröße in GB
        """
        super().__init__(parent)
        self.target_path = target_path
        self.file_count = file_count
        self.total_size_gb = total_size_gb
        self._setup_ui()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("Testdateien löschen")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Warnung
        warning_layout = QHBoxLayout()

        warning_icon = QLabel("⚠")
        warning_icon.setStyleSheet("font-size: 32px; color: #ffc107;")
        warning_layout.addWidget(warning_icon)

        warning_text = QLabel("Möchten Sie alle Testdateien löschen?")
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("font-weight: bold;")
        warning_layout.addWidget(warning_text, 1)

        layout.addLayout(warning_layout)

        # Details
        details_widget = QWidget()
        details_widget.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-radius: 5px;
                padding: 15px;
            }
        """)

        details_layout = QVBoxLayout(details_widget)
        details_layout.setSpacing(8)

        # Pfad
        path_layout = self._create_detail_row("Pfad:", self.target_path)
        details_layout.addLayout(path_layout)

        # Anzahl
        count_layout = self._create_detail_row("Anzahl:", f"{self.file_count} Dateien")
        details_layout.addLayout(count_layout)

        # Größe
        size_layout = self._create_detail_row("Größe:", f"{self.total_size_gb:.1f} GB")
        details_layout.addLayout(size_layout)

        layout.addWidget(details_widget)

        # Buttons
        button_box = QDialogButtonBox()

        delete_button = button_box.addButton("Löschen", QDialogButtonBox.ButtonRole.AcceptRole)
        delete_button.setStyleSheet("color: red; font-weight: bold;")

        cancel_button = button_box.addButton("Abbrechen", QDialogButtonBox.ButtonRole.RejectRole)
        cancel_button.setDefault(True)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def _create_detail_row(self, label_text: str, value_text: str) -> QHBoxLayout:
        """Hilfsfunktion zum Erstellen einer Detail-Zeile."""
        row_layout = QHBoxLayout()

        label = QLabel(label_text)
        label.setMinimumWidth(80)
        label.setStyleSheet("font-weight: bold;")
        row_layout.addWidget(label)

        value = QLabel(value_text)
        row_layout.addWidget(value, 1)

        return row_layout


class StopConfirmationDialog(QDialog):
    """
    Dialog zur Bestätigung des Test-Abbruchs.

    Warnt den User dass der Fortschritt verloren geht.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("Test abbrechen")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Warnung
        warning_layout = QHBoxLayout()

        warning_icon = QLabel("⚠")
        warning_icon.setStyleSheet("font-size: 32px; color: #ffc107;")
        warning_layout.addWidget(warning_icon)

        warning_text = QLabel("Möchten Sie den Test wirklich abbrechen?")
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("font-weight: bold;")
        warning_layout.addWidget(warning_text, 1)

        layout.addLayout(warning_layout)

        # Info
        info_widget = QWidget()
        info_widget.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-radius: 5px;
                padding: 15px;
            }
        """)

        info_layout = QVBoxLayout(info_widget)

        info1 = QLabel("Der aktuelle Fortschritt geht verloren.")
        info_layout.addWidget(info1)

        info2 = QLabel("Die erstellten Testdateien bleiben erhalten.")
        info_layout.addWidget(info2)

        layout.addWidget(info_widget)

        # Buttons
        button_box = QDialogButtonBox()

        abort_button = button_box.addButton("Test beenden", QDialogButtonBox.ButtonRole.AcceptRole)
        abort_button.setStyleSheet("color: red; font-weight: bold;")

        cancel_button = button_box.addButton("Abbrechen", QDialogButtonBox.ButtonRole.RejectRole)
        cancel_button.setDefault(True)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)


class ErrorDetailDialog(QDialog):
    """
    Dialog zur Anzeige von Fehler-Details.

    Zeigt eine Liste aller aufgetretenen Fehler.
    """

    def __init__(self, errors: list, parent=None):
        """
        Args:
            errors: Liste von Fehler-Dictionaries mit Schlüsseln:
                - filename: Dateiname
                - pattern: Muster (z.B. '0xFF')
                - phase: Phase ('Schreiben' oder 'Verifizierung')
                - details: Detaillierte Fehlerbeschreibung
        """
        super().__init__(parent)
        self.errors = errors
        self._setup_ui()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("Fehler-Details")
        self.setModal(True)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"Fehler während des Tests: {len(self.errors)}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # Scroll-Bereich für Fehler-Liste
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)

        error_list_widget = QWidget()
        error_list_layout = QVBoxLayout(error_list_widget)
        error_list_layout.setSpacing(15)

        # Fehler-Einträge erstellen
        for i, error in enumerate(self.errors, 1):
            error_widget = self._create_error_widget(i, error)
            error_list_layout.addWidget(error_widget)

        error_list_layout.addStretch()

        scroll.setWidget(error_list_widget)
        layout.addWidget(scroll)

        # Schließen-Button
        close_button = QPushButton("Schließen")
        close_button.setMinimumWidth(100)
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _create_error_widget(self, index: int, error: dict) -> QWidget:
        """Erstellt ein Widget für einen Fehler-Eintrag."""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #ffebee;
                border-left: 4px solid #dc3545;
                border-radius: 3px;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout(widget)
        layout.setSpacing(5)

        # Nummer und Dateiname
        header = QLabel(f"{index}. {error.get('filename', 'Unbekannte Datei')}")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        # Muster
        muster_label = QLabel(f"Muster: {error.get('pattern', '--')}")
        layout.addWidget(muster_label)

        # Phase
        phase_label = QLabel(f"Phase: {error.get('phase', '--')}")
        layout.addWidget(phase_label)

        # Details
        details_label = QLabel(f"Details: {error.get('details', 'Keine Details verfügbar')}")
        details_label.setWordWrap(True)
        layout.addWidget(details_label)

        return widget
