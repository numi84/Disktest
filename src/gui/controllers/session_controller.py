"""
Session-Controller - Verwaltet Test-Sessions

Verantwortlich für:
- Session-Wiederherstellung beim Start
- Multi-Session-Scanning
- Session-Dialoge anzeigen
- Session-Resume Logik
"""

import os
import time
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING, Callable
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from core.session import SessionManager, SessionData
from core.patterns import PatternType, PATTERN_SEQUENCE
from core.file_analyzer import FileAnalyzer
from core.platform import get_window_activator

if TYPE_CHECKING:
    from gui.main_window import MainWindow
    from .settings_controller import SettingsController
    from .file_controller import FileController


@dataclass
class SessionInfo:
    """Informationen über eine gefundene Session oder verwaiste Testdateien."""
    path: str
    type: str  # "session" oder "orphaned"

    # Für type="session"
    progress: Optional[float] = None
    pattern_index: Optional[int] = None
    pattern_name: Optional[str] = None
    error_count: Optional[int] = None
    file_count: Optional[int] = None

    # Für type="orphaned"
    detected_pattern: Optional[str] = None
    orphaned_file_count: Optional[int] = None
    total_size_gb: Optional[float] = None

    # Metadata
    last_modified: Optional[str] = None


class SessionController(QObject):
    """
    Controller für Session-Management.

    Verwaltet Session-Scanning, -Wiederherstellung und -Dialoge.
    """

    def __init__(
        self,
        main_window: "MainWindow",
        settings_controller: "SettingsController",
        file_controller: "FileController",
        get_timestamp: Callable[[], str]
    ):
        """
        Initialisiert den Session-Controller.

        Args:
            main_window: Referenz zum MainWindow
            settings_controller: Referenz zum SettingsController
            file_controller: Referenz zum FileController
            get_timestamp: Funktion die aktuellen Timestamp zurückgibt
        """
        super().__init__()
        self.window = main_window
        self.settings = settings_controller
        self.file_controller = file_controller
        self._get_timestamp = get_timestamp

    def check_for_existing_session(self) -> None:
        """Prüft beim Start ob eine oder mehrere Sessions existieren und fragt User."""
        from gui.dialogs import DriveSelectionDialog, MultiSessionSelectionDialog

        # Multi-Session-Scan aktiviert?
        scan_enabled = self.settings.is_session_scan_enabled()

        all_sessions: List[SessionInfo] = []

        if scan_enabled:
            # 1. Schneller Scan: Recent Sessions
            recent_sessions = self._scan_recent_sessions()
            all_sessions.extend(recent_sessions)

            # 2. Full-Scan aller Laufwerke (immer durchführen um neue Sessions zu finden)
            full_scan_sessions = self._scan_all_drives_for_sessions()
            # Deduplizieren (falls Pfade doppelt vorkommen)
            existing_paths = {s.path for s in all_sessions}
            for session in full_scan_sessions:
                if session.path not in existing_paths:
                    all_sessions.append(session)
        else:
            # Fallback: Nur aktuellen Pfad prüfen (altes Verhalten)
            config = self.window.config_widget.get_config()
            target_path = config.get('target_path', '')

            if target_path and os.path.exists(target_path):
                session_info = self._check_path_for_session(target_path)
                if session_info:
                    all_sessions.append(session_info)

        # Verhalten abhängig von Anzahl gefundener Sessions
        if len(all_sessions) == 0:
            # Keine Sessions gefunden - zeige Drive Selection Dialog
            self._show_drive_selection_dialog()

        elif len(all_sessions) == 1:
            # Genau eine Session - zeige bisherigen Session Restore Dialog
            session_info_obj = all_sessions[0]
            self._handle_single_session(session_info_obj)

        else:
            # Mehrere Sessions - zeige Multi-Session-Auswahl-Dialog
            self._show_multi_session_dialog(all_sessions)

    def _check_path_for_session(self, path: str) -> Optional[SessionInfo]:
        """
        Prüft einzelnen Pfad auf Session oder Testdateien.

        Args:
            path: Zu prüfender Pfad

        Returns:
            SessionInfo wenn Session oder Testdateien gefunden, sonst None
        """
        if not os.path.exists(path):
            return None

        session_manager = SessionManager(path)

        # 1. Session-Datei vorhanden?
        if session_manager.exists():
            try:
                session_data = session_manager.load()

                # Letzte Änderungszeit
                session_file = Path(path) / SessionManager.SESSION_FILENAME
                try:
                    mtime = session_file.stat().st_mtime
                    last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    last_modified = None

                return SessionInfo(
                    path=path,
                    type="session",
                    progress=session_data.get_progress_percentage(),
                    pattern_index=session_data.current_pattern_index,
                    pattern_name=self._get_pattern_name_from_value(session_data.current_pattern_name),
                    error_count=len(session_data.errors),
                    file_count=session_data.file_count,
                    last_modified=last_modified
                )
            except Exception:
                # Session-Datei korrupt - ignorieren
                pass

        # 2. Orphaned Files vorhanden?
        test_files = list(Path(path).glob("disktest_*.dat"))
        if test_files:
            # Nutze aktuelle Config für erwartete Dateigröße
            config = self.window.config_widget.get_config()
            file_size_gb = config.get('file_size_mb', 1000) / 1024.0

            analyzer = FileAnalyzer(path, file_size_gb)
            results = analyzer.analyze_existing_files()

            if results:
                total_size = sum(r.actual_size for r in results)
                total_size_gb = total_size / (1024 ** 3)

                # Pattern schätzen
                pattern_estimate = analyzer.estimate_current_pattern(results)
                detected_pattern = pattern_estimate[0].display_name if pattern_estimate else None

                # Letzte Änderungszeit der neuesten Datei
                try:
                    newest_file = max(test_files, key=lambda f: f.stat().st_mtime)
                    mtime = newest_file.stat().st_mtime
                    last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    last_modified = None

                return SessionInfo(
                    path=path,
                    type="orphaned",
                    orphaned_file_count=len(test_files),
                    detected_pattern=detected_pattern,
                    total_size_gb=total_size_gb,
                    last_modified=last_modified
                )

        return None

    def _scan_all_drives_for_sessions(self) -> List[SessionInfo]:
        """
        Scannt alle Laufwerke nach Sessions und Testdateien.

        Returns:
            Liste von SessionInfo-Objekten
        """
        sessions: List[SessionInfo] = []
        scan_depth = self.settings.get_session_scan_depth()
        timeout_ms = self.settings.get_session_scan_timeout_ms()

        start_time = time.time()

        # Windows: A-Z scannen
        for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = f"{drive_letter}:\\"

            # Timeout-Check
            if (time.time() - start_time) * 1000 > timeout_ms:
                self.window.log_widget.add_log(
                    self._get_timestamp(),
                    "WARNING",
                    f"Session-Scan nach {timeout_ms}ms abgebrochen"
                )
                break

            if not os.path.exists(drive_path):
                continue

            # 1. Session direkt im Root prüfen
            session_info = self._check_path_for_session(drive_path)
            if session_info:
                sessions.append(session_info)

            # 2. Eine Ordner-Ebene tiefer scannen (falls konfiguriert)
            if scan_depth in ["one_level", "two_levels"]:
                try:
                    for entry in os.scandir(drive_path):
                        # Timeout-Check
                        if (time.time() - start_time) * 1000 > timeout_ms:
                            break

                        if entry.is_dir():
                            subpath = entry.path
                            session_info = self._check_path_for_session(subpath)
                            if session_info:
                                sessions.append(session_info)

                            # 3. Zwei Ebenen tiefer (falls konfiguriert)
                            if scan_depth == "two_levels":
                                try:
                                    for subentry in os.scandir(subpath):
                                        if (time.time() - start_time) * 1000 > timeout_ms:
                                            break

                                        if subentry.is_dir():
                                            subsubpath = subentry.path
                                            session_info = self._check_path_for_session(subsubpath)
                                            if session_info:
                                                sessions.append(session_info)
                                except (PermissionError, OSError):
                                    pass
                except (PermissionError, OSError):
                    # Laufwerk nicht zugreifbar - überspringen
                    pass

        return sessions

    def _scan_recent_sessions(self) -> List[SessionInfo]:
        """
        Scannt nur die zuletzt verwendeten Pfade nach Sessions.

        Returns:
            Liste von SessionInfo-Objekten
        """
        sessions: List[SessionInfo] = []
        recent_paths = self.settings.get_recent_session_paths()

        for path in recent_paths:
            session_info = self._check_path_for_session(path)
            if session_info:
                sessions.append(session_info)

        return sessions

    def _handle_single_session(self, session_info_obj: SessionInfo) -> None:
        """
        Behandelt eine einzelne gefundene Session.

        Args:
            session_info_obj: SessionInfo-Objekt
        """
        from gui.dialogs import SessionRestoreDialog

        if session_info_obj.type == "session":
            # Normale Session - lade SessionData
            try:
                session_manager = SessionManager(session_info_obj.path)
                session_data = session_manager.load()

                # Setze Pfad in GUI
                self.window.config_widget.path_edit.setText(session_info_obj.path)

                # Zeige Session Restore Dialog
                session_info_dict = {
                    'target_path': session_data.target_path,
                    'progress': int(session_data.get_progress_percentage()),
                    'pattern_index': session_data.current_pattern_index,
                    'pattern_name': self._get_pattern_name_from_value(session_data.current_pattern_name),
                    'error_count': len(session_data.errors)
                }

                dialog = SessionRestoreDialog(session_info_dict, self.window)
                activate_window = get_window_activator()
                activate_window(dialog)
                result = dialog.exec()

                if result == SessionRestoreDialog.RESULT_RESUME:
                    # Prüfe auf fehlende Dateien
                    self.file_controller.check_for_missing_files(session_data)
                    # Session fortsetzen
                    self.resume_session(session_data)
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

            except Exception as e:
                QMessageBox.warning(
                    self.window,
                    "Session-Fehler",
                    f"Fehler beim Laden der Session:\n{e}\n\nDie Session wird ignoriert."
                )

        elif session_info_obj.type == "orphaned":
            # Orphaned Files - zeige Recovery Dialog
            self.window.config_widget.path_edit.setText(session_info_obj.path)
            self.file_controller.check_for_orphaned_files(session_info_obj.path)

    def _show_multi_session_dialog(self, sessions: List[SessionInfo]) -> None:
        """
        Zeigt Multi-Session-Auswahl-Dialog.

        Args:
            sessions: Liste von SessionInfo-Objekten
        """
        from gui.dialogs import MultiSessionSelectionDialog

        dialog = MultiSessionSelectionDialog(sessions, self.window)
        activate_window = get_window_activator()
        activate_window(dialog)
        result = dialog.exec()

        if result == MultiSessionSelectionDialog.RESULT_SESSION_SELECTED:
            # Session wurde ausgewählt
            selected_session = dialog.get_selected_session()
            if selected_session:
                # Speichere als Recent Session
                self.settings.add_recent_session(selected_session.path)
                # Behandle wie einzelne Session
                self._handle_single_session(selected_session)

        elif result == MultiSessionSelectionDialog.RESULT_NEW_DRIVE:
            # User will neues Laufwerk wählen
            self._show_drive_selection_dialog()

    def _show_drive_selection_dialog(self) -> None:
        """
        Zeigt Dialog zur Laufwerksauswahl beim Programmstart.

        Nach der Auswahl wird automatisch nach verwaisten Testdateien gesucht.
        """
        from gui.dialogs import DriveSelectionDialog, SessionRestoreDialog

        dialog = DriveSelectionDialog(self.window)
        activate_window = get_window_activator()
        activate_window(dialog)
        result = dialog.exec()

        if result == DriveSelectionDialog.RESULT_SELECTED:
            selected_path = dialog.get_selected_path()

            if selected_path and os.path.exists(selected_path):
                # Setze Pfad in GUI
                self.window.config_widget.path_edit.setText(selected_path)

                # Speichere Pfad
                self.settings.save_last_path(selected_path)

                # Prüfe auf Session oder verwaiste Dateien
                session_manager = SessionManager(selected_path)

                if session_manager.exists():
                    # Session gefunden - normale Session-Wiederherstellung
                    try:
                        session_data = session_manager.load()

                        session_info = {
                            'target_path': session_data.target_path,
                            'progress': int(session_data.get_progress_percentage()),
                            'pattern_index': session_data.current_pattern_index,
                            'pattern_name': self._get_pattern_name_from_value(session_data.current_pattern_name),
                            'error_count': len(session_data.errors)
                        }

                        restore_dialog = SessionRestoreDialog(session_info, self.window)
                        activate_window = get_window_activator()
                        activate_window(restore_dialog)
                        restore_result = restore_dialog.exec()

                        if restore_result == SessionRestoreDialog.RESULT_RESUME:
                            # Prüfe auf fehlende Dateien
                            self.file_controller.check_for_missing_files(session_data)
                            # Session fortsetzen
                            self.resume_session(session_data)
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
                        self.file_controller.check_for_orphaned_files(selected_path)
                else:
                    # Keine Session - prüfe auf verwaiste Testdateien
                    self.file_controller.check_for_orphaned_files(selected_path)

    def resume_session(self, session_data: SessionData) -> None:
        """
        Stellt GUI-State aus Session wieder her.

        Args:
            session_data: Die Session-Daten
        """
        # Pattern-Liste aus Session wiederherstellen
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

        # Fehler setzen (wird vom TestController übernommen)
        # self.window.progress_widget.set_error_count(len(session_data.errors))

        # State setzen
        self.window.control_widget.set_state_paused()
        self.window.config_widget.set_enabled_for_resume()  # Nur bestimmte Felder aktivieren

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

    def _get_pattern_name_from_value(self, pattern_value: str) -> str:
        """
        Gibt den Display-Namen eines Musters anhand seines Werts zurück.

        Args:
            pattern_value: Pattern-Wert (z.B. "0x00")

        Returns:
            Display-Name des Patterns
        """
        try:
            pattern_type = PatternType(pattern_value)
            return pattern_type.display_name
        except (ValueError, AttributeError):
            return "--"
