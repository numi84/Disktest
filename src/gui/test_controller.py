"""
Test-Controller - Verbindet GUI mit Test-Engine

Koordiniert die Kommunikation zwischen MainWindow und TestEngine.
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QMessageBox

from core.test_engine import TestEngine, TestConfig, TestState
from core.session import SessionManager
from core.file_manager import FileManager
from .dialogs import (
    SessionRestoreDialog,
    DeleteFilesDialog,
    StopConfirmationDialog,
    ErrorDetailDialog
)


class TestController(QObject):
    """
    Controller für DiskTest-Logik

    Verbindet MainWindow mit TestEngine und koordiniert:
    - Start/Pause/Resume/Stop des Tests
    - Session-Wiederherstellung
    - Progress-Updates
    - Error-Handling
    - Dateiverwaltung
    """

    def __init__(self, main_window):
        """
        Initialisiert den Controller

        Args:
            main_window: Referenz zum MainWindow
        """
        super().__init__()

        self.window = main_window
        self.engine: Optional[TestEngine] = None
        self.current_state = TestState.IDLE

        # Fehler-Liste für Detail-Dialog
        self.errors = []

        # Statistiken
        self.test_start_time = None

        # Signals verbinden
        self._connect_gui_signals()

        # Session-Wiederherstellung beim Start prüfen
        self._check_for_existing_session()

    def _connect_gui_signals(self):
        """Verbindet GUI-Signals mit Controller-Slots"""
        # Control-Buttons
        self.window.control_widget.start_clicked.connect(self.on_start_clicked)
        self.window.control_widget.pause_clicked.connect(self.on_pause_clicked)
        self.window.control_widget.stop_clicked.connect(self.on_stop_clicked)
        self.window.control_widget.delete_files_clicked.connect(self.on_delete_files_clicked)

        # Error-Counter klickbar machen
        self.window.progress_widget.error_counter.clicked.connect(self.on_error_counter_clicked)

        # Config-Änderungen
        self.window.config_widget.path_changed.connect(self.on_path_changed)

    def _check_for_existing_session(self):
        """Prüft beim Start ob eine Session existiert und fragt User"""
        # Aktuellen Pfad aus Config nehmen (oder Default)
        config = self.window.config_widget.get_config()
        target_path = config.get('target_path', '')

        if not target_path or not os.path.exists(target_path):
            return

        # Session-Manager erstellen
        session_manager = SessionManager(target_path)

        if not session_manager.exists():
            return

        # Session laden
        try:
            session_data = session_manager.load()
        except Exception as e:
            QMessageBox.warning(
                self.window,
                "Session-Fehler",
                f"Fehler beim Laden der Session:\n{e}\n\nDie Session wird ignoriert."
            )
            return

        # Dialog anzeigen
        session_info = {
            'target_path': session_data.target_path,
            'progress': int(session_data.get_progress_percentage()),
            'pattern_index': session_data.current_pattern_index,
            'pattern_name': self._get_pattern_name(session_data.current_pattern_index),
            'error_count': len(session_data.errors)
        }

        dialog = SessionRestoreDialog(session_info, self.window)
        result = dialog.exec()

        if result == SessionRestoreDialog.RESULT_RESUME:
            # Session fortsetzen
            self._resume_session(session_data)
        elif result == SessionRestoreDialog.RESULT_NEW_TEST:
            # Session löschen
            try:
                session_manager.delete()
                self.window.set_session_info("")
            except Exception as e:
                QMessageBox.warning(
                    self.window,
                    "Fehler",
                    f"Fehler beim Löschen der Session:\n{e}"
                )

    def _get_pattern_name(self, pattern_index: int) -> str:
        """Gibt den Namen eines Musters zurück"""
        from core.patterns import PATTERN_SEQUENCE
        if 0 <= pattern_index < len(PATTERN_SEQUENCE):
            return PATTERN_SEQUENCE[pattern_index].display_name
        return "--"

    def _resume_session(self, session_data):
        """Stellt GUI-State aus Session wieder her"""
        # Config setzen
        config = {
            'target_path': session_data.target_path,
            'test_size_gb': session_data.total_size_gb,
            'file_size_mb': int(session_data.file_size_gb * 1024),
            'whole_drive': False
        }
        self.window.config_widget.set_config(config)

        # Progress setzen
        progress = int(session_data.get_progress_percentage())
        self.window.progress_widget.set_progress(progress)

        pattern_idx = session_data.current_pattern_index
        pattern_name = self._get_pattern_name(pattern_idx)
        self.window.progress_widget.set_pattern(f"{pattern_idx + 1}/5 ({pattern_name})")

        phase = "Schreiben" if session_data.current_phase == "write" else "Verifizieren"
        self.window.progress_widget.set_phase(phase)

        file_info = f"{session_data.current_file_index + 1}/{session_data.file_count}"
        self.window.progress_widget.set_file(file_info)

        # Fehler setzen
        self.errors = session_data.errors
        self.window.progress_widget.set_error_count(len(self.errors))

        # State setzen
        self.window.control_widget.set_state_paused()
        self.window.config_widget.set_enabled(False)
        self.current_state = TestState.PAUSED

        # Session-Info anzeigen
        session_path = Path(session_data.target_path) / "disktest_session.json"
        self.window.set_session_info(str(session_path))

        # Log
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            "Session wiederhergestellt - Test pausiert"
        )
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Fortschritt: {progress}% - Muster {pattern_idx + 1}/5"
        )

    @Slot()
    def on_start_clicked(self):
        """Start/Fortsetzen-Button wurde geklickt"""
        if self.current_state == TestState.IDLE:
            self._start_new_test()
        elif self.current_state == TestState.PAUSED:
            self._resume_test()

    @Slot()
    def on_pause_clicked(self):
        """Pause-Button wurde geklickt"""
        if self.engine and self.current_state == TestState.RUNNING:
            self.engine.pause()
            self.window.control_widget.set_state_paused()
            self.current_state = TestState.PAUSED

            self.window.log_widget.add_log(
                self._get_timestamp(),
                "INFO",
                "Test pausiert"
            )

    @Slot()
    def on_stop_clicked(self):
        """Stop-Button wurde geklickt"""
        # Bestätigungs-Dialog
        dialog = StopConfirmationDialog(self.window)
        if dialog.exec() != StopConfirmationDialog.DialogCode.Accepted:
            return

        # Test stoppen
        if self.engine:
            self.engine.stop()
            self.engine.wait()  # Warten bis Thread beendet

        # Session löschen
        config = self.window.config_widget.get_config()
        if config['target_path']:
            try:
                session_manager = SessionManager(config['target_path'])
                session_manager.delete()
            except Exception:
                pass

        # GUI zurücksetzen
        self._reset_gui()

        self.window.log_widget.add_log(
            self._get_timestamp(),
            "WARNING",
            "Test abgebrochen"
        )

    @Slot()
    def on_delete_files_clicked(self):
        """Dateien löschen-Button wurde geklickt"""
        config = self.window.config_widget.get_config()
        target_path = config['target_path']

        if not target_path or not os.path.exists(target_path):
            QMessageBox.warning(
                self.window,
                "Fehler",
                "Bitte wählen Sie zuerst einen gültigen Zielpfad."
            )
            return

        # Testdateien zählen und Größe ermitteln
        file_manager = FileManager(target_path, 1.0)  # Größe egal
        file_count = file_manager.count_existing_files()

        if file_count == 0:
            QMessageBox.information(
                self.window,
                "Keine Dateien",
                "Es wurden keine Testdateien gefunden."
            )
            return

        # Gesamtgröße berechnen
        total_size_bytes = file_manager.get_existing_files_size()
        total_size_gb = total_size_bytes / (1024 ** 3)

        # Bestätigungs-Dialog
        dialog = DeleteFilesDialog(
            target_path,
            file_count,
            total_size_gb,
            self.window
        )

        if dialog.exec() != DeleteFilesDialog.DialogCode.Accepted:
            return

        # Dateien löschen
        try:
            deleted_count = file_manager.delete_all_files()
        except Exception as e:
            self.window.log_widget.add_log(
                self._get_timestamp(),
                "ERROR",
                f"Fehler beim Löschen: {e}"
            )
            deleted_count = 0

        # Feedback
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "SUCCESS",
            f"{deleted_count} Testdateien gelöscht ({total_size_gb:.1f} GB)"
        )

        QMessageBox.information(
            self.window,
            "Erfolgreich",
            f"{deleted_count} Testdateien wurden gelöscht."
        )

        # Delete-Button deaktivieren
        self._update_delete_button()

    @Slot()
    def on_error_counter_clicked(self):
        """Error-Counter wurde geklickt - zeigt Detail-Dialog"""
        if not self.errors:
            return

        # Fehler für Dialog formatieren
        error_list = []
        for err in self.errors:
            error_list.append({
                'filename': err.get('file', 'Unbekannt'),
                'pattern': err.get('pattern', '--'),
                'phase': 'Schreiben' if err.get('phase') == 'write' else 'Verifizierung',
                'details': err.get('message', 'Keine Details')
            })

        dialog = ErrorDetailDialog(error_list, self.window)
        dialog.exec()

    @Slot(str)
    def on_path_changed(self, path: str):
        """Pfad wurde geändert"""
        self._update_delete_button()

    def _start_new_test(self):
        """Startet einen neuen Test"""
        # Config validieren
        config = self.window.config_widget.get_config()

        if not config['target_path'] or not os.path.exists(config['target_path']):
            QMessageBox.warning(
                self.window,
                "Fehler",
                "Bitte wählen Sie einen gültigen Zielpfad."
            )
            return

        if config['test_size_gb'] <= 0:
            QMessageBox.warning(
                self.window,
                "Fehler",
                "Die Testgröße muss größer als 0 sein."
            )
            return

        # Test-Config erstellen
        file_size_gb = config['file_size_mb'] / 1024.0

        test_config = TestConfig(
            target_path=config['target_path'],
            file_size_gb=file_size_gb,
            total_size_gb=config['test_size_gb'],
            resume_session=False,
            selected_patterns=config.get('selected_patterns', None)
        )

        # Engine erstellen
        self.engine = TestEngine(test_config)
        self._connect_engine_signals()

        # GUI vorbereiten
        self.errors = []
        self.test_start_time = datetime.now()
        self.window.control_widget.set_state_running()
        self.window.config_widget.set_enabled(False)
        self.window.progress_widget.reset()
        self.current_state = TestState.RUNNING

        # Session-Info
        session_path = Path(config['target_path']) / "disktest_session.json"
        self.window.set_session_info(str(session_path))

        # Log
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Test gestartet - Ziel: {config['target_path']}"
        )
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Konfiguration: {config['test_size_gb']} GB, Dateigröße: {config['file_size_mb']} MB"
        )

        # Engine starten
        self.engine.start()

    def _resume_test(self):
        """Setzt pausierte Test fort"""
        if not self.engine:
            # Keine Engine vorhanden - Session laden und neue Engine erstellen
            config = self.window.config_widget.get_config()
            session_manager = SessionManager(config['target_path'])

            try:
                session_data = session_manager.load()
            except Exception as e:
                QMessageBox.critical(
                    self.window,
                    "Fehler",
                    f"Session konnte nicht geladen werden:\n{e}"
                )
                return

            # Test-Config mit Session erstellen
            test_config = TestConfig(
                target_path=session_data.target_path,
                file_size_gb=session_data.file_size_gb,
                total_size_gb=session_data.total_size_gb,
                resume_session=True,
                session_data=session_data,
                selected_patterns=None  # Wird aus session_data wiederhergestellt
            )

            self.engine = TestEngine(test_config)
            self._connect_engine_signals()

            # Engine starten
            self.engine.start()
        else:
            # Bestehende Engine fortsetzen
            self.engine.resume()

        # GUI aktualisieren
        self.window.control_widget.set_state_running()
        self.current_state = TestState.RUNNING

        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            "Test fortgesetzt"
        )

    def _connect_engine_signals(self):
        """Verbindet Engine-Signals mit Controller-Slots"""
        self.engine.progress_updated.connect(self.on_progress_updated)
        self.engine.status_changed.connect(self.on_status_changed)
        self.engine.log_entry.connect(self.on_log_entry)
        self.engine.error_occurred.connect(self.on_error_occurred)
        self.engine.test_completed.connect(self.on_test_completed)
        self.engine.pattern_changed.connect(self.on_pattern_changed)
        self.engine.phase_changed.connect(self.on_phase_changed)

    @Slot(float, float, float)
    def on_progress_updated(self, current_bytes: float, total_bytes: float, speed_mbps: float):
        """Progress-Update von Engine"""
        # Prozent berechnen
        if total_bytes > 0:
            percent = int((current_bytes / total_bytes) * 100)
        else:
            percent = 0

        self.window.progress_widget.set_progress(percent)
        self.window.progress_widget.set_speed(f"{speed_mbps:.1f} MB/s")

        # Restzeit schätzen
        if speed_mbps > 0:
            remaining_bytes = total_bytes - current_bytes
            remaining_mb = remaining_bytes / (1024 * 1024)
            remaining_seconds = remaining_mb / speed_mbps

            time_str = self._format_time_remaining(remaining_seconds)
            self.window.progress_widget.set_time_remaining(time_str)

    @Slot(str)
    def on_status_changed(self, status: str):
        """Status-Update von Engine"""
        self.window.statusBar().showMessage(status)

    @Slot(str)
    def on_log_entry(self, message: str):
        """Log-Eintrag von Engine"""
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            message
        )

    @Slot(dict)
    def on_error_occurred(self, error: dict):
        """Fehler von Engine"""
        self.errors.append(error)
        self.window.progress_widget.set_error_count(len(self.errors))

        # Log
        message = f"{error.get('file', '?')} - {error.get('message', 'Fehler')}"
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "ERROR",
            message
        )

    @Slot(dict)
    def on_test_completed(self, summary: dict):
        """Test abgeschlossen"""
        elapsed = summary.get('elapsed_seconds', 0)
        error_count = summary.get('error_count', 0)

        # Log
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "SUCCESS",
            f"Test abgeschlossen - Dauer: {self._format_time_remaining(elapsed)}"
        )
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Fehler: {error_count}"
        )

        # GUI zurücksetzen
        self._reset_gui()

        # Erfolgs-Dialog
        if error_count == 0:
            QMessageBox.information(
                self.window,
                "Test abgeschlossen",
                f"Der Test wurde erfolgreich abgeschlossen!\n\n"
                f"Dauer: {self._format_time_remaining(elapsed)}\n"
                f"Keine Fehler gefunden."
            )
        else:
            QMessageBox.warning(
                self.window,
                "Test abgeschlossen",
                f"Der Test wurde abgeschlossen.\n\n"
                f"Dauer: {self._format_time_remaining(elapsed)}\n"
                f"Fehler: {error_count}\n\n"
                f"Klicken Sie auf den Fehler-Counter für Details."
            )

    @Slot(int, str)
    def on_pattern_changed(self, pattern_index: int, pattern_name: str):
        """Muster-Wechsel von Engine"""
        self.window.progress_widget.set_pattern(f"{pattern_index + 1}/5 ({pattern_name})")

    @Slot(str)
    def on_phase_changed(self, phase: str):
        """Phasen-Wechsel von Engine"""
        self.window.progress_widget.set_phase(phase)

    def _reset_gui(self):
        """Setzt GUI in Idle-Zustand zurück"""
        self.window.control_widget.set_state_idle()
        self.window.config_widget.set_enabled(True)
        self.window.set_session_info("")
        self.current_state = TestState.IDLE
        self.window.statusBar().showMessage("Bereit")
        self._update_delete_button()

    def _update_delete_button(self):
        """Aktualisiert Delete-Button basierend auf vorhandenen Dateien"""
        config = self.window.config_widget.get_config()
        target_path = config.get('target_path', '')

        if target_path and os.path.exists(target_path):
            file_manager = FileManager(target_path, 1.0)
            has_files = file_manager.count_existing_files() > 0
            self.window.control_widget.enable_delete_button(has_files)
        else:
            self.window.control_widget.enable_delete_button(False)

    def _get_timestamp(self) -> str:
        """Gibt aktuellen Timestamp zurück"""
        return datetime.now().strftime("%H:%M:%S")

    def _format_time_remaining(self, seconds: float) -> str:
        """Formatiert Restzeit"""
        s = int(seconds)
        if s < 60:
            return f"{s}s"

        h = s // 3600
        m = (s % 3600) // 60

        if h > 0:
            return f"{h}h {m}m"
        else:
            return f"{m}m"
