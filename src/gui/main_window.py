"""Hauptfenster der DiskTest Anwendung."""

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLineEdit, QLabel, QSlider, QSpinBox, QDoubleSpinBox,
    QCheckBox, QFileDialog, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon, QAction

from .widgets import ProgressWidget, LogWidget, PatternSelectionWidget


class ConfigurationWidget(QGroupBox):
    """
    Widget für Test-Konfiguration.

    Enthält:
    - Zielpfad-Auswahl
    - Testgröße (Slider + SpinBox + Checkbox)
    - Dateigröße
    - Freier Speicher Anzeige
    """

    # Signals
    path_changed = Signal(str)  # Emittiert wenn Pfad geändert wird
    config_changed = Signal()   # Emittiert bei jeder Config-Änderung

    def __init__(self, parent=None):
        super().__init__("Konfiguration", parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """UI-Elemente erstellen."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Zielpfad
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Zielpfad:"))

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("z.B. D:\\")
        path_layout.addWidget(self.path_edit, 1)

        self.browse_button = QPushButton("Browse")
        self.browse_button.setMaximumWidth(100)
        path_layout.addWidget(self.browse_button)

        layout.addLayout(path_layout)

        # Testgröße
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Testgröße:"))

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setMinimum(1)
        self.size_slider.setMaximum(100)  # Wird dynamisch angepasst
        self.size_slider.setValue(50)
        size_layout.addWidget(self.size_slider, 1)

        self.size_spinbox = QDoubleSpinBox()
        self.size_spinbox.setMinimum(0.1)  # 100 MB minimum
        self.size_spinbox.setMaximum(10000)  # Wird dynamisch angepasst
        self.size_spinbox.setValue(50)
        self.size_spinbox.setSuffix(" GB")
        self.size_spinbox.setDecimals(1)
        self.size_spinbox.setSingleStep(0.1)
        self.size_spinbox.setMinimumWidth(100)
        size_layout.addWidget(self.size_spinbox)

        self.whole_drive_checkbox = QCheckBox("Ganzes Lfw.")
        size_layout.addWidget(self.whole_drive_checkbox)

        layout.addLayout(size_layout)

        # Dateigröße, Freier Speicher und Log-Option in einer Zeile
        file_size_layout = QHBoxLayout()
        file_size_layout.addWidget(QLabel("Dateigröße:"))

        self.file_size_spinbox = QSpinBox()
        self.file_size_spinbox.setMinimum(128)  # 128 MB minimum
        self.file_size_spinbox.setMaximum(10240)  # 10240 MB = 10 GB
        self.file_size_spinbox.setValue(1024)  # 1024 MB = 1 GB
        self.file_size_spinbox.setSingleStep(128)  # 128 MB Schritte für runde GB-Werte
        self.file_size_spinbox.setSuffix(" MB")
        self.file_size_spinbox.setMinimumWidth(100)
        file_size_layout.addWidget(self.file_size_spinbox)

        file_size_layout.addWidget(QLabel("GB"))

        file_size_layout.addSpacing(20)

        self.free_space_label = QLabel("Freier Speicher: --")
        file_size_layout.addWidget(self.free_space_label)

        file_size_layout.addSpacing(20)

        self.log_in_userdir_checkbox = QCheckBox("Logs im Benutzerordner speichern")
        self.log_in_userdir_checkbox.setToolTip(
            "Wenn aktiviert, werden Log-Dateien im Benutzerordner statt im Zielpfad gespeichert.\n"
            "Nützlich wenn das Ziellaufwerk wenig Platz hat oder Probleme aufweist."
        )
        file_size_layout.addWidget(self.log_in_userdir_checkbox)

        layout.addLayout(file_size_layout)

        # Pattern-Auswahl Widget
        self.pattern_widget = PatternSelectionWidget()
        layout.addWidget(self.pattern_widget)

    def _connect_signals(self):
        """Verbindet interne Signals."""
        self.browse_button.clicked.connect(self._browse_path)
        self.path_edit.textChanged.connect(self._on_path_changed)

        # Slider und SpinBox synchronisieren
        # Slider verwendet Ganzzahlen, SpinBox erlaubt Dezimalwerte
        self.size_slider.valueChanged.connect(self._on_slider_changed)
        self.size_spinbox.valueChanged.connect(self._on_spinbox_changed)

        # Checkbox für ganzes Laufwerk
        self.whole_drive_checkbox.toggled.connect(self._on_whole_drive_toggled)

        # Config-Changed Signal (Lambda um Parameter zu ignorieren)
        self.size_spinbox.valueChanged.connect(lambda: self.config_changed.emit())
        self.file_size_spinbox.valueChanged.connect(lambda: self.config_changed.emit())

        # Wenn Dateigröße geändert wird, Speicherplatz neu berechnen
        self.file_size_spinbox.valueChanged.connect(lambda: self._on_path_changed(self.path_edit.text()))

    def _on_slider_changed(self, value: int):
        """Slider-Wert geändert - synchronisiere mit SpinBox"""
        # Nur synchronisieren wenn Wert unterschiedlich (verhindert Endlosschleife)
        if abs(self.size_spinbox.value() - value) >= 0.5:
            self.size_spinbox.setValue(float(value))

    def _on_spinbox_changed(self, value: float):
        """SpinBox-Wert geändert - synchronisiere mit Slider"""
        # Slider kann nur Ganzzahlen, runde den Wert
        int_value = max(1, int(round(value)))  # Mindestens 1 für Slider
        if self.size_slider.value() != int_value:
            self.size_slider.setValue(int_value)

    def _browse_path(self):
        """Öffnet Datei-Dialog zur Ordnerauswahl."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Zielpfad auswählen",
            self.path_edit.text() or "",
            QFileDialog.Option.ShowDirsOnly
        )

        if directory:
            self.path_edit.setText(directory)

    def _on_path_changed(self, path: str):
        """Wird aufgerufen wenn Pfad geändert wird."""
        self._update_free_space(path)
        self.path_changed.emit(path)
        self.config_changed.emit()

    def _get_available_test_space(self, path: str) -> float:
        """
        Berechnet verfügbaren Speicher für Test inkl. vorhandener Testdateien.

        Returns:
            float: Verfügbarer Speicher in GB
        """
        if not path or not os.path.exists(path):
            return 0.0

        try:
            import shutil
            from core.file_manager import FileManager

            # OS-freier Speicher
            stat = shutil.disk_usage(path)
            free_gb = stat.free / (1024 ** 3)

            # Größe vorhandener Testdateien
            file_size_gb = self.file_size_spinbox.value() / 1024.0  # MB to GB
            fm = FileManager(path, file_size_gb)
            existing_size_gb = fm.get_existing_files_size() / (1024 ** 3)

            return free_gb + existing_size_gb
        except Exception:
            return 0.0

    def _update_free_space(self, path: str):
        """Aktualisiert die Anzeige des freien Speichers."""
        if not path or not os.path.exists(path):
            self.free_space_label.setText("Freier Speicher: --")
            return

        available_gb = self._get_available_test_space(path)

        if available_gb > 0:
            self.free_space_label.setText(f"Freier Speicher: {available_gb:.1f} GB")

            # Slider-Maximum anpassen (Ganzzahl)
            self.size_slider.setMaximum(max(1, int(available_gb)))
            # SpinBox-Maximum anpassen (Dezimalwert)
            self.size_spinbox.setMaximum(available_gb)
        else:
            self.free_space_label.setText("Freier Speicher: Fehler")

    def _on_whole_drive_toggled(self, checked: bool):
        """Wird aufgerufen wenn 'Ganzes Laufwerk' Checkbox geändert wird."""
        if checked:
            # Setze auf Maximum
            self.size_slider.setValue(self.size_slider.maximum())
            self.size_spinbox.setValue(self.size_spinbox.maximum())

            # Deaktiviere manuelle Eingabe
            self.size_slider.setEnabled(False)
            self.size_spinbox.setEnabled(False)
        else:
            # Aktiviere manuelle Eingabe
            self.size_slider.setEnabled(True)
            self.size_spinbox.setEnabled(True)

    def get_config(self) -> dict:
        """
        Gibt die aktuelle Konfiguration zurück.

        Returns:
            dict mit Schlüsseln:
                - target_path (str): Zielpfad
                - test_size_gb (float): Testgröße in GB
                - file_size_mb (int): Dateigröße in MB
                - whole_drive (bool): Ganzes Laufwerk nutzen
                - log_in_userdir (bool): Logs im Benutzerordner speichern
        """
        return {
            'target_path': self.path_edit.text(),
            'test_size_gb': self.size_spinbox.value(),
            'file_size_mb': self.file_size_spinbox.value(),
            'whole_drive': self.whole_drive_checkbox.isChecked(),
            'selected_patterns': self.pattern_widget.get_selected_patterns(),
            'log_in_userdir': self.log_in_userdir_checkbox.isChecked()
        }

    def set_config(self, config: dict):
        """Setzt die Konfiguration."""
        if 'target_path' in config:
            self.path_edit.setText(config['target_path'])

        if 'test_size_gb' in config:
            self.size_spinbox.setValue(config['test_size_gb'])

        if 'file_size_mb' in config:
            self.file_size_spinbox.setValue(config['file_size_mb'])

        if 'whole_drive' in config:
            self.whole_drive_checkbox.setChecked(config['whole_drive'])

        if 'log_in_userdir' in config:
            self.log_in_userdir_checkbox.setChecked(config['log_in_userdir'])

    def set_enabled(self, enabled: bool):
        """Aktiviert/Deaktiviert alle Eingabeelemente."""
        self.path_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.file_size_spinbox.setEnabled(enabled)

        if not self.whole_drive_checkbox.isChecked():
            self.size_slider.setEnabled(enabled)
            self.size_spinbox.setEnabled(enabled)

        self.whole_drive_checkbox.setEnabled(enabled)

    def set_enabled_for_resume(self):
        """
        Aktiviert nur bestimmte Felder beim Fortsetzen einer Session.

        Beim Fortsetzen können geändert werden:
        - Testgröße (wie viel vom Laufwerk getestet werden soll)

        NICHT änderbar:
        - Zielpfad (fest durch Session)
        - Dateigröße (fest durch Session)
        """
        # Zielpfad und Dateigröße deaktiviert (fest durch Session)
        self.path_edit.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.file_size_spinbox.setEnabled(False)

        # Testgröße kann geändert werden
        if not self.whole_drive_checkbox.isChecked():
            self.size_slider.setEnabled(True)
            self.size_spinbox.setEnabled(True)

        self.whole_drive_checkbox.setEnabled(True)


class ControlWidget(QGroupBox):
    """
    Widget für Test-Steuerung.

    Enthält:
    - Start Button
    - Pause Button
    - Stop Button
    - Dateien löschen Button
    """

    # Signals
    start_clicked = Signal()
    pause_clicked = Signal()
    stop_after_file_clicked = Signal()
    stop_clicked = Signal()
    delete_files_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("Steuerung", parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """UI-Elemente erstellen."""
        layout = QHBoxLayout(self)

        self.start_button = QPushButton("▶ Start")
        self.start_button.setMinimumHeight(40)
        layout.addWidget(self.start_button)

        self.pause_button = QPushButton("⏸ Pause")
        self.pause_button.setMinimumHeight(40)
        self.pause_button.setEnabled(False)
        layout.addWidget(self.pause_button)

        self.stop_after_file_button = QPushButton("⏸ Pause nach Datei")
        self.stop_after_file_button.setMinimumHeight(40)
        self.stop_after_file_button.setEnabled(False)
        layout.addWidget(self.stop_after_file_button)

        self.stop_button = QPushButton("⏹ Test Abbrechen")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        layout.addStretch()

        self.delete_button = QPushButton("🗑 Dateien löschen")
        self.delete_button.setMinimumHeight(40)
        self.delete_button.setEnabled(False)
        layout.addWidget(self.delete_button)

    def _connect_signals(self):
        """Verbindet Button-Signals."""
        self.start_button.clicked.connect(self.start_clicked.emit)
        self.pause_button.clicked.connect(self.pause_clicked.emit)
        self.stop_after_file_button.clicked.connect(self.stop_after_file_clicked.emit)
        self.stop_button.clicked.connect(self.stop_clicked.emit)
        self.delete_button.clicked.connect(self.delete_files_clicked.emit)

    def set_state_idle(self):
        """Setzt Buttons für 'Bereit' Zustand."""
        self.start_button.setEnabled(True)
        self.start_button.setText("▶ Start")
        self.pause_button.setEnabled(False)
        self.stop_after_file_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    def set_state_running(self):
        """Setzt Buttons für 'Test läuft' Zustand."""
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("⏸ Pause")
        self.stop_after_file_button.setEnabled(True)
        self.stop_button.setEnabled(True)

    def set_state_paused(self):
        """Setzt Buttons für 'Pausiert' Zustand."""
        self.start_button.setEnabled(True)
        self.start_button.setText("▶ Fortsetzen")
        self.pause_button.setEnabled(False)
        self.stop_after_file_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def enable_delete_button(self, enabled: bool):
        """Aktiviert/Deaktiviert den Dateien-löschen Button."""
        self.delete_button.setEnabled(enabled)


class MainWindow(QMainWindow):
    """Hauptfenster der DiskTest Anwendung."""

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._initialize_state()

        # Controller wird nach UI-Setup erstellt
        # Import hier um zirkuläre Imports zu vermeiden
        from .test_controller import TestController
        self.controller = TestController(self)

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.setWindowTitle("DiskTest")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        # Zentrales Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Hauptlayout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)

        # Konfiguration
        self.config_widget = ConfigurationWidget()
        main_layout.addWidget(self.config_widget)

        # Steuerung
        self.control_widget = ControlWidget()
        main_layout.addWidget(self.control_widget)

        # Fortschritt
        self.progress_widget = ProgressWidget()
        main_layout.addWidget(self.progress_widget)

        # Log
        self.log_widget = LogWidget()
        main_layout.addWidget(self.log_widget, 1)  # Nimmt verfügbaren Platz

        # Statusleiste
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit")

        # Session Info in Statusleiste (rechts)
        self.session_label = QLabel("")
        self.status_bar.addPermanentWidget(self.session_label)

        # Menüleiste
        self._create_menu()

    def _create_menu(self):
        """Erstellt die Menüleiste."""
        menubar = self.menuBar()

        # Datei-Menü
        file_menu = menubar.addMenu("&Datei")

        exit_action = QAction("B&eenden", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Bearbeiten-Menü
        edit_menu = menubar.addMenu("&Bearbeiten")

        clear_log_action = QAction("Log &leeren", self)
        clear_log_action.setShortcut("Ctrl+L")
        clear_log_action.triggered.connect(self.log_widget.clear)
        edit_menu.addAction(clear_log_action)

        # Hilfe-Menü
        help_menu = menubar.addMenu("&Hilfe")

        about_action = QAction("Ü&ber DiskTest", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _initialize_state(self):
        """Initialisiert den UI-Zustand."""
        self.control_widget.set_state_idle()

    def _show_about(self):
        """Zeigt About-Dialog."""
        QMessageBox.about(
            self,
            "Über DiskTest",
            "<h3>DiskTest</h3>"
            "<p>Version 1.0</p>"
            "<p>Nicht-destruktive Festplattentest-Anwendung</p>"
            "<p>Inspiriert von Linux badblocks</p>"
        )

    def set_session_info(self, session_path: str):
        """Zeigt Session-Info in Statusleiste."""
        if session_path:
            filename = Path(session_path).name
            self.session_label.setText(f"Session: {filename}")
        else:
            self.session_label.setText("")

    def closeEvent(self, event):
        """Wird beim Schließen des Fensters aufgerufen."""
        # Prüfen ob Test läuft
        if hasattr(self, 'controller') and self.controller.current_state.name == 'RUNNING':
            reply = QMessageBox.question(
                self,
                "Test läuft",
                "Ein Test läuft gerade. Möchten Sie wirklich beenden?\n\n"
                "Der Fortschritt wird gespeichert und kann später fortgesetzt werden.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            # Test pausieren vor dem Beenden
            if self.controller.engine:
                self.controller.engine.pause()
                self.controller.engine.wait()

        event.accept()
