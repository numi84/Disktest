"""Dialoge für DiskTest GUI."""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox, QMessageBox, QWidget, QScrollArea, QCheckBox,
    QProgressBar, QComboBox, QFileDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon

from .styles import AppStyles, is_dark_mode


class DriveSelectionDialog(QDialog):
    """
    Dialog zur Auswahl eines Laufwerks beim Programmstart.

    Zeigt verfügbare Laufwerke und erlaubt Auswahl oder manuelles Durchsuchen.
    """

    RESULT_SELECTED = 1
    RESULT_CANCEL = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_path = None
        self._setup_ui()
        self._populate_drives()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("Laufwerk auswählen")
        self.setModal(True)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Info-Text
        info_text = QLabel(
            "Wählen Sie ein Laufwerk für den Test aus.\n"
            "Das Programm sucht automatisch nach vorhandenen Testdateien."
        )
        info_text.setWordWrap(True)
        layout.addWidget(info_text)

        # Laufwerks-Auswahl
        drive_layout = QHBoxLayout()
        drive_layout.addWidget(QLabel("Laufwerk:"))

        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumWidth(200)
        drive_layout.addWidget(self.drive_combo, 1)

        self.browse_button = QPushButton("Durchsuchen...")
        self.browse_button.clicked.connect(self._browse_path)
        drive_layout.addWidget(self.browse_button)

        layout.addLayout(drive_layout)

        # Freier Speicher Anzeige
        self.free_space_label = QLabel("Freier Speicher: --")
        # Farbe passt sich automatisch an Dark/Light Mode an
        self.free_space_label.setStyleSheet("font-style: italic; opacity: 0.7;")
        layout.addWidget(self.free_space_label)

        # Verbinde Combo-Box Signal
        self.drive_combo.currentTextChanged.connect(self._update_free_space)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.setDefault(True)
        self.ok_button.setMinimumWidth(100)
        self.ok_button.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.clicked.connect(lambda: self.done(self.RESULT_CANCEL))
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _populate_drives(self):
        """Füllt die ComboBox mit verfügbaren Laufwerken."""
        # Windows: Prüfe Laufwerke A-Z
        available_drives = []
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                try:
                    # Prüfe ob Laufwerk zugreifbar ist
                    os.listdir(drive_path)
                    available_drives.append(drive_path)
                except (PermissionError, OSError):
                    # Laufwerk nicht zugreifbar (z.B. leeres CD-Laufwerk)
                    pass

        self.drive_combo.addItems(available_drives)

        # Wenn Laufwerke gefunden wurden, zeige Speicherinfo für erstes
        if available_drives:
            self._update_free_space(available_drives[0])

    def _update_free_space(self, path: str):
        """Aktualisiert die Anzeige des freien Speichers."""
        if not path or not os.path.exists(path):
            self.free_space_label.setText("Freier Speicher: --")
            return

        try:
            import shutil
            stat = shutil.disk_usage(path)
            free_gb = stat.free / (1024 ** 3)
            total_gb = stat.total / (1024 ** 3)
            self.free_space_label.setText(
                f"Freier Speicher: {free_gb:.1f} GB von {total_gb:.1f} GB"
            )
        except Exception:
            self.free_space_label.setText("Freier Speicher: Fehler beim Abrufen")

    def _browse_path(self):
        """Öffnet Datei-Dialog zur manuellen Ordnerauswahl."""
        current_path = self.drive_combo.currentText()

        directory = QFileDialog.getExistingDirectory(
            self,
            "Zielpfad auswählen",
            current_path or "",
            QFileDialog.Option.ShowDirsOnly
        )

        if directory:
            # Setze benutzerdefinierten Pfad
            # Prüfe ob Pfad bereits in ComboBox ist
            index = self.drive_combo.findText(directory)
            if index >= 0:
                self.drive_combo.setCurrentIndex(index)
            else:
                # Füge benutzerdefinierten Pfad hinzu
                self.drive_combo.addItem(directory)
                self.drive_combo.setCurrentIndex(self.drive_combo.count() - 1)

    def _on_ok_clicked(self):
        """OK-Button wurde geklickt."""
        self.selected_path = self.drive_combo.currentText()

        if not self.selected_path or not os.path.exists(self.selected_path):
            QMessageBox.warning(
                self,
                "Ungültiger Pfad",
                "Bitte wählen Sie einen gültigen Pfad aus."
            )
            return

        self.done(self.RESULT_SELECTED)

    def get_selected_path(self) -> str:
        """Gibt den ausgewählten Pfad zurück."""
        return self.selected_path


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
        # Farbe passt sich an Dark/Light Mode an
        icon_color = "#1565c0" if is_dark_mode() else "#0078d4"
        icon_label.setStyleSheet(f"font-size: 32px; color: {icon_color};")
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
        widget.setStyleSheet(AppStyles.get_dialog_detail_style())

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
        warning_color = "#ffa726" if is_dark_mode() else "#ffc107"
        warning_icon.setStyleSheet(f"font-size: 32px; color: {warning_color};")
        warning_layout.addWidget(warning_icon)

        warning_text = QLabel("Möchten Sie alle Testdateien löschen?")
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("font-weight: bold;")
        warning_layout.addWidget(warning_text, 1)

        layout.addLayout(warning_layout)

        # Details
        details_widget = QWidget()
        details_widget.setStyleSheet(AppStyles.get_dialog_detail_style())

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
        delete_color = "#ef5350" if is_dark_mode() else "#d32f2f"
        delete_button.setStyleSheet(f"color: {delete_color}; font-weight: bold;")

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
        warning_color = "#ffa726" if is_dark_mode() else "#ffc107"
        warning_icon.setStyleSheet(f"font-size: 32px; color: {warning_color};")
        warning_layout.addWidget(warning_icon)

        warning_text = QLabel("Möchten Sie den Test wirklich abbrechen?")
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("font-weight: bold;")
        warning_layout.addWidget(warning_text, 1)

        layout.addLayout(warning_layout)

        # Info
        info_widget = QWidget()
        info_widget.setStyleSheet(AppStyles.get_dialog_detail_style())

        info_layout = QVBoxLayout(info_widget)

        info1 = QLabel("Der aktuelle Fortschritt geht verloren.")
        info_layout.addWidget(info1)

        info2 = QLabel("Die erstellten Testdateien bleiben erhalten.")
        info_layout.addWidget(info2)

        layout.addWidget(info_widget)

        # Buttons
        button_box = QDialogButtonBox()

        abort_button = button_box.addButton("Test beenden", QDialogButtonBox.ButtonRole.AcceptRole)
        abort_color = "#ef5350" if is_dark_mode() else "#d32f2f"
        abort_button.setStyleSheet(f"color: {abort_color}; font-weight: bold;")

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
        border_color = "#555555" if is_dark_mode() else "#cccccc"
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {border_color};
                border-radius: 5px;
            }}
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
        widget.setStyleSheet(AppStyles.get_error_style())

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


class FileRecoveryDialog(QDialog):
    """
    Dialog zur Wiederherstellung von Testdateien ohne Session.

    Zeigt erkannte Testdateien und bietet Optionen:
    - Weiter testen (vorhandene Dateien verwenden)
    - Neuer Test (alles überschreiben)
    - Abbrechen
    """

    RESULT_CONTINUE = 1
    RESULT_NEW_TEST = 2
    RESULT_CANCEL = 0

    def __init__(self, recovery_info: dict, parent=None):
        """
        Args:
            recovery_info: Dictionary mit Recovery-Informationen
                - file_count: Anzahl gefundener Dateien
                - complete_count: Anzahl vollständiger Dateien
                - smaller_consistent_count: Anzahl zu kleiner konsistenter Dateien
                - corrupted_count: Anzahl beschädigter/unfertiger Dateien
                - expected_size_mb: Erwartete Dateigröße in MB
                - detected_pattern: Erkanntes Muster (oder None)
                - total_size_gb: Gesamtgröße in GB
                - last_complete_file: Index der letzten vollständigen Datei
        """
        super().__init__(parent)
        self.recovery_info = recovery_info
        self.overwrite_corrupted = True  # Default: Beschädigte überschreiben
        self.expand_smaller_files = True  # Default: Zu kleine Dateien vergrößern
        self._setup_ui()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("Testdateien gefunden")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Info-Icon und Text
        header_layout = QHBoxLayout()

        icon_label = QLabel("⚠")
        warning_color = "#ffa726" if is_dark_mode() else "#ffc107"
        icon_label.setStyleSheet(f"font-size: 32px; color: {warning_color};")
        header_layout.addWidget(icon_label)

        info_text = QLabel(
            "Es wurden Testdateien gefunden, aber keine passende Session.\n"
            "Die Dateien könnten von einem unterbrochenen Test stammen."
        )
        info_text.setWordWrap(True)
        header_layout.addWidget(info_text, 1)

        layout.addLayout(header_layout)

        # Datei-Details
        details_widget = self._create_details_widget()
        layout.addWidget(details_widget)

        # Option: Beschädigte Dateien überschreiben
        corrupted_count = self.recovery_info.get('corrupted_count', 0)
        if corrupted_count > 0:
            self.overwrite_checkbox = QCheckBox(
                f"Beschädigte Dateien überschreiben ({corrupted_count} Dateien)"
            )
            self.overwrite_checkbox.setChecked(True)
            self.overwrite_checkbox.setToolTip(
                "Beschädigte Dateien haben kein erkennbares Muster, sind leer oder zu groß.\n"
                "Diese Dateien müssen überschrieben werden."
            )
            self.overwrite_checkbox.stateChanged.connect(self._on_overwrite_changed)
            layout.addWidget(self.overwrite_checkbox)

        # Option: Zu kleine Dateien vergrößern
        smaller_count = self.recovery_info.get('smaller_consistent_count', 0)
        expected_size_mb = self.recovery_info.get('expected_size_mb', 0)
        if smaller_count > 0:
            self.expand_checkbox = QCheckBox(
                f"Zu kleine Dateien auf {expected_size_mb} MB vergrößern ({smaller_count} Dateien)"
            )
            self.expand_checkbox.setChecked(True)
            self.expand_checkbox.setToolTip(
                "Vergrößert Dateien durch Wiederholen des vorhandenen Musters.\n"
                "Nützlich wenn alte Tests mit kleinerer Dateigröße durchgeführt wurden."
            )
            self.expand_checkbox.stateChanged.connect(self._on_expand_changed)
            layout.addWidget(self.expand_checkbox)

        # Frage
        question = QLabel("Wie möchten Sie fortfahren?")
        question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(question)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.continue_button = QPushButton("Test fortsetzen")
        self.continue_button.setToolTip(
            "Nutzt vorhandene vollständige Dateien und setzt den Test fort"
        )
        self.continue_button.setMinimumWidth(120)
        self.continue_button.clicked.connect(lambda: self.done(self.RESULT_CONTINUE))
        button_layout.addWidget(self.continue_button)

        self.new_test_button = QPushButton("Neuer Test")
        self.new_test_button.setToolTip("Überschreibt alle vorhandenen Dateien")
        self.new_test_button.setDefault(True)
        self.new_test_button.setMinimumWidth(120)
        self.new_test_button.clicked.connect(lambda: self.done(self.RESULT_NEW_TEST))
        button_layout.addWidget(self.new_test_button)

        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.setMinimumWidth(120)
        self.cancel_button.clicked.connect(lambda: self.done(self.RESULT_CANCEL))
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _create_details_widget(self) -> QWidget:
        """Erstellt das Widget mit Datei-Details."""
        widget = QWidget()
        widget.setStyleSheet(AppStyles.get_dialog_detail_style())

        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        # Anzahl Dateien
        file_count = self.recovery_info.get('file_count', 0)
        count_layout = self._create_detail_row(
            "Gefundene Dateien:",
            str(file_count)
        )
        layout.addLayout(count_layout)

        # Vollständige Dateien
        complete = self.recovery_info.get('complete_count', 0)
        complete_layout = self._create_detail_row(
            "Vollständig:",
            f"{complete} Dateien"
        )
        layout.addLayout(complete_layout)

        # Zu kleine konsistente Dateien
        smaller_consistent = self.recovery_info.get('smaller_consistent_count', 0)
        if smaller_consistent > 0:
            smaller_layout = self._create_detail_row(
                "Zu klein (konsistent):",
                f"{smaller_consistent} Dateien"
            )
            layout.addLayout(smaller_layout)

        # Beschädigte Dateien
        corrupted = self.recovery_info.get('corrupted_count', 0)
        if corrupted > 0:
            corrupted_layout = self._create_detail_row(
                "Beschädigt/Unfertig:",
                f"{corrupted} Dateien"
            )
            layout.addLayout(corrupted_layout)

        # Gesamtgröße
        size_gb = self.recovery_info.get('total_size_gb', 0)
        size_layout = self._create_detail_row(
            "Gesamtgröße:",
            f"{size_gb:.1f} GB"
        )
        layout.addLayout(size_layout)

        # Erkanntes Muster
        pattern = self.recovery_info.get('detected_pattern')
        if pattern:
            pattern_layout = self._create_detail_row(
                "Erkanntes Muster:",
                pattern
            )
            layout.addLayout(pattern_layout)

        return widget

    def _create_detail_row(self, label_text: str, value_text: str) -> QHBoxLayout:
        """Hilfsfunktion zum Erstellen einer Detail-Zeile."""
        row_layout = QHBoxLayout()

        label = QLabel(label_text)
        label.setMinimumWidth(140)
        label.setStyleSheet("font-weight: bold;")
        row_layout.addWidget(label)

        value = QLabel(value_text)
        row_layout.addWidget(value, 1)

        return row_layout

    def _on_overwrite_changed(self, state):
        """Callback wenn Checkbox geändert wird."""
        self.overwrite_corrupted = (state == Qt.CheckState.Checked.value)

    def _on_expand_changed(self, state):
        """Callback wenn Expand-Checkbox geändert wird."""
        self.expand_smaller_files = (state == Qt.CheckState.Checked.value)

    def should_overwrite_corrupted(self) -> bool:
        """Gibt zurück ob beschädigte Dateien überschrieben werden sollen."""
        return self.overwrite_corrupted

    def should_expand_smaller_files(self) -> bool:
        """Gibt zurück ob zu kleine Dateien vergrößert werden sollen."""
        return self.expand_smaller_files


class FileExpansionWorker(QThread):
    """
    Worker-Thread zum Vergrößern von Dateien.
    """
    progress = Signal(int, int, str)  # (current_file_index, total_files, filename)
    file_progress = Signal(int, int)  # (current_bytes, total_bytes)
    finished = Signal(int, int)  # (success_count, error_count)

    def __init__(self, file_analyzer, files_to_expand):
        super().__init__()
        self.file_analyzer = file_analyzer
        self.files_to_expand = files_to_expand

    def run(self):
        """Führt die Datei-Vergrößerung aus."""
        success_count = 0
        error_count = 0
        total_files = len(self.files_to_expand)

        for i, file_result in enumerate(self.files_to_expand):
            # Emit progress für diese Datei
            self.progress.emit(i + 1, total_files, file_result.filepath.name)

            # Pattern muss bekannt sein
            if not file_result.detected_pattern:
                error_count += 1
                continue

            # Vergrößern mit File-Progress-Callback
            def on_file_progress(current_bytes, total_bytes):
                self.file_progress.emit(current_bytes, total_bytes)

            if self.file_analyzer.expand_file_to_target_size(
                file_result.filepath,
                file_result.detected_pattern,
                progress_callback=on_file_progress
            ):
                success_count += 1
            else:
                error_count += 1

        # Fertig
        self.finished.emit(success_count, error_count)


class FileExpansionDialog(QDialog):
    """
    Dialog zur Anzeige des Fortschritts beim Vergrößern von Dateien.
    """

    def __init__(self, file_analyzer, files_to_expand, parent=None):
        """
        Args:
            file_analyzer: FileAnalyzer Instanz
            files_to_expand: Liste von FileAnalysisResult
        """
        super().__init__(parent)
        self.file_analyzer = file_analyzer
        self.files_to_expand = files_to_expand
        self.success_count = 0
        self.error_count = 0
        self._setup_ui()
        self._start_expansion()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("Dateien werden vergrößert")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Info-Text
        info_text = QLabel("Testdateien werden auf Zielgröße vergrößert...")
        info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_text)

        # Datei-Label
        self.file_label = QLabel("Vorbereitung...")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.file_label)

        # Datei-Fortschrittsbalken
        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setMinimum(0)
        self.file_progress_bar.setMaximum(100)
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setTextVisible(True)
        self.file_progress_bar.setFormat("Datei: %p%")
        layout.addWidget(self.file_progress_bar)

        # Gesamt-Fortschrittsbalken
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setMinimum(0)
        self.overall_progress_bar.setMaximum(len(self.files_to_expand))
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setTextVisible(True)
        self.overall_progress_bar.setFormat("Dateien: %v / %m")
        layout.addWidget(self.overall_progress_bar)

        # Close-Button (initial disabled)
        self.close_button = QPushButton("Schließen")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)

    def _start_expansion(self):
        """Startet den Expansion-Worker."""
        self.worker = FileExpansionWorker(self.file_analyzer, self.files_to_expand)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_progress.connect(self._on_file_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, current_file: int, total_files: int, filename: str):
        """Callback für Gesamt-Fortschritt."""
        self.file_label.setText(f"Datei: {filename}")
        self.overall_progress_bar.setValue(current_file)
        # Reset File-Progress für nächste Datei
        self.file_progress_bar.setValue(0)

    def _on_file_progress(self, current_bytes: int, total_bytes: int):
        """Callback für Datei-Fortschritt."""
        if total_bytes > 0:
            progress_percent = int((current_bytes / total_bytes) * 100)
            self.file_progress_bar.setValue(progress_percent)

    def _on_finished(self, success_count: int, error_count: int):
        """Callback wenn Expansion fertig ist."""
        self.success_count = success_count
        self.error_count = error_count

        # Update UI
        if error_count > 0:
            self.file_label.setText(
                f"Abgeschlossen: {success_count} erfolgreich, {error_count} Fehler"
            )
        else:
            self.file_label.setText(f"Abgeschlossen: {success_count} Dateien vergrößert")

        self.file_progress_bar.setValue(100)
        self.overall_progress_bar.setValue(len(self.files_to_expand))
        self.close_button.setEnabled(True)

    def get_results(self):
        """Gibt die Ergebnisse zurück."""
        return (self.success_count, self.error_count)
