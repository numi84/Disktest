"""
Test-Controller - Steuert Test-Engine

Verantwortlich für:
- Test starten/pausieren/stoppen
- Progress-Updates empfangen
- Error-Handling während Test
"""

import os
import shutil
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from PySide6.QtCore import QObject, Slot, QTimer
from PySide6.QtWidgets import QMessageBox

from core.test_engine import TestEngine, TestConfig, TestState
from core.session import SessionManager, SessionData
from core.file_manager import FileManager
from core.patterns import PatternType, PATTERN_SEQUENCE
from core.platform import get_window_activator

from .settings_controller import SettingsController
from .file_controller import FileController
from .session_controller import SessionController

if TYPE_CHECKING:
    from gui.main_window import MainWindow


class TestController(QObject):
    """
    Hauptcontroller für Test-Ausführung.

    Koordiniert alle anderen Controller und steuert die Test-Engine.
    """

    def __init__(self, main_window: "MainWindow"):
        """
        Initialisiert den Controller.

        Args:
            main_window: Referenz zum MainWindow
        """
        super().__init__()

        self.window: "MainWindow" = main_window
        self.engine: Optional[TestEngine] = None
        self.current_state = TestState.IDLE

        # Sub-Controller initialisieren
        self.settings = SettingsController()
        self.file_controller = FileController(main_window, self._get_timestamp)
        self.session_controller = SessionController(
            main_window,
            self.settings,
            self.file_controller,
            self._get_timestamp
        )

        # Fehler-Liste für Detail-Dialog
        self.errors = []

        # Statistiken
        self.test_start_time = None

        # Signals verbinden
        self._connect_gui_signals()

        # Letzten Pfad laden und setzen
        self._load_last_path()

        # Session-Wiederherstellung beim Start prüfen
        self.session_controller.check_for_existing_session()

        # Delete-Button Status aktualisieren
        self._update_delete_button()

    def _connect_gui_signals(self):
        """Verbindet GUI-Signals mit Controller-Slots."""
        # Control-Buttons
        self.window.control_widget.start_clicked.connect(self.on_start_clicked)
        self.window.control_widget.pause_clicked.connect(self.on_pause_clicked)
        self.window.control_widget.stop_after_file_clicked.connect(self.on_stop_after_file_clicked)
        self.window.control_widget.stop_clicked.connect(self.on_stop_clicked)
        self.window.control_widget.delete_files_clicked.connect(self.on_delete_files_clicked)

        # Pattern-Auswahl Änderungen
        self.window.config_widget.pattern_widget.selection_changed.connect(self.on_pattern_selection_changed)

        # Error-Counter klickbar machen
        self.window.progress_widget.error_counter.clicked.connect(self.on_error_counter_clicked)

        # Config-Änderungen
        self.window.config_widget.path_changed.connect(self.on_path_changed)

    def _load_last_path(self):
        """Lädt den zuletzt verwendeten Pfad aus QSettings."""
        last_path = self.settings.get_last_path()
        if last_path and os.path.exists(last_path):
            self.window.config_widget.path_edit.setText(last_path)

    # --- Button-Handler ---

    @Slot()
    def on_start_clicked(self):
        """Start/Fortsetzen-Button wurde geklickt."""
        if self.current_state == TestState.IDLE:
            self._start_new_test()
        elif self.current_state == TestState.PAUSED:
            self._resume_test()

    @Slot()
    def on_pause_clicked(self):
        """Pause-Button wurde geklickt."""
        if self.engine and self.current_state == TestState.RUNNING:
            self.engine.pause()
            self.window.control_widget.set_state_paused()
            self.window.enable_pattern_selection(True)  # Pattern-Auswahl bei Pause aktivieren
            self.current_state = TestState.PAUSED

            self.window.log_widget.add_log(
                self._get_timestamp(),
                "INFO",
                "Test pausiert"
            )

    @Slot()
    def on_stop_after_file_clicked(self):
        """Pause-nach-Datei Button wurde geklickt."""
        from gui.dialogs import StopConfirmationDialog

        if self.engine and self.current_state == TestState.RUNNING:
            self.engine.stop_after_current_file()

            # Sofort Button-State auf Pausiert setzen
            self.window.control_widget.set_state_paused()
            self.window.enable_pattern_selection(True)  # Pattern-Auswahl bei Pause aktivieren
            self.current_state = TestState.PAUSED

            self.window.log_widget.add_log(
                self._get_timestamp(),
                "INFO",
                "Pausiere nach aktueller Datei..."
            )

    @Slot()
    def on_stop_clicked(self):
        """Stop-Button wurde geklickt."""
        from gui.dialogs import StopConfirmationDialog

        # Bestätigungs-Dialog
        dialog = StopConfirmationDialog(self.window)
        activate_window = get_window_activator()
        activate_window(dialog)
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
        """Dateien löschen-Button wurde geklickt."""
        config = self.window.config_widget.get_config()
        target_path = config['target_path']

        deleted_count, errors = self.file_controller.delete_test_files(target_path)

        # Delete-Button deaktivieren
        self._update_delete_button()

    @Slot()
    def on_error_counter_clicked(self):
        """Error-Counter wurde geklickt - zeigt Detail-Dialog."""
        from gui.dialogs import ErrorDetailDialog

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
        activate_window = get_window_activator()
        activate_window(dialog)
        dialog.exec()

    @Slot(str)
    def on_path_changed(self, path: str):
        """Pfad wurde geändert."""
        self._update_delete_button()

    @Slot()
    def on_pattern_selection_changed(self):
        """Pattern-Auswahl wurde geändert (während pausierter Session)."""
        # Nur aktiv wenn Test pausiert ist und Engine existiert
        if self.current_state != TestState.PAUSED or not self.engine or not self.engine.session:
            return

        # Hole aktuelle Pattern-Auswahl aus GUI
        new_selected_patterns = self.window.config_widget.pattern_widget.get_selected_patterns()
        new_selected_pattern_values = [p.value for p in new_selected_patterns]

        # Hole alte Pattern-Auswahl aus Session
        old_selected_pattern_values = self.engine.session.selected_patterns

        # Prüfe ob sich was geändert hat
        if new_selected_pattern_values == old_selected_pattern_values:
            return

        # Prüfe ob bereits getestete Patterns entfernt wurden
        completed = self.engine.session.completed_patterns if hasattr(self.engine.session, 'completed_patterns') else []
        removed_completed = [p for p in completed if p not in new_selected_pattern_values]

        if removed_completed:
            # Warnung: Getestete Patterns werden entfernt
            pattern_names = [PatternType(p).display_name for p in removed_completed]
            msg = QMessageBox(self.window)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Pattern-Änderung")
            msg.setText(f"Die folgenden Muster wurden bereits getestet:\n\n{', '.join(pattern_names)}\n\nDurch Entfernen wird der Fortschritt für diese Muster verworfen.")
            msg.setInformativeText("Möchten Sie fortfahren?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            activate_window = get_window_activator()
            activate_window(msg)

            if msg.exec() != QMessageBox.Yes:
                # User hat abgebrochen - Pattern-Widget zurücksetzen
                self.window.config_widget.pattern_widget.set_selected_patterns(
                    [PatternType(p) for p in old_selected_pattern_values]
                )
                return

            # User hat bestätigt - completed_patterns aktualisieren
            self.engine.session.completed_patterns = [p for p in completed if p in new_selected_pattern_values]

        # Prüfe ob neue Patterns hinzugefügt wurden
        added_patterns = [p for p in new_selected_pattern_values if p not in old_selected_pattern_values]
        if added_patterns:
            pattern_names = [PatternType(p).display_name for p in added_patterns]
            info_msg = QMessageBox(self.window)
            info_msg.setIcon(QMessageBox.Information)
            info_msg.setWindowTitle("Pattern-Änderung")
            info_msg.setText(f"{len(added_patterns)} neue Muster hinzugefügt:\n\n{', '.join(pattern_names)}")
            info_msg.setInformativeText("Diese werden nach den bestehenden Mustern getestet.")
            activate_window = get_window_activator()
            activate_window(info_msg)
            info_msg.exec()

        # Session aktualisieren
        self.engine.session.selected_patterns = new_selected_pattern_values

        # Session sofort speichern
        try:
            self.engine.session_manager.save(self.engine.session)
            self.window.log_widget.add_log(
                self._get_timestamp(),
                "INFO",
                f"Testmuster angepasst: {len(new_selected_patterns)} Muster ausgewählt"
            )
        except Exception as e:
            self.window.log_widget.add_log(
                self._get_timestamp(),
                "ERROR",
                f"Fehler beim Speichern der Session: {e}"
            )

    # --- Test-Steuerung ---

    def _start_new_test(self):
        """Startet einen neuen Test."""
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

        # Prüfe ZUERST auf vorhandene Testdateien
        file_size_gb = config['file_size_mb'] / 1024.0
        test_files = list(Path(config['target_path']).glob("disktest_*.dat"))

        if test_files:
            # Testdateien gefunden - File Recovery anbieten
            # WICHTIG: Dieser Schritt läuft VOR Speicherplatz-Check
            # Wenn User "Fortsetzen" wählt, werden vorhandene Dateien wiederverwendet
            recovery_result = self.file_controller.handle_orphaned_files_interactive(
                config['target_path'],
                file_size_gb,
                config['test_size_gb']
            )

            if recovery_result == "reconstructed":
                # Session wurde erstellt
                # Lade Session und setze GUI-State
                session_manager = SessionManager(config['target_path'])
                try:
                    session_data = session_manager.load()
                    self.errors = session_data.errors
                    self.window.progress_widget.set_error_count(len(self.errors))
                    self.session_controller.resume_session(session_data)
                    self.current_state = TestState.PAUSED
                except Exception as e:
                    self.window.log_widget.add_log(
                        self._get_timestamp(),
                        "ERROR",
                        f"Fehler beim Laden der rekonstruierten Session: {e}"
                    )
                return
            elif recovery_result == "new_test":
                # User möchte neu starten - Dateien überschreiben
                # Weiter mit Speicherplatz-Check
                pass
            else:
                # Abgebrochen
                return

        # Speicherplatz prüfen (nur wenn KEIN File Recovery oder "Neuer Test")
        try:
            disk_usage = shutil.disk_usage(config['target_path'])
            free_space_gb = disk_usage.free / (1024 ** 3)

            # Vorhandene Testdateien einrechnen (werden überschrieben)
            # FileManager: Berechne file_count für richtige Stellenzahl
            file_count = int(config['test_size_gb'] / file_size_gb)
            file_count = max(1, file_count)
            fm = FileManager(config['target_path'], file_size_gb, file_count)
            existing_size_gb = fm.get_existing_files_size() / (1024 ** 3)
            available_gb = free_space_gb + existing_size_gb

            if config['test_size_gb'] > available_gb:
                QMessageBox.warning(
                    self.window,
                    "Nicht genügend Speicherplatz",
                    f"Angefordert: {config['test_size_gb']:.1f} GB\n"
                    f"Verfügbar: {available_gb:.1f} GB\n"
                    f"  (Frei: {free_space_gb:.1f} GB + Testdateien: {existing_size_gb:.1f} GB)\n\n"
                    "Bitte reduzieren Sie die Testgröße oder wählen Sie "
                    "einen anderen Speicherort."
                )
                return
        except Exception as e:
            QMessageBox.warning(
                self.window,
                "Fehler",
                f"Speicherplatz konnte nicht ermittelt werden:\n{e}"
            )
            return

        # Pfad speichern für spätere Sessions
        self.settings.save_last_path(config['target_path'])
        self.settings.add_recent_session(config['target_path'])

        # Log-Verzeichnis bestimmen
        log_dir = None
        if config.get('log_in_userdir', False):
            # Benutzerverzeichnis für Logs verwenden
            log_dir = self._get_user_log_dir()

        # Test-Config erstellen
        test_config = TestConfig(
            target_path=config['target_path'],
            file_size_gb=file_size_gb,
            total_size_gb=config['test_size_gb'],
            resume_session=False,
            selected_patterns=config.get('selected_patterns', None),
            log_dir=log_dir
        )

        # Engine erstellen
        self.engine = TestEngine(test_config)
        self._connect_engine_signals()

        # GUI vorbereiten
        self.errors = []
        self.test_start_time = datetime.now()
        self.window.control_widget.set_state_running()
        self.window.config_widget.set_enabled(False)
        self.window.enable_pattern_selection(False)  # Pattern-Widget während Test sperren
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
        """Setzt pausierte Test fort."""
        if not self.engine:
            # Keine Engine vorhanden - Session laden und neue Engine erstellen
            config = self.window.config_widget.get_config()
            session_manager = SessionManager(config['target_path'])

            # Speichere Pfad in Recent Sessions
            self.settings.add_recent_session(config['target_path'])

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
            # WICHTIG: Verwende aktuelle GUI-Einstellung für total_size_gb und selected_patterns,
            # da User beim Fortsetzen diese ändern kann
            current_config = self.window.config_widget.get_config()
            new_total_size_gb = current_config.get('test_size_gb', session_data.total_size_gb)
            new_selected_patterns = current_config.get('selected_patterns', None)

            # Dateianzahl neu berechnen falls Testgröße geändert wurde
            new_file_count = int(new_total_size_gb / session_data.file_size_gb)
            if new_file_count != session_data.file_count:
                # Session-Daten aktualisieren
                session_data.total_size_gb = new_total_size_gb
                session_data.file_count = new_file_count

                self.window.log_widget.add_log(
                    self._get_timestamp(),
                    "INFO",
                    f"Testgröße angepasst: {new_total_size_gb} GB ({new_file_count} Dateien)"
                )

            # Pattern-Auswahl aktualisieren falls geändert
            if new_selected_patterns is not None:
                new_selected_pattern_values = [p.value for p in new_selected_patterns]
                old_selected_pattern_values = session_data.selected_patterns

                if new_selected_pattern_values != old_selected_pattern_values:
                    # Prüfe ob bereits getestete Patterns entfernt wurden
                    completed = session_data.completed_patterns if hasattr(session_data, 'completed_patterns') else []
                    removed_completed = [p for p in completed if p not in new_selected_pattern_values]

                    if removed_completed:
                        # Warnung: Getestete Patterns werden entfernt
                        pattern_names = [PatternType(p).display_name for p in removed_completed]
                        msg = QMessageBox(self.window)
                        msg.setIcon(QMessageBox.Warning)
                        msg.setWindowTitle("Pattern-Änderung")
                        msg.setText(f"Die folgenden Muster wurden bereits getestet:\n\n{', '.join(pattern_names)}\n\nDurch Entfernen wird der Fortschritt für diese Muster verworfen.")
                        msg.setInformativeText("Möchten Sie fortfahren?")
                        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msg.setDefaultButton(QMessageBox.No)
                        activate_window = get_window_activator()
                        activate_window(msg)

                        if msg.exec() != QMessageBox.Yes:
                            # User hat abgebrochen - Pattern-Widget zurücksetzen
                            self.window.config_widget.pattern_widget.set_selected_patterns(
                                [PatternType(p) for p in old_selected_pattern_values]
                            )
                            return

                        # User hat bestätigt - completed_patterns aktualisieren
                        session_data.completed_patterns = [p for p in completed if p in new_selected_pattern_values]

                    # Prüfe ob neue Patterns hinzugefügt wurden
                    added_patterns = [p for p in new_selected_pattern_values if p not in old_selected_pattern_values]
                    if added_patterns:
                        pattern_names = [PatternType(p).display_name for p in added_patterns]
                        info_msg = QMessageBox(self.window)
                        info_msg.setIcon(QMessageBox.Information)
                        info_msg.setWindowTitle("Pattern-Änderung")
                        info_msg.setText(f"{len(added_patterns)} neue Muster hinzugefügt:\n\n{', '.join(pattern_names)}")
                        info_msg.setInformativeText("Diese werden nach den bestehenden Mustern getestet.")
                        activate_window = get_window_activator()
                        activate_window(info_msg)
                        info_msg.exec()

                    session_data.selected_patterns = new_selected_pattern_values

                    self.window.log_widget.add_log(
                        self._get_timestamp(),
                        "INFO",
                        f"Testmuster angepasst: {len(new_selected_patterns)} Muster ausgewählt"
                    )

                    # Session sofort speichern, damit Änderungen persistent sind
                    try:
                        session_manager.save(session_data)
                    except Exception as e:
                        self.window.log_widget.add_log(
                            self._get_timestamp(),
                            "ERROR",
                            f"Fehler beim Speichern der Session: {e}"
                        )

            test_config = TestConfig(
                target_path=session_data.target_path,
                file_size_gb=session_data.file_size_gb,
                total_size_gb=new_total_size_gb,
                resume_session=True,
                session_data=session_data,
                selected_patterns=new_selected_patterns
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
        self.window.enable_pattern_selection(False)  # Pattern-Widget während Test sperren
        self.current_state = TestState.RUNNING

        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            "Test fortgesetzt"
        )

    def _connect_engine_signals(self):
        """Verbindet Engine-Signals mit Controller-Slots."""
        self.engine.progress_updated.connect(self.on_progress_updated)
        self.engine.file_progress_updated.connect(self.on_file_progress_updated)
        self.engine.file_changed.connect(self.on_file_changed)
        self.engine.status_changed.connect(self.on_status_changed)
        self.engine.log_entry.connect(self.on_log_entry)
        self.engine.error_occurred.connect(self.on_error_occurred)
        self.engine.test_completed.connect(self.on_test_completed)
        self.engine.pattern_changed.connect(self.on_pattern_changed)
        self.engine.phase_changed.connect(self.on_phase_changed)

    # --- Engine-Signal-Handler ---

    @Slot(float, float, float)
    def on_progress_updated(self, current_bytes: float, total_bytes: float, speed_mbps: float):
        """Progress-Update von Engine."""
        # Test-Fortschritt berechnen (über alle Muster)
        test_percent = self._calculate_test_progress(current_bytes, total_bytes)
        self.window.progress_widget.set_test_progress(test_percent)

        # Alle-Dateien-Fortschritt berechnen (aktuelles Muster + Phase)
        all_files_percent = self._calculate_all_files_progress(current_bytes, total_bytes)
        self.window.progress_widget.set_all_files_progress(all_files_percent)

        self.window.progress_widget.set_speed(f"{speed_mbps:.1f} MB/s")

        # Restzeit schätzen - basierend auf tatsächlichem Test-Fortschritt
        if speed_mbps > 0:
            remaining_seconds = self._calculate_time_remaining(test_percent, speed_mbps)
            time_str = self._format_time_remaining(remaining_seconds)
            self.window.progress_widget.set_time_remaining(time_str)

    @Slot(int)
    def on_file_progress_updated(self, percent: int):
        """Datei-Fortschritt Update von Engine."""
        self.window.progress_widget.set_file_progress(percent)

    @Slot(int, int)
    def on_file_changed(self, current_file_index: int, total_file_count: int):
        """Datei-Wechsel von Engine."""
        file_info = f"{current_file_index + 1}/{total_file_count}"
        self.window.progress_widget.set_file(file_info)

    @Slot(str)
    def on_status_changed(self, status: str):
        """Status-Update von Engine."""
        self.window.statusBar().showMessage(status)

    @Slot(str)
    def on_log_entry(self, message: str):
        """Log-Eintrag von Engine."""
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            message
        )

    @Slot(dict)
    def on_error_occurred(self, error: dict):
        """Fehler von Engine."""
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
        """Test abgeschlossen."""
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

        # Warte kurz damit User die 100% sieht, dann GUI zurücksetzen
        QTimer.singleShot(500, self._reset_gui)  # 500ms delay

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
        """Muster-Wechsel von Engine."""
        # Hole Anzahl ausgewählter Patterns aus Engine-Session
        total_patterns = 5  # Default
        if self.engine and self.engine.session:
            total_patterns = len(self.engine.session.selected_patterns) if self.engine.session.selected_patterns else 5
        self.window.progress_widget.set_pattern(f"{pattern_index + 1}/{total_patterns} ({pattern_name})")

    @Slot(str)
    def on_phase_changed(self, phase: str):
        """Phasen-Wechsel von Engine."""
        self.window.progress_widget.set_phase(phase)
        # Beim Phasenwechsel "Alle Dateien" zurücksetzen
        self.window.progress_widget.set_all_files_progress(0)

    # --- Helper-Methoden ---

    def _reset_gui(self):
        """Setzt GUI in Idle-Zustand zurück."""
        self.window.control_widget.set_state_idle()
        self.window.config_widget.set_enabled(True)
        self.window.enable_pattern_selection(True)  # Pattern-Auswahl wieder aktivieren
        self.window.set_session_info("")
        self.current_state = TestState.IDLE
        self.window.statusBar().showMessage("Bereit")
        self._update_delete_button()

    def _update_delete_button(self):
        """Aktualisiert Delete-Button basierend auf vorhandenen Dateien."""
        config = self.window.config_widget.get_config()
        target_path = config.get('target_path', '')

        if target_path and os.path.exists(target_path):
            file_manager = FileManager(target_path, 1.0)
            has_files = file_manager.count_existing_files() > 0
            self.window.control_widget.enable_delete_button(has_files)
        else:
            self.window.control_widget.enable_delete_button(False)

    def _get_timestamp(self) -> str:
        """Gibt aktuellen Timestamp zurück."""
        return datetime.now().strftime("%H:%M:%S")

    def _get_user_log_dir(self) -> str:
        """Gibt das Benutzerverzeichnis für Logs zurück."""
        # Benutze das Dokumente-Verzeichnis oder Home-Verzeichnis
        home = Path.home()
        log_dir = home / "DiskTest_Logs"
        # Verzeichnis erstellen falls nicht vorhanden
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir)

    def _calculate_test_progress(self, current_bytes: float, total_bytes: float) -> int:
        """
        Berechnet Test-Fortschritt über alle Muster.

        Formel: (completed_patterns * 2 + current_phase) / (total_patterns * 2) * 100

        Args:
            current_bytes: Bereits verarbeitete Bytes
            total_bytes: Gesamtbytes des Tests

        Returns:
            Fortschritt in Prozent (0-100)
        """
        if not self.engine or not self.engine.session:
            return 0

        session = self.engine.session

        # Anzahl ausgewählter Patterns
        total_patterns = len(session.selected_patterns) if session.selected_patterns else 5

        # Anzahl abgeschlossener Patterns (beide Phasen komplett)
        completed_patterns = len(session.completed_patterns) if session.completed_patterns else 0

        # Aktuelles Pattern: Wie viele Phasen sind abgeschlossen?
        # - Wenn Phase "write": 0 Phasen abgeschlossen
        # - Wenn Phase "verify": 1 Phase abgeschlossen (write ist fertig)
        current_phase_value = 1 if session.current_phase == "verify" else 0

        # Bytes pro Datei
        file_size_bytes = session.file_size_gb * 1024 * 1024 * 1024
        bytes_per_file = int(file_size_bytes)

        # Fortschritt in der aktuellen Phase (0.0 - 1.0)
        bytes_per_phase = session.file_count * bytes_per_file
        current_file_bytes = session.current_file_index * bytes_per_file
        current_chunk_bytes = session.current_chunk_index * self.engine.CHUNK_SIZE
        phase_bytes = current_file_bytes + current_chunk_bytes
        phase_progress = min(1.0, phase_bytes / bytes_per_phase) if bytes_per_phase > 0 else 0.0

        # Gesamtfortschritt berechnen
        # completed_patterns sind komplett (2 Phasen je Pattern)
        # Aktuelles Pattern: current_phase_value Phasen + Fortschritt in aktueller Phase
        total_phases = total_patterns * 2  # Jedes Pattern hat 2 Phasen (write + verify)
        completed_phases = (completed_patterns * 2) + current_phase_value + phase_progress

        percent = int((completed_phases / total_phases) * 100) if total_phases > 0 else 0
        return min(100, max(0, percent))

    def _calculate_all_files_progress(self, current_bytes: float, total_bytes: float) -> int:
        """
        Berechnet Fortschritt aller Dateien in der aktuellen Phase.

        Args:
            current_bytes: Bereits verarbeitete Bytes (gesamt)
            total_bytes: Gesamtbytes des Tests

        Returns:
            Fortschritt in Prozent (0-100)
        """
        if not self.engine or not self.engine.session:
            return 0

        session = self.engine.session

        # Bytes pro Datei
        file_size_bytes = session.file_size_gb * 1024 * 1024 * 1024
        bytes_per_file = int(file_size_bytes)

        # Fortschritt in der aktuellen Phase
        bytes_per_phase = session.file_count * bytes_per_file
        current_file_bytes = session.current_file_index * bytes_per_file
        current_chunk_bytes = session.current_chunk_index * self.engine.CHUNK_SIZE
        phase_bytes = current_file_bytes + current_chunk_bytes

        percent = int((phase_bytes / bytes_per_phase) * 100) if bytes_per_phase > 0 else 0
        return min(100, max(0, percent))

    def _calculate_time_remaining(self, test_percent: int, speed_mbps: float) -> float:
        """
        Berechnet geschätzte Restzeit basierend auf Test-Fortschritt und aktueller Geschwindigkeit.

        Args:
            test_percent: Aktueller Test-Fortschritt (0-100)
            speed_mbps: Aktuelle Geschwindigkeit in MB/s

        Returns:
            Geschätzte Restzeit in Sekunden
        """
        if not self.engine or not self.engine.session or test_percent >= 100:
            return 0.0

        session = self.engine.session

        # Gesamtvolumen berechnen: Alle Dateien × Alle Muster × 2 Phasen
        total_patterns = len(session.selected_patterns) if session.selected_patterns else 5
        file_size_bytes = session.file_size_gb * 1024 * 1024 * 1024
        bytes_per_pattern = session.file_count * int(file_size_bytes) * 2  # Write + Verify

        total_test_bytes = total_patterns * bytes_per_pattern

        # Bereits verarbeitete Bytes basierend auf Test-Prozent
        processed_bytes = (test_percent / 100.0) * total_test_bytes

        # Verbleibende Bytes
        remaining_bytes = total_test_bytes - processed_bytes
        remaining_mb = remaining_bytes / (1024 * 1024)

        # Restzeit = Verbleibende MB / Geschwindigkeit
        remaining_seconds = remaining_mb / speed_mbps if speed_mbps > 0 else 0.0

        return max(0.0, remaining_seconds)

    def _format_time_remaining(self, seconds: float) -> str:
        """Formatiert Restzeit."""
        s = int(seconds)
        if s < 60:
            return f"{s}s"

        h = s // 3600
        m = (s % 3600) // 60

        if h > 0:
            return f"{h}h {m}m"
        else:
            return f"{m}m"
