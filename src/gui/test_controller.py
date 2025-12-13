"""
Test-Controller - Verbindet GUI mit Test-Engine

Koordiniert die Kommunikation zwischen MainWindow und TestEngine.
"""

import os
import shutil
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .main_window import MainWindow
from datetime import datetime

from PySide6.QtCore import QObject, Slot, QSettings
from PySide6.QtWidgets import QMessageBox

from core.test_engine import TestEngine, TestConfig, TestState
from core.session import SessionManager, SessionData
from core.file_manager import FileManager
from core.file_analyzer import FileAnalyzer
from core.patterns import PatternType
from .dialogs import (
    DriveSelectionDialog,
    SessionRestoreDialog,
    DeleteFilesDialog,
    StopConfirmationDialog,
    ErrorDetailDialog,
    FileRecoveryDialog,
    FileExpansionDialog
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

    def __init__(self, main_window: "MainWindow"):
        """
        Initialisiert den Controller

        Args:
            main_window: Referenz zum MainWindow
        """
        super().__init__()

        self.window: "MainWindow" = main_window
        self.engine: Optional[TestEngine] = None
        self.current_state = TestState.IDLE

        # QSettings für persistente Einstellungen
        self.settings = QSettings("DiskTest", "DiskTest")

        # Fehler-Liste für Detail-Dialog
        self.errors = []

        # Statistiken
        self.test_start_time = None

        # Signals verbinden
        self._connect_gui_signals()

        # Letzten Pfad laden und setzen
        self._load_last_path()

        # Session-Wiederherstellung beim Start prüfen
        self._check_for_existing_session()

        # Delete-Button Status aktualisieren
        self._update_delete_button()

    def _connect_gui_signals(self):
        """Verbindet GUI-Signals mit Controller-Slots"""
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
        """Lädt den zuletzt verwendeten Pfad aus QSettings"""
        last_path = self.settings.value("last_target_path", "")
        if last_path and os.path.exists(last_path):
            self.window.config_widget.path_edit.setText(last_path)

    def _save_last_path(self, path: str):
        """Speichert den verwendeten Pfad in QSettings"""
        if path and os.path.exists(path):
            self.settings.setValue("last_target_path", path)

    def _check_for_existing_session(self):
        """Prüft beim Start ob eine Session existiert und fragt User"""
        # Aktuellen Pfad aus Config nehmen (oder Default)
        config = self.window.config_widget.get_config()
        target_path = config.get('target_path', '')

        # Wenn kein Pfad vorhanden ist, zeige Laufwerks-Auswahl Dialog
        if not target_path or not os.path.exists(target_path):
            self._show_drive_selection_dialog()
            return

        # Session-Manager erstellen
        session_manager = SessionManager(target_path)

        if not session_manager.exists():
            # Keine Session, aber vielleicht verwaiste Testdateien?
            self._check_for_orphaned_files(target_path)
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
            'pattern_index': session_data.current_pattern_index,  # Backward compatibility
            'pattern_name': self._get_pattern_name_from_value(session_data.current_pattern_name),
            'error_count': len(session_data.errors)
        }

        dialog = SessionRestoreDialog(session_info, self.window)
        result = dialog.exec()

        if result == SessionRestoreDialog.RESULT_RESUME:
            # Prüfe auf fehlende Dateien (Lücken in Sequenz)
            self._check_for_missing_files(session_data)

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
        """Gibt den Namen eines Musters zurück (backward compatibility)"""
        from core.patterns import PATTERN_SEQUENCE
        if 0 <= pattern_index < len(PATTERN_SEQUENCE):
            return PATTERN_SEQUENCE[pattern_index].display_name
        return "--"

    def _get_pattern_name_from_value(self, pattern_value: str) -> str:
        """Gibt den Display-Namen eines Musters anhand seines Werts zurück"""
        try:
            pattern_type = PatternType(pattern_value)
            return pattern_type.display_name
        except (ValueError, AttributeError):
            return "--"

    def _show_drive_selection_dialog(self):
        """
        Zeigt Dialog zur Laufwerksauswahl beim Programmstart.

        Nach der Auswahl wird automatisch nach verwaisten Testdateien gesucht.
        """
        dialog = DriveSelectionDialog(self.window)
        result = dialog.exec()

        if result == DriveSelectionDialog.RESULT_SELECTED:
            selected_path = dialog.get_selected_path()

            if selected_path and os.path.exists(selected_path):
                # Setze Pfad in GUI
                self.window.config_widget.path_edit.setText(selected_path)

                # Speichere Pfad
                self._save_last_path(selected_path)

                # Prüfe auf Session oder verwaiste Dateien
                session_manager = SessionManager(selected_path)

                if session_manager.exists():
                    # Session gefunden - normale Session-Wiederherstellung
                    try:
                        session_data = session_manager.load()

                        session_info = {
                            'target_path': session_data.target_path,
                            'progress': int(session_data.get_progress_percentage()),
                            'pattern_index': session_data.current_pattern_index,  # Backward compatibility
                            'pattern_name': self._get_pattern_name_from_value(session_data.current_pattern_name),
                            'error_count': len(session_data.errors)
                        }

                        restore_dialog = SessionRestoreDialog(session_info, self.window)
                        restore_result = restore_dialog.exec()

                        if restore_result == SessionRestoreDialog.RESULT_RESUME:
                            # Prüfe auf fehlende Dateien
                            self._check_for_missing_files(session_data)
                            # Session fortsetzen
                            self._resume_session(session_data)
                        elif restore_result == SessionRestoreDialog.RESULT_NEW_TEST:
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
                    except Exception as e:
                        QMessageBox.warning(
                            self.window,
                            "Session-Fehler",
                            f"Fehler beim Laden der Session:\n{e}\n\nDie Session wird ignoriert."
                        )
                        # Prüfe trotzdem auf verwaiste Dateien
                        self._check_for_orphaned_files(selected_path)
                else:
                    # Keine Session - prüfe auf verwaiste Testdateien
                    self._check_for_orphaned_files(selected_path)

    def _fill_missing_files(self, analyzer: FileAnalyzer, results: List, file_size_gb: float) -> None:
        """
        Füllt fehlende Dateien (Lücken in der Sequenz) mit dem erkannten Muster

        Args:
            analyzer: FileAnalyzer Instanz
            results: Liste von FileAnalysisResult
            file_size_gb: Dateigröße in GB
        """
        from core.file_manager import FileManager
        from core.patterns import PatternGenerator

        if not results:
            return  # Keine Dateien vorhanden

        # Erstelle Set der vorhandenen Datei-Indizes (Engine-Index: 0-basiert)
        existing_indices = {r.file_index - 1 for r in results}

        # Finde fehlende Dateien (Lücken in der Sequenz)
        if not existing_indices:
            return

        min_index = min(existing_indices)
        max_index = max(existing_indices)
        missing_indices = set(range(min_index, max_index + 1)) - existing_indices

        if not missing_indices:
            return  # Keine Lücken

        # Erkenne Muster aus vorhandenen Dateien
        usable_files = [r for r in results if r.detected_pattern is not None]
        if not usable_files:
            self.window.log_widget.add_log(
                self._get_timestamp(),
                "WARNING",
                f"{len(missing_indices)} fehlende Datei(en) erkannt, aber kein Muster erkennbar - werden übersprungen"
            )
            return

        detected_pattern = usable_files[0].detected_pattern

        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"{len(missing_indices)} fehlende Datei(en) werden mit Muster {detected_pattern.display_name} gefüllt"
        )

        # Erstelle fehlende Dateien
        file_manager = FileManager(analyzer.target_path, file_size_gb)
        pattern_gen = PatternGenerator(detected_pattern)
        chunk_size = 16 * 1024 * 1024  # 16 MB
        target_size = int(file_size_gb * 1024 * 1024 * 1024)

        for engine_index in sorted(missing_indices):
            file_path = file_manager.get_file_path(engine_index)

            try:
                with open(file_path, 'wb') as f:
                    bytes_written = 0
                    while bytes_written < target_size:
                        chunk_bytes = min(chunk_size, target_size - bytes_written)
                        chunk = pattern_gen.generate_chunk(chunk_bytes)
                        f.write(chunk)
                        bytes_written += chunk_bytes

                self.window.log_widget.add_log(
                    self._get_timestamp(),
                    "INFO",
                    f"Lücke gefüllt: {file_path.name}"
                )
            except Exception as e:
                self.window.log_widget.add_log(
                    self._get_timestamp(),
                    "ERROR",
                    f"Fehler beim Füllen von {file_path.name}: {e}"
                )

    def _check_for_missing_files(self, session_data: SessionData) -> None:
        """
        Prüft auf fehlende Dateien (Lücken in der Sequenz) und füllt sie

        Args:
            session_data: Die Session-Daten
        """
        from core.file_analyzer import FileAnalyzer

        # Analyzer erstellen
        analyzer = FileAnalyzer(session_data.target_path, session_data.file_size_gb)
        results = analyzer.analyze_existing_files()

        if not results:
            return  # Keine Dateien vorhanden

        # Fülle Lücken
        self._fill_missing_files(analyzer, results, session_data.file_size_gb)

    def _resume_session(self, session_data: SessionData) -> None:
        """Stellt GUI-State aus Session wieder her"""
        # Pattern-Liste aus Session wiederherstellen
        from core.patterns import PATTERN_SEQUENCE
        if session_data.selected_patterns:
            # String-Liste zu PatternType-Liste konvertieren
            selected_patterns = [
                pt for pt in PATTERN_SEQUENCE
                if pt.value in session_data.selected_patterns
            ]
        else:
            # Fallback: Alle Patterns
            selected_patterns = list(PATTERN_SEQUENCE)

        # Config setzen
        config = {
            'target_path': session_data.target_path,
            'test_size_gb': session_data.total_size_gb,
            'file_size_mb': int(session_data.file_size_gb * 1024),
            'whole_drive': False,
            'selected_patterns': selected_patterns
        }
        self.window.config_widget.set_config(config)

        # Completed patterns im UI anzeigen
        completed = session_data.completed_patterns if hasattr(session_data, 'completed_patterns') else []
        self.window.config_widget.pattern_widget.set_completed_patterns(completed)

        # Progress setzen
        progress = int(session_data.get_progress_percentage())
        self.window.progress_widget.set_progress(progress)

        pattern_name = self._get_pattern_name_from_value(session_data.current_pattern_name)
        total_patterns = len(session_data.selected_patterns) if session_data.selected_patterns else 5
        # Berechne aktuellen Index (abgeschlossene + 1)
        completed_count = len(session_data.completed_patterns) if hasattr(session_data, 'completed_patterns') else 0
        current_pattern_num = completed_count + 1
        self.window.progress_widget.set_pattern(f"{current_pattern_num}/{total_patterns} ({pattern_name})")

        phase = "Schreiben" if session_data.current_phase == "write" else "Verifizieren"
        self.window.progress_widget.set_phase(phase)

        # Datei-Info setzen (0-basiert zu 1-basiert konvertieren)
        file_info = f"{session_data.current_file_index + 1}/{session_data.file_count}"
        self.window.progress_widget.set_file(file_info)

        # Fehler setzen
        self.errors = session_data.errors
        self.window.progress_widget.set_error_count(len(self.errors))

        # State setzen
        self.window.control_widget.set_state_paused()
        self.window.config_widget.set_enabled_for_resume()  # Nur bestimmte Felder aktivieren
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

        # Pattern-Info für Log
        total_patterns = len(session_data.selected_patterns) if session_data.selected_patterns else 5
        completed_count = len(session_data.completed_patterns) if hasattr(session_data, 'completed_patterns') else 0
        current_pattern_num = completed_count + 1

        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Fortschritt: {progress}% - Muster {current_pattern_num}/{total_patterns} ({pattern_name})"
        )

    def _check_for_orphaned_files(self, target_path: str):
        """
        Prüft auf verwaiste Testdateien ohne Session

        Args:
            target_path: Pfad zum Test-Verzeichnis
        """
        # Aktuelle Config für erwartete Dateigröße
        config = self.window.config_widget.get_config()
        file_size_mb = config.get('file_size_mb', 1000)
        file_size_gb = file_size_mb / 1024.0

        # Analyzer erstellen und Dateien analysieren
        analyzer = FileAnalyzer(target_path, file_size_gb)
        results = analyzer.analyze_existing_files()

        if not results:
            # Keine Testdateien gefunden
            return

        # Recovery-Info zusammenstellen - Neue kategorisierte Logik
        categorized = analyzer.categorize_files(results)
        complete_results = categorized['complete']
        smaller_consistent = categorized['smaller_consistent']
        corrupted_incomplete = categorized['corrupted_incomplete']

        total_size = sum(r.actual_size for r in results)
        total_size_gb = total_size / (1024 ** 3)

        # Muster schätzen
        pattern_estimate = analyzer.estimate_current_pattern(results)
        detected_pattern = pattern_estimate[0].display_name if pattern_estimate else None

        recovery_info = {
            'file_count': len(results),
            'complete_count': len(complete_results),
            'smaller_consistent_count': len(smaller_consistent),
            'corrupted_count': len(corrupted_incomplete),
            'expected_size_mb': file_size_mb,
            'detected_pattern': detected_pattern,
            'total_size_gb': total_size_gb,
            'last_complete_file': complete_results[-1].file_index if complete_results else None
        }

        # Dialog anzeigen
        dialog = FileRecoveryDialog(recovery_info, self.window)
        result = dialog.exec()

        if result == FileRecoveryDialog.RESULT_CONTINUE:
            # Rekonstruiere Session und fahre fort
            overwrite_corrupted = dialog.should_overwrite_corrupted()
            expand_smaller = dialog.should_expand_smaller_files()

            # Zu kleine Dateien vergrößern falls gewünscht
            if expand_smaller and smaller_consistent:
                success = self._expand_smaller_files(analyzer, smaller_consistent)
                if success:
                    # Neu analysieren nach Vergrößerung
                    results = analyzer.analyze_existing_files()

            # Fülle Lücken in der Datei-Sequenz
            self._fill_missing_files(analyzer, results, file_size_gb)

            # Neu analysieren nach Lückenfüllung
            results = analyzer.analyze_existing_files()

            self._reconstruct_session_from_files(
                results,
                file_size_gb,
                overwrite_corrupted
            )
        elif result == FileRecoveryDialog.RESULT_NEW_TEST:
            # User will neuen Test - Dateien bleiben, werden überschrieben
            pass

    def _expand_smaller_files(self, analyzer: FileAnalyzer, smaller_files: list) -> bool:
        """
        Vergrößert zu kleine Dateien auf Zielgröße

        Args:
            analyzer: FileAnalyzer Instanz
            smaller_files: Liste von FileAnalysisResult die vergrößert werden sollen

        Returns:
            True bei Erfolg
        """
        if not smaller_files:
            return True

        # Zeige Progress-Dialog
        try:
            expansion_dialog = FileExpansionDialog(analyzer, smaller_files, self.window)
            expansion_dialog.exec()

            success_count, error_count = expansion_dialog.get_results()

            if error_count > 0:
                self.window.log_widget.add_log(
                    self._get_timestamp(),
                    "WARNING",
                    f"{success_count} Dateien vergrößert, {error_count} Fehler"
                )
            else:
                self.window.log_widget.add_log(
                    self._get_timestamp(),
                    "SUCCESS",
                    f"{success_count} Dateien erfolgreich vergrößert"
                )

            return error_count == 0

        except Exception as e:
            self.window.log_widget.add_log(
                self._get_timestamp(),
                "ERROR",
                f"Fehler beim Vergrößern: {e}"
            )
            return False

    def _reconstruct_session_from_files(
        self,
        analysis_results: list,
        file_size_gb: float,
        overwrite_corrupted: bool
    ):
        """
        Rekonstruiert eine Session aus vorhandenen Dateien

        Args:
            analysis_results: Liste von FileAnalysisResult
            file_size_gb: Erwartete Dateigröße in GB
            overwrite_corrupted: Ob beschädigte Dateien überschrieben werden sollen
        """
        from core.patterns import PATTERN_SEQUENCE
        import random

        # Finde verwendbare Dateien (vollständig ODER konsistent mit erkanntem Muster)
        # Nach dem Vergrößern sind sie vollständig, vorher können sie zu klein aber konsistent sein
        # WICHTIG: FileAnalyzer gibt Indizes aus Dateinamen (1-basiert)
        # Konvertiere alle zu Engine-Indizes (0-basiert) durch -1
        usable_files = [
            r for r in analysis_results
            if r.detected_pattern is not None and r.actual_size > 0
        ]

        if not usable_files:
            QMessageBox.warning(
                self.window,
                "Keine verwendbaren Dateien",
                "Es wurden keine verwendbaren Testdateien gefunden.\n"
                "Starten Sie einen neuen Test."
            )
            return

        # Konvertiere file_index von 1-basiert zu 0-basiert
        last_usable = max(usable_files, key=lambda r: r.file_index)
        last_usable_index = last_usable.file_index - 1  # Engine-Index

        # Aktuelles Muster schätzen (Write-Phase)
        # Annahme: Alle verwendbaren Dateien haben gleiches Muster
        current_pattern_type = last_usable.detected_pattern
        if not current_pattern_type:
            QMessageBox.warning(
                self.window,
                "Muster nicht erkennbar",
                "Das Bitmuster konnte nicht erkannt werden.\n"
                "Starten Sie einen neuen Test."
            )
            return

        # Pattern-Name und Index für Session
        current_pattern_name = current_pattern_type.value
        try:
            current_pattern_index = PATTERN_SEQUENCE.index(current_pattern_type)  # Backward compatibility
        except ValueError:
            current_pattern_index = 0

        # Nächste Datei bestimmen
        # HINWEIS: Lücken wurden bereits in _fill_missing_files() gefüllt
        if overwrite_corrupted:
            # Finde erste beschädigte Datei NACH letzter verwendbarer (Engine-Index)
            corrupted_after = [
                r for r in analysis_results
                if not r.is_complete and (r.file_index - 1) > last_usable_index
            ]

            if corrupted_after:
                next_file_index = min(corrupted_after, key=lambda r: r.file_index).file_index - 1
            else:
                # Keine beschädigten Dateien nach letzter verwendbarer
                # Setze am Ende fort
                next_file_index = last_usable_index + 1
        else:
            # Finde erste beschädigte Datei (auch vor letzter verwendbarer)
            corrupted_all = [r for r in analysis_results if not r.is_complete]

            if corrupted_all:
                next_file_index = min(corrupted_all, key=lambda r: r.file_index).file_index - 1
            else:
                # Keine beschädigten Dateien
                # Setze am Ende fort
                next_file_index = last_usable_index + 1

        # Session-Daten erstellen
        config = self.window.config_widget.get_config()

        # Dateianzahl basierend auf aktueller Testgröße berechnen
        # (User kann beim Fortsetzen die Testgröße anpassen)
        target_file_count = int(config.get('test_size_gb', 50) / file_size_gb)

        # Falls bereits mehr Dateien vorhanden sind, behalte die höhere Anzahl
        total_file_count = max(len(analysis_results), target_file_count)

        # Random-Seed: Neu generieren
        random_seed = random.randint(0, 2**31 - 1)

        # Erstelle Session
        session_data = SessionData(
            target_path=config['target_path'],
            file_size_gb=file_size_gb,
            total_size_gb=config.get('test_size_gb', 50),
            file_count=total_file_count,
            current_pattern_index=current_pattern_index,  # Backward compatibility
            current_pattern_name=current_pattern_name,
            current_file_index=next_file_index,
            current_phase="write",
            current_chunk_index=0,  # Von vorne beginnen
            random_seed=random_seed,
            selected_patterns=[p.value for p in config.get('selected_patterns', PATTERN_SEQUENCE)],
            completed_patterns=[]  # Neue Session - keine abgeschlossenen Patterns
        )

        # Session speichern
        try:
            session_manager = SessionManager(config['target_path'])
            session_manager.save(session_data)
        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Fehler",
                f"Session konnte nicht gespeichert werden:\n{e}"
            )
            return

        # GUI-State wiederherstellen
        self._resume_session(session_data)

        # Log
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Session aus {len(usable_files)} verwendbaren Dateien rekonstruiert"
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
            self.window.enable_pattern_selection(True)  # Pattern-Auswahl bei Pause aktivieren
            self.current_state = TestState.PAUSED

            self.window.log_widget.add_log(
                self._get_timestamp(),
                "INFO",
                "Test pausiert"
            )

    @Slot()
    def on_stop_after_file_clicked(self):
        """Pause-nach-Datei Button wurde geklickt"""
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
            deleted_count, errors = file_manager.delete_test_files()
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

        # Speicherplatz prüfen
        try:
            disk_usage = shutil.disk_usage(config['target_path'])
            free_space_gb = disk_usage.free / (1024 ** 3)

            # Vorhandene Testdateien einrechnen
            from core.file_manager import FileManager
            file_size_gb = config['file_size_mb'] / 1024.0
            fm = FileManager(config['target_path'], file_size_gb)
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
        self._save_last_path(config['target_path'])

        # Log-Verzeichnis bestimmen
        log_dir = None
        if config.get('log_in_userdir', False):
            # Benutzerverzeichnis für Logs verwenden
            log_dir = self._get_user_log_dir()

        # Test-Config erstellen
        file_size_gb = config['file_size_mb'] / 1024.0

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
        """Verbindet Engine-Signals mit Controller-Slots"""
        self.engine.progress_updated.connect(self.on_progress_updated)
        self.engine.file_progress_updated.connect(self.on_file_progress_updated)
        self.engine.file_changed.connect(self.on_file_changed)
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

    @Slot(int)
    def on_file_progress_updated(self, percent: int):
        """Datei-Fortschritt Update von Engine"""
        self.window.progress_widget.set_file_progress(percent)

    @Slot(int, int)
    def on_file_changed(self, current_file_index: int, total_file_count: int):
        """Datei-Wechsel von Engine"""
        file_info = f"{current_file_index + 1}/{total_file_count}"
        self.window.progress_widget.set_file(file_info)

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
        # Hole Anzahl ausgewählter Patterns aus Engine-Session
        total_patterns = 5  # Default
        if self.engine and self.engine.session:
            total_patterns = len(self.engine.session.selected_patterns) if self.engine.session.selected_patterns else 5
        self.window.progress_widget.set_pattern(f"{pattern_index + 1}/{total_patterns} ({pattern_name})")

    @Slot(str)
    def on_phase_changed(self, phase: str):
        """Phasen-Wechsel von Engine"""
        self.window.progress_widget.set_phase(phase)

    @Slot()
    def on_pattern_selection_changed(self):
        """Pattern-Auswahl wurde geändert (während pausierter Session)"""
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

    def _reset_gui(self):
        """Setzt GUI in Idle-Zustand zurück"""
        self.window.control_widget.set_state_idle()
        self.window.config_widget.set_enabled(True)
        self.window.enable_pattern_selection(True)  # Pattern-Auswahl wieder aktivieren
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

    def _get_user_log_dir(self) -> str:
        """Gibt das Benutzerverzeichnis für Logs zurück"""
        # Benutze das Dokumente-Verzeichnis oder Home-Verzeichnis
        home = Path.home()
        log_dir = home / "DiskTest_Logs"
        # Verzeichnis erstellen falls nicht vorhanden
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir)

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
