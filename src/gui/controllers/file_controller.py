"""
File-Controller - Verwaltet Testdateien

Verantwortlich für:
- Orphaned Files Recovery
- Datei-Expansion
- Testdateien löschen
- Fehlende Dateien füllen (Lücken)
"""

import os
import random
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING, Callable
from datetime import datetime

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from core.file_manager import FileManager
from core.file_analyzer import FileAnalyzer, FileAnalysisResult
from core.patterns import PatternGenerator, PatternType, PATTERN_SEQUENCE
from core.session import SessionManager, SessionData
from core.platform import get_window_activator

if TYPE_CHECKING:
    from gui.main_window import MainWindow


class FileController(QObject):
    """
    Controller für Datei-Operationen.

    Verwaltet alle Operationen mit Testdateien:
    - Lücken füllen
    - Dateien vergrößern
    - Dateien löschen
    - Recovery aus verwaisten Dateien
    """

    def __init__(self, main_window: "MainWindow", get_timestamp: Callable[[], str]):
        """
        Initialisiert den File-Controller.

        Args:
            main_window: Referenz zum MainWindow
            get_timestamp: Funktion die aktuellen Timestamp zurückgibt
        """
        super().__init__()
        self.window = main_window
        self._get_timestamp = get_timestamp

    def fill_missing_files(
        self,
        analyzer: FileAnalyzer,
        results: List[FileAnalysisResult],
        file_size_gb: float
    ) -> None:
        """
        Füllt fehlende Dateien (Lücken in der Sequenz) mit dem erkannten Muster.

        Args:
            analyzer: FileAnalyzer Instanz
            results: Liste von FileAnalysisResult
            file_size_gb: Dateigröße in GB
        """
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
        file_manager = FileManager(analyzer.target_path, file_size_gb, session_data.file_count)
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

    def check_for_missing_files(self, session_data: SessionData) -> None:
        """
        Prüft auf fehlende Dateien (Lücken in der Sequenz) und füllt sie.

        Args:
            session_data: Die Session-Daten
        """
        # Analyzer erstellen
        analyzer = FileAnalyzer(session_data.target_path, session_data.file_size_gb)
        results = analyzer.analyze_existing_files()

        if not results:
            return  # Keine Dateien vorhanden

        # Fülle Lücken
        self.fill_missing_files(analyzer, results, session_data.file_size_gb)

    def expand_smaller_files(
        self,
        analyzer: FileAnalyzer,
        smaller_files: List[FileAnalysisResult]
    ) -> bool:
        """
        Vergrößert zu kleine Dateien auf Zielgröße.

        Args:
            analyzer: FileAnalyzer Instanz
            smaller_files: Liste von FileAnalysisResult die vergrößert werden sollen

        Returns:
            True bei Erfolg
        """
        from gui.dialogs import FileExpansionDialog

        if not smaller_files:
            return True

        # Zeige Progress-Dialog
        try:
            expansion_dialog = FileExpansionDialog(analyzer, smaller_files, self.window)
            activate_window = get_window_activator()
            activate_window(expansion_dialog)
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

    def reconstruct_session_from_files(
        self,
        analysis_results: List[FileAnalysisResult],
        file_size_gb: float,
        overwrite_corrupted: bool,
        requested_test_size_gb: Optional[float] = None
    ) -> Optional[SessionData]:
        """
        Rekonstruiert eine Session aus vorhandenen Dateien.

        Args:
            analysis_results: Liste von FileAnalysisResult
            file_size_gb: Erwartete Dateigröße in GB
            overwrite_corrupted: Ob beschädigte Dateien überschrieben werden sollen
            requested_test_size_gb: Vom User gewünschte Testgröße (falls None: aus GUI lesen)

        Returns:
            SessionData bei Erfolg, None bei Fehler
        """
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
            return None

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
            return None

        # Pattern-Name und Index für Session
        current_pattern_name = current_pattern_type.value
        try:
            current_pattern_index = PATTERN_SEQUENCE.index(current_pattern_type)  # Backward compatibility
        except ValueError:
            current_pattern_index = 0

        # Nächste Datei bestimmen
        # HINWEIS: Lücken wurden bereits in fill_missing_files() gefüllt
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

        # Testgröße: Verwende Parameter falls vorhanden, sonst aus GUI
        if requested_test_size_gb is None:
            requested_test_size_gb = config.get('test_size_gb', 50)

        # Dateianzahl basierend auf aktueller Testgröße berechnen
        # (User kann beim Fortsetzen die Testgröße anpassen)
        target_file_count = int(requested_test_size_gb / file_size_gb)

        # Falls bereits mehr Dateien vorhanden sind, behalte die höhere Anzahl
        total_file_count = max(len(analysis_results), target_file_count)

        # Random-Seed: Neu generieren
        random_seed = random.randint(0, 2**31 - 1)

        # File-Pattern-Mapping erstellen
        file_patterns = {}
        for result in analysis_results:
            if result.detected_pattern and result.is_complete:
                # Vollständige Datei - Pattern speichern
                file_idx = result.file_index - 1  # 0-basiert für Engine
                file_patterns[file_idx] = result.detected_pattern.value

        # Erstelle Session
        session_data = SessionData(
            target_path=config['target_path'],
            file_size_gb=file_size_gb,
            total_size_gb=requested_test_size_gb,
            file_count=total_file_count,
            current_pattern_index=current_pattern_index,  # Backward compatibility
            current_pattern_name=current_pattern_name,
            current_file_index=next_file_index,
            current_phase="write",
            current_chunk_index=0,  # Von vorne beginnen
            random_seed=random_seed,
            selected_patterns=[p.value for p in config.get('selected_patterns', PATTERN_SEQUENCE)],
            completed_patterns=[],  # Neue Session - keine abgeschlossenen Patterns
            file_patterns=file_patterns  # Pattern-Mapping für vorhandene Dateien
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
            return None

        # Log
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Session aus {len(usable_files)} verwendbaren Dateien rekonstruiert"
        )

        return session_data

    def check_for_orphaned_files(self, target_path: str) -> Optional[SessionData]:
        """
        Prüft auf verwaiste Testdateien ohne Session.

        Args:
            target_path: Pfad zum Test-Verzeichnis

        Returns:
            SessionData wenn rekonstruiert, None sonst
        """
        from gui.dialogs import FileRecoveryDialog

        # Aktuelle Config für erwartete Dateigröße
        config = self.window.config_widget.get_config()
        file_size_mb = config.get('file_size_mb', 1000)
        file_size_gb = file_size_mb / 1024.0

        # Analyzer erstellen und Dateien analysieren
        analyzer = FileAnalyzer(target_path, file_size_gb)
        results = analyzer.analyze_existing_files()

        if not results:
            # Keine Testdateien gefunden
            return None

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
        activate_window = get_window_activator()
        activate_window(dialog)
        result = dialog.exec()

        if result == FileRecoveryDialog.RESULT_CONTINUE:
            # Rekonstruiere Session und fahre fort
            overwrite_corrupted = dialog.should_overwrite_corrupted()
            expand_smaller = dialog.should_expand_smaller_files()

            # Zu kleine Dateien vergrößern falls gewünscht
            if expand_smaller and smaller_consistent:
                success = self.expand_smaller_files(analyzer, smaller_consistent)
                if success:
                    # Neu analysieren nach Vergrößerung
                    results = analyzer.analyze_existing_files()

            # Fülle Lücken in der Datei-Sequenz
            self.fill_missing_files(analyzer, results, file_size_gb)

            # Neu analysieren nach Lückenfüllung
            results = analyzer.analyze_existing_files()

            session_data = self.reconstruct_session_from_files(
                results,
                file_size_gb,
                overwrite_corrupted,
                requested_test_size_gb=None  # Aus GUI lesen
            )
            return session_data

        elif result == FileRecoveryDialog.RESULT_NEW_TEST:
            # User will neuen Test - Dateien bleiben, werden überschrieben
            return None

        return None

    def handle_orphaned_files_interactive(
        self,
        target_path: str,
        file_size_gb: float,
        requested_test_size_gb: float
    ) -> str:
        """
        Zeigt File Recovery Dialog für vorhandene Testdateien.

        Args:
            target_path: Zielpfad
            file_size_gb: Dateigröße in GB
            requested_test_size_gb: Vom User gewünschte Testgröße

        Returns:
            "reconstructed" - Session erstellt, GUI auf PAUSED
            "new_test" - User will neuen Test (Dateien überschreiben)
            "cancel" - User hat abgebrochen
        """
        from gui.dialogs import FileRecoveryDialog

        # Dateien analysieren
        analyzer = FileAnalyzer(target_path, file_size_gb)
        results = analyzer.analyze_existing_files()

        if not results:
            return "new_test"

        # Recovery-Info zusammenstellen
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
            'expected_size_mb': file_size_gb * 1024,
            'detected_pattern': detected_pattern,
            'total_size_gb': total_size_gb,
            'last_complete_file': complete_results[-1].file_index if complete_results else None
        }

        # Dialog anzeigen
        dialog = FileRecoveryDialog(recovery_info, self.window)
        activate_window = get_window_activator()
        activate_window(dialog)
        result = dialog.exec()

        if result == FileRecoveryDialog.RESULT_CONTINUE:
            # Rekonstruiere Session und fahre fort
            overwrite_corrupted = dialog.should_overwrite_corrupted()
            expand_smaller = dialog.should_expand_smaller_files()

            # Zu kleine Dateien vergrößern falls gewünscht
            if expand_smaller and smaller_consistent:
                success = self.expand_smaller_files(analyzer, smaller_consistent)
                if success:
                    # Neu analysieren nach Vergrößerung
                    results = analyzer.analyze_existing_files()

            # Fülle Lücken in der Datei-Sequenz
            self.fill_missing_files(analyzer, results, file_size_gb)

            # Neu analysieren nach Lückenfüllung
            results = analyzer.analyze_existing_files()

            # Session rekonstruieren mit requested_test_size_gb
            session_data = self.reconstruct_session_from_files(
                results,
                file_size_gb,
                overwrite_corrupted,
                requested_test_size_gb
            )

            if session_data:
                return "reconstructed"
            else:
                return "cancel"

        elif result == FileRecoveryDialog.RESULT_NEW_TEST:
            # User will neuen Test - Dateien bleiben, werden überschrieben
            return "new_test"
        else:
            # Abgebrochen
            return "cancel"

    def delete_test_files(self, target_path: str) -> tuple:
        """
        Löscht Testdateien im angegebenen Pfad.

        Args:
            target_path: Zielpfad

        Returns:
            Tuple (deleted_count, error_count)
        """
        from gui.dialogs import DeleteFilesDialog

        if not target_path or not os.path.exists(target_path):
            QMessageBox.warning(
                self.window,
                "Fehler",
                "Bitte wählen Sie zuerst einen gültigen Zielpfad."
            )
            return (0, 0)

        # Testdateien zählen und Größe ermitteln
        file_manager = FileManager(target_path, 1.0)  # Größe egal
        file_count = file_manager.count_existing_files()

        if file_count == 0:
            QMessageBox.information(
                self.window,
                "Keine Dateien",
                "Es wurden keine Testdateien gefunden."
            )
            return (0, 0)

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
        activate_window = get_window_activator()
        activate_window(dialog)

        if dialog.exec() != DeleteFilesDialog.DialogCode.Accepted:
            return (0, 0)

        # Dateien löschen
        try:
            deleted_count, errors = file_manager.delete_test_files()
        except Exception as e:
            self.window.log_widget.add_log(
                self._get_timestamp(),
                "ERROR",
                f"Fehler beim Löschen: {e}"
            )
            return (0, 1)

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

        return (deleted_count, errors)
