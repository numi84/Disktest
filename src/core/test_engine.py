"""
Test-Engine für DiskTest
Führt die Festplattentests durch - Herzstück der Anwendung
"""
import errno
import os
import time
import threading
from enum import Enum, auto
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, IO

from PySide6.QtCore import QThread, Signal

from .patterns import PatternType, PatternGenerator, PATTERN_SEQUENCE
from .file_manager import FileManager
from .session import SessionData, SessionManager
from .platform import get_platform_io
from utils.logger import DiskTestLogger
from utils.disk_info import DiskInfo


class TestState(Enum):
    """Status der Test-Engine"""
    IDLE = auto()       # Bereit, nicht aktiv
    RUNNING = auto()    # Test läuft
    PAUSED = auto()     # Test pausiert
    STOPPING = auto()   # Test wird gestoppt
    COMPLETED = auto()  # Test abgeschlossen
    ERROR = auto()      # Fehler aufgetreten


@dataclass
class TestConfig:
    """Konfiguration für einen Test-Durchlauf"""
    target_path: str        # Zielpfad für Testdateien
    file_size_gb: float     # Größe einer Testdatei in GB
    total_size_gb: float    # Gesamtgröße des Tests in GB

    # Optional: Session wiederherstellen
    resume_session: bool = False
    session_data: Optional[SessionData] = None

    # Optional: Ausgewählte Patterns (None = alle)
    selected_patterns: Optional[list] = None

    # Optional: Log-Verzeichnis (None = target_path)
    log_dir: Optional[str] = None


class TestEngine(QThread):
    """
    Test-Engine als QThread

    Führt Festplattentests durch: Schreibt Testdateien mit verschiedenen
    Bitmustern und verifiziert diese durch Zurücklesen.

    Signals:
        progress_updated: (current_bytes: float, total_bytes: float, speed_mbps: float)
        status_changed: (status_message)
        log_entry: (log_message)
        error_occurred: (error_dict)
        test_completed: (summary_dict)
        pattern_changed: (pattern_index, pattern_name)
        phase_changed: (phase_name)  # "write" oder "verify"
    """

    # Qt Signals
    progress_updated = Signal(float, float, float)  # current_bytes, total_bytes, speed_mbps
    file_progress_updated = Signal(int)  # file_progress_percent (0-100)
    file_changed = Signal(int, int)  # current_file_index, total_file_count
    status_changed = Signal(str)
    log_entry = Signal(str)
    error_occurred = Signal(dict)
    test_completed = Signal(dict)
    pattern_changed = Signal(int, str)  # index, name
    phase_changed = Signal(str)  # "write" oder "verify"

    # Konstanten
    CHUNK_SIZE = 32 * 1024 * 1024  # 32 MB - Größere Chunks = weniger System-Calls
    IO_BUFFER_SIZE = 64 * 1024 * 1024  # 64 MB - Großer Buffer für bessere Performance
    PROGRESS_UPDATE_INTERVAL = 4  # Emit Progress nur alle N Chunks (reduziert GUI-Overhead)
    IO_TIMEOUT_WARNING_SECONDS = 30  # Warnung wenn Chunk länger als 30s dauert

    def __init__(self, config: TestConfig):
        """
        Initialisiert die Test-Engine

        Args:
            config: Test-Konfiguration
        """
        super().__init__()

        self.config = config
        self.state = TestState.IDLE

        # Thread-sichere Control Events
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._stop_after_file_event = threading.Event()

        # Komponenten
        # FileManager: Berechne file_count für richtige Stellenzahl
        file_count = int(config.total_size_gb / config.file_size_gb)
        file_count = max(1, file_count)  # Mindestens 1 Datei
        self.file_manager = FileManager(config.target_path, config.file_size_gb, file_count)
        self.session_manager = SessionManager(config.target_path)
        # Logger: Nutze log_dir wenn angegeben, sonst target_path
        log_dir = config.log_dir if config.log_dir else config.target_path
        self.logger = DiskTestLogger(log_dir)

        # Session-Daten
        self.session: Optional[SessionData] = None
        self.random_seed: Optional[int] = None

        # Resume-Tracking: Speichert den initialen Resume-Punkt
        # Wird nur bei Resume gesetzt, sonst -1/None
        self._initial_resume_pattern = -1
        self._initial_resume_phase: Optional[str] = None
        self._initial_resume_file = 0

        # Pattern-Auswahl (Default: alle)
        self.selected_patterns = config.selected_patterns if config.selected_patterns else PATTERN_SEQUENCE

        # Statistiken
        self.start_time = 0.0
        self.bytes_processed = 0
        self.total_bytes = 0
        self.error_count = 0

        # Geschwindigkeits-Berechnung
        self._speed_samples = []
        self._speed_window = 10  # Letzte N Chunks für Durchschnitt

        # Platform I/O fuer plattform-spezifische Operationen
        self.platform_io = get_platform_io(self.IO_BUFFER_SIZE)

    def run(self):
        """Hauptmethode - wird in separatem Thread ausgeführt"""
        try:
            self.state = TestState.RUNNING
            self.start_time = time.time()

            self.log_entry.emit("Test-Engine gestartet")
            self.logger.section("DiskTest gestartet")

            # Session initialisieren oder wiederherstellen
            if self.config.resume_session and self.config.session_data:
                self._resume_from_session()
            else:
                self._start_new_session()

            # Hauptschleife: Ausgewählte Muster durchlaufen
            total_patterns = len(self.selected_patterns)
            for pattern_idx, pattern_type in enumerate(self.selected_patterns):
                # Skip wenn Resume und bereits abgeschlossen
                if pattern_type.value in self.session.completed_patterns:
                    self.logger.info(f"Überspringe Muster {pattern_type.display_name} (bereits abgeschlossen)")
                    continue

                self.session.current_pattern_name = pattern_type.value
                self.session.current_pattern_index = pattern_idx  # Backward compatibility
                self.pattern_changed.emit(pattern_idx, pattern_type.display_name)

                self.logger.separator()
                self.logger.info(f"Starte Muster {pattern_idx + 1}/{total_patterns}: {pattern_type.display_name}")
                self.log_entry.emit(f"Muster {pattern_idx + 1}/{total_patterns}: {pattern_type.display_name}")

                # Pattern-Generator erstellen
                if pattern_type == PatternType.RANDOM:
                    gen = PatternGenerator(pattern_type, seed=self.session.random_seed)
                else:
                    gen = PatternGenerator(pattern_type)

                # Schreib-Phase
                success = self._write_pattern(gen, pattern_type)
                if not success:
                    break

                # Verifikations-Phase
                gen.reset()  # Wichtig für Random!
                success = self._verify_pattern(gen, pattern_type)
                if not success:
                    break

                # Pattern abgeschlossen - zu completed_patterns hinzufügen
                if pattern_type.value not in self.session.completed_patterns:
                    self.session.completed_patterns.append(pattern_type.value)

            # Test abgeschlossen
            if self.state == TestState.RUNNING:
                self._complete_test()

        except Exception as e:
            self._handle_error(f"Kritischer Fehler: {e}")
            self.logger.error(f"Kritischer Fehler: {e}")

        finally:
            self.state = TestState.IDLE

    def _start_new_session(self):
        """Startet eine neue Test-Session"""
        # Dateianzahl berechnen
        file_count = self.file_manager.calculate_file_count(self.config.total_size_gb)

        # Random-Seed generieren
        import random
        self.random_seed = random.randint(0, 2**31 - 1)

        # Session erstellen
        self.session = SessionData(
            target_path=self.config.target_path,
            file_size_gb=self.config.file_size_gb,
            total_size_gb=self.config.total_size_gb,
            file_count=file_count,
            current_pattern_index=0,  # Backward compatibility
            current_pattern_name=self.selected_patterns[0].value if self.selected_patterns else "00",
            current_file_index=0,
            current_phase="write",
            current_chunk_index=0,
            random_seed=self.random_seed,
            selected_patterns=[p.value for p in self.selected_patterns],
            completed_patterns=[]
        )

        # Total bytes berechnen
        self.total_bytes = int(file_count * self.config.file_size_gb * 1024 * 1024 * 1024)

        # Logging
        self.logger.info(f"Zielpfad: {self.config.target_path}")
        self.logger.info(f"Dateigröße: {self.config.file_size_gb} GB")
        self.logger.info(f"Anzahl Dateien: {file_count}")
        self.logger.info(f"Gesamtgröße: {self.config.total_size_gb} GB")
        self.logger.info(f"Random-Seed: {self.random_seed}")

    def _resume_from_session(self):
        """Setzt Test von gespeicherter Session fort"""
        self.session = self.config.session_data
        self.random_seed = self.session.random_seed

        # Speichere initialen Resume-Punkt für Skip-Logik
        self._initial_resume_pattern = self.session.current_pattern_name
        self._initial_resume_phase = self.session.current_phase
        self._initial_resume_file = self.session.current_file_index

        # Pattern-Auswahl: Priorisiere Config über Session (erlaubt Änderungen beim Resume)
        if self.config.selected_patterns:
            # User hat beim Resume neue Patterns ausgewählt - nutze diese
            self.selected_patterns = self.config.selected_patterns
            # Aktualisiere Session mit neuen Patterns
            self.session.selected_patterns = [p.value for p in self.selected_patterns]
        elif self.session.selected_patterns:
            # Keine neuen Patterns in Config - nutze Patterns aus Session
            from .patterns import PatternType
            self.selected_patterns = [
                PatternType(p) for p in self.session.selected_patterns
            ]

        # Total bytes berechnen
        self.total_bytes = int(
            self.session.file_count *
            self.session.file_size_gb *
            1024 * 1024 * 1024
        )

        # Bereits verarbeitete Bytes berechnen
        self.bytes_processed = self._calculate_processed_bytes()

        self.logger.info("Session wiederhergestellt")
        self.logger.info(f"Fortschritt: {self.session.get_progress_percentage():.1f}%")
        self.log_entry.emit(f"Session fortgesetzt bei {self.session.get_progress_percentage():.1f}%")

        # Validiere Pattern-Generator Konsistenz
        self._validate_pattern_generator()

    def _validate_pattern_generator(self):
        """
        Validiert dass der Pattern-Generator mit dem gespeicherten Seed
        die korrekten Daten erzeugt.

        Prüft die erste vorhandene Testdatei gegen das erwartete Pattern.
        Bei Random-Pattern wird der Seed validiert.
        """
        SAMPLE_SIZE = 4096  # 4 KB Sample reicht für Validierung

        try:
            # Finde erste vorhandene Testdatei
            first_file = self.file_manager.get_file_path(0)
            if not first_file.exists():
                self.logger.warning("Keine Testdateien fuer Validierung gefunden")
                return

            # Lese erstes Sample
            with open(first_file, 'rb') as f:
                actual_sample = f.read(SAMPLE_SIZE)

            if len(actual_sample) < SAMPLE_SIZE:
                self.logger.warning(f"Testdatei zu klein fuer Validierung: {len(actual_sample)} Bytes")
                return

            # Ermittle aktuelles Pattern aus Session
            try:
                current_pattern = PatternType(self.session.current_pattern_name)
            except ValueError:
                self.logger.warning(f"Unbekanntes Pattern: {self.session.current_pattern_name}")
                return

            # Generiere erwartetes Pattern
            if current_pattern == PatternType.RANDOM:
                gen = PatternGenerator(current_pattern, seed=self.random_seed)
            else:
                gen = PatternGenerator(current_pattern)

            expected_sample = gen.generate_chunk(SAMPLE_SIZE)

            # Vergleiche
            if actual_sample == expected_sample:
                self.logger.info("Pattern-Generator Validierung erfolgreich")
            else:
                # Bei Nicht-Random Patterns könnte das Pattern geändert worden sein
                # Versuche alle Patterns zu erkennen
                detected = self._detect_sample_pattern(actual_sample)
                if detected:
                    self.logger.warning(
                        f"Pattern-Mismatch: Session erwartet {current_pattern.display_name}, "
                        f"Datei enthaelt {detected.display_name}"
                    )
                else:
                    self.logger.warning(
                        f"Pattern-Validierung fehlgeschlagen - "
                        f"Daten stimmen nicht mit {current_pattern.display_name} ueberein"
                    )
        except Exception as e:
            self.logger.warning(f"Pattern-Validierung fehlgeschlagen: {e}")

    def _detect_sample_pattern(self, sample: bytes) -> Optional[PatternType]:
        """Erkennt das Pattern eines Samples"""
        if all(b == 0x00 for b in sample):
            return PatternType.ZERO
        elif all(b == 0xFF for b in sample):
            return PatternType.ONE
        elif all(b == 0xAA for b in sample):
            return PatternType.ALT_AA
        elif all(b == 0x55 for b in sample):
            return PatternType.ALT_55
        elif len(set(sample)) > 10:  # Variiert stark = wahrscheinlich Random
            return PatternType.RANDOM
        return None

    def _calculate_processed_bytes(self) -> int:
        """Berechnet bereits verarbeitete Bytes"""
        file_size_bytes = int(self.session.file_size_gb * 1024 * 1024 * 1024)

        # Vollständig abgeschlossene Muster (completed_patterns Liste)
        completed_count = len(self.session.completed_patterns) if self.session.completed_patterns else 0
        bytes_per_pattern = self.session.file_count * file_size_bytes * 2  # Write + Verify

        # Aktuelles Pattern: +1 Phase wenn verify
        if self.session.current_phase == "verify":
            current_pattern_bytes = self.session.file_count * file_size_bytes
        else:
            current_pattern_bytes = 0

        # Aktuelle Phase
        current_phase_files = self.session.current_file_index
        bytes_in_phase = current_phase_files * file_size_bytes

        # Aktueller Chunk
        bytes_in_file = self.session.current_chunk_index * self.CHUNK_SIZE

        total = (completed_count * bytes_per_pattern) + current_pattern_bytes + bytes_in_phase + bytes_in_file
        return total

    def _write_pattern(self, generator: PatternGenerator, pattern_type: PatternType) -> bool:
        """
        Schreibt Testmuster in alle Dateien

        Args:
            generator: Pattern-Generator
            pattern_type: Typ des Musters

        Returns:
            bool: True wenn erfolgreich, False bei Abbruch
        """
        self.session.current_phase = "write"
        self.phase_changed.emit("Schreiben")

        self.logger.info(f"Phase: Schreiben")

        for file_idx in range(self.session.file_count):
            # Skip wenn Datei bereits vollständig mit DIESEM Pattern geschrieben
            if hasattr(self.session, 'file_patterns') and file_idx in self.session.file_patterns:
                if self.session.file_patterns[file_idx] == pattern_type.value:
                    # Datei bereits vorhanden und vollständig
                    self.logger.info(
                        f"Datei {file_idx + 1} bereits vorhanden mit {pattern_type.value} - ueberspringe"
                    )
                    continue

            # Skip wenn Resume und bereits geschrieben
            # Nutze den initialen Resume-Punkt, nicht den aktuellen Session-State
            if (self._initial_resume_pattern == pattern_type.value and
                self._initial_resume_phase == "write" and
                file_idx < self._initial_resume_file):
                continue

            self.session.current_file_index = file_idx
            filepath = self.file_manager.get_file_path(file_idx)

            self.file_changed.emit(file_idx, self.session.file_count)
            self.status_changed.emit(
                f"Schreibe Datei {file_idx + 1}/{self.session.file_count}"
            )

            success = self._write_file(filepath, generator)

            # Nach erfolgreichem Schreiben - Pattern speichern
            if success and hasattr(self.session, 'file_patterns'):
                self.session.file_patterns[file_idx] = pattern_type.value

            if not success or self._stop_event.is_set():
                return False

            # Pause-Handling
            if self._pause_event.is_set():
                self._handle_pause()

        return True

    def _verify_pattern(self, generator: PatternGenerator, pattern_type: PatternType) -> bool:
        """
        Verifiziert Testmuster in allen Dateien

        Args:
            generator: Pattern-Generator (muss resettet sein!)
            pattern_type: Typ des Musters

        Returns:
            bool: True wenn erfolgreich, False bei Abbruch
        """
        self.session.current_phase = "verify"
        self.session.current_file_index = 0
        self.phase_changed.emit("Verifizieren")

        self.logger.info(f"Phase: Verifizieren")

        for file_idx in range(self.session.file_count):
            # Skip wenn Resume
            # Nutze den initialen Resume-Punkt, nicht den aktuellen Session-State
            if (self._initial_resume_pattern == pattern_type.value and
                self._initial_resume_phase == "verify" and
                file_idx < self._initial_resume_file):
                # Generator muss aber bis zur richtigen Position vorspulen
                chunks_per_file = int(self.session.file_size_gb * 1024 * 1024 * 1024) // self.CHUNK_SIZE
                for _ in range(chunks_per_file):
                    generator.generate_chunk(self.CHUNK_SIZE)
                continue

            self.session.current_file_index = file_idx
            filepath = self.file_manager.get_file_path(file_idx)

            self.file_changed.emit(file_idx, self.session.file_count)
            self.status_changed.emit(
                f"Verifiziere Datei {file_idx + 1}/{self.session.file_count}"
            )

            success = self._verify_file(filepath, generator)

            if not success or self._stop_event.is_set():
                return False

            # Pause-Handling
            if self._pause_event.is_set():
                self._handle_pause()

        return True

    def _write_file(self, filepath: Path, generator: PatternGenerator) -> bool:
        """Schreibt eine einzelne Testdatei"""
        file_size_bytes = int(self.session.file_size_gb * 1024 * 1024 * 1024)
        chunks_total = file_size_bytes // self.CHUNK_SIZE

        # Resume-Handling: Prüfen ob wir mitten in dieser Datei sind
        start_chunk = 0
        file_mode = 'wb'  # Standard: Von vorne schreiben

        if self.session.current_chunk_index > 0:
            # Wir setzen mitten in dieser Datei fort
            start_chunk = self.session.current_chunk_index
            file_mode = 'ab'  # Append: An bestehende Datei anhängen

            # Generator muss zur richtigen Position vorspulen
            for _ in range(start_chunk):
                generator.generate_chunk(self.CHUNK_SIZE)

            self.logger.info(f"{filepath.name} - Fortsetzen ab Chunk {start_chunk}/{chunks_total}")

        try:
            with open(filepath, file_mode, buffering=self.IO_BUFFER_SIZE) as f:
                for chunk_idx in range(start_chunk, chunks_total):
                    # Chunk generieren und schreiben
                    chunk_start = time.time()
                    chunk = generator.generate_chunk(self.CHUNK_SIZE)
                    f.write(chunk)
                    chunk_elapsed = time.time() - chunk_start

                    # Statistiken aktualisieren
                    self.bytes_processed += self.CHUNK_SIZE
                    self._update_speed(chunk_elapsed)

                    # Timeout-Warnung bei langsamen I/O (mögliche Disk-Probleme)
                    if chunk_elapsed > self.IO_TIMEOUT_WARNING_SECONDS:
                        self.logger.warning(
                            f"{filepath.name} - Langsamer Schreibvorgang: "
                            f"Chunk {chunk_idx} dauerte {chunk_elapsed:.1f}s "
                            f"(>{self.IO_TIMEOUT_WARNING_SECONDS}s)"
                        )
                        self.log_entry.emit(
                            f"WARNUNG: Langsamer Schreibvorgang - "
                            f"moeglicherweise Disk-Probleme"
                        )

                    # Progress nur alle PROGRESS_UPDATE_INTERVAL Chunks emittieren
                    # Oder am Ende der Datei (letzter Chunk)
                    if chunk_idx % self.PROGRESS_UPDATE_INTERVAL == 0 or chunk_idx == chunks_total - 1:
                        self._emit_progress()

                        # Datei-Fortschritt emittieren
                        file_progress = int((chunk_idx + 1) / chunks_total * 100)
                        self.file_progress_updated.emit(file_progress)

                    # Stop-Check - Chunk fertig schreiben, dann speichern
                    if self._stop_event.is_set():
                        self.session.current_chunk_index = chunk_idx + 1
                        self._save_session()
                        self.status_changed.emit("Gestoppt - Session gespeichert")
                        self.logger.info("Test gestoppt - Session gespeichert")
                        return False

                    # Pause-Check
                    if self._pause_event.is_set():
                        self.session.current_chunk_index = chunk_idx + 1
                        self._save_session()
                        self._handle_pause()

            self.logger.success(f"{filepath.name} - Schreiben OK")
            self.session.current_chunk_index = 0
            self.file_progress_updated.emit(0)  # Zurücksetzen

            # Pause nach Datei Check
            if self._stop_after_file_event.is_set():
                self.session.current_chunk_index = 0
                self._save_session()
                self.state = TestState.PAUSED
                self.status_changed.emit("Pausiert nach Datei")
                self.logger.info("Test nach Datei pausiert")

                # Warten auf Resume (wie bei normaler Pause)
                while self._stop_after_file_event.is_set() and not self._stop_event.is_set():
                    time.sleep(0.1)

                if self._stop_event.is_set():
                    return False

                # Fortsetzen
                self.state = TestState.RUNNING
                self.status_changed.emit("Fortgesetzt")
                self.logger.info("Test fortgesetzt")

            return True

        except OSError as e:
            # Spezifische Fehlerbehandlung für bekannte OS-Fehler
            if e.errno == errno.ENOSPC:  # 28 - No space left on device
                self._handle_disk_full(filepath, e)
                return False  # Test beenden bei vollem Laufwerk
            elif e.errno in (errno.EIO, errno.ENODEV, errno.ENXIO):  # I/O Error, Device not found
                self._handle_drive_error(filepath, e)
                return False  # Test beenden bei Laufwerksfehler
            else:
                self._handle_write_error(filepath, e)
                return True  # Weitermachen mit nächster Datei
        except Exception as e:
            self._handle_write_error(filepath, e)
            return True  # Weitermachen mit nächster Datei

    def _verify_file(self, filepath: Path, generator: PatternGenerator) -> bool:
        """Verifiziert eine einzelne Testdatei"""
        file_size_bytes = int(self.session.file_size_gb * 1024 * 1024 * 1024)
        chunks_total = file_size_bytes // self.CHUNK_SIZE

        # Resume-Handling: Prüfen ob wir mitten in dieser Datei sind
        start_chunk = 0

        if self.session.current_chunk_index > 0:
            # Wir setzen mitten in dieser Datei fort
            start_chunk = self.session.current_chunk_index

            # Generator muss zur richtigen Position vorspulen
            for _ in range(start_chunk):
                generator.generate_chunk(self.CHUNK_SIZE)

            self.logger.info(f"{filepath.name} - Fortsetzen ab Chunk {start_chunk}/{chunks_total}")

        # Cache-Flush vor Verifikation um sicherzustellen dass von Disk gelesen wird
        self.platform_io.flush_file_cache(filepath)

        try:
            # Versuche Direct I/O (plattform-spezifisch)
            f = self.platform_io.open_file_direct(filepath, 'rb')
            if f is None:
                # Fallback: Standard-I/O wenn Direct I/O nicht verfuegbar
                self.logger.warning(f"{filepath.name} - Direct I/O nicht verfuegbar, nutze Standard-I/O")
                f = open(filepath, 'rb', buffering=self.IO_BUFFER_SIZE)

            with f:
                # Seek zur richtigen Position wenn Resume
                if start_chunk > 0:
                    offset = start_chunk * self.CHUNK_SIZE
                    # Bei Direct I/O: Prüfe dass Offset sector-aligned ist
                    if self.platform_io.is_direct_io_available() and hasattr(f, 'fileno'):
                        sector_size = self.platform_io.get_sector_size(filepath)
                        if offset % sector_size != 0:
                            # Dies sollte nicht passieren, da CHUNK_SIZE bereits aligned ist
                            # Aber zur Sicherheit: Runde auf nächste Sektor-Grenze ab
                            aligned_offset = (offset // sector_size) * sector_size
                            self.logger.warning(
                                f"Offset {offset} nicht sector-aligned ({sector_size} Bytes), "
                                f"nutze aligned offset {aligned_offset}"
                            )
                            offset = aligned_offset
                    f.seek(offset)

                for chunk_idx in range(start_chunk, chunks_total):
                    # Chunk lesen und vergleichen
                    chunk_start = time.time()
                    expected = generator.generate_chunk(self.CHUNK_SIZE)
                    actual = f.read(self.CHUNK_SIZE)
                    chunk_elapsed = time.time() - chunk_start

                    # Prüfe auf unvollständigen Read (kann bei USB-Disconnect, Netzlaufwerken passieren)
                    if len(actual) != self.CHUNK_SIZE:
                        self._handle_read_error(
                            filepath,
                            Exception(f"Unvollstaendiger Read: {len(actual)}/{self.CHUNK_SIZE} Bytes bei Chunk {chunk_idx}")
                        )
                        return True  # Weitermachen mit nächster Datei

                    # Verifikation
                    if expected != actual:
                        # Finde erste abweichende Position für Diagnose
                        first_diff_pos = None
                        for i, (e, a) in enumerate(zip(expected, actual)):
                            if e != a:
                                first_diff_pos = i
                                break
                        self._handle_verification_error(
                            filepath, chunk_idx, first_diff_pos,
                            expected[first_diff_pos] if first_diff_pos is not None else None,
                            actual[first_diff_pos] if first_diff_pos is not None else None
                        )

                    # Statistiken aktualisieren
                    self.bytes_processed += self.CHUNK_SIZE
                    self._update_speed(chunk_elapsed)

                    # Timeout-Warnung bei langsamen I/O (mögliche Disk-Probleme)
                    if chunk_elapsed > self.IO_TIMEOUT_WARNING_SECONDS:
                        self.logger.warning(
                            f"{filepath.name} - Langsamer Lesevorgang: "
                            f"Chunk {chunk_idx} dauerte {chunk_elapsed:.1f}s "
                            f"(>{self.IO_TIMEOUT_WARNING_SECONDS}s)"
                        )
                        self.log_entry.emit(
                            f"WARNUNG: Langsamer Lesevorgang - "
                            f"moeglicherweise Disk-Probleme"
                        )

                    # Progress nur alle PROGRESS_UPDATE_INTERVAL Chunks emittieren
                    # Oder am Ende der Datei (letzter Chunk)
                    if chunk_idx % self.PROGRESS_UPDATE_INTERVAL == 0 or chunk_idx == chunks_total - 1:
                        self._emit_progress()

                        # Datei-Fortschritt emittieren
                        file_progress = int((chunk_idx + 1) / chunks_total * 100)
                        self.file_progress_updated.emit(file_progress)

                    # Stop-Check - Chunk fertig lesen, dann speichern
                    if self._stop_event.is_set():
                        self.session.current_chunk_index = chunk_idx + 1
                        self._save_session()
                        self.status_changed.emit("Gestoppt - Session gespeichert")
                        self.logger.info("Test gestoppt - Session gespeichert")
                        return False

                    # Pause-Check
                    if self._pause_event.is_set():
                        self.session.current_chunk_index = chunk_idx + 1
                        self._save_session()
                        self._handle_pause()

            self.logger.success(f"{filepath.name} - Verifizierung OK")
            self.session.current_chunk_index = 0
            self.file_progress_updated.emit(0)  # Zurücksetzen

            # Pause nach Datei Check
            if self._stop_after_file_event.is_set():
                self.session.current_chunk_index = 0
                self._save_session()
                self.state = TestState.PAUSED
                self.status_changed.emit("Pausiert nach Datei")
                self.logger.info("Test nach Datei pausiert")

                # Warten auf Resume (wie bei normaler Pause)
                while self._stop_after_file_event.is_set() and not self._stop_event.is_set():
                    time.sleep(0.1)

                if self._stop_event.is_set():
                    return False

                # Fortsetzen
                self.state = TestState.RUNNING
                self.status_changed.emit("Fortgesetzt")
                self.logger.info("Test fortgesetzt")

            return True

        except OSError as e:
            # Spezifische Fehlerbehandlung für Laufwerksfehler
            if e.errno in (errno.EIO, errno.ENODEV, errno.ENXIO):  # I/O Error, Device not found
                self._handle_drive_error(filepath, e)
                return False  # Test beenden bei Laufwerksfehler
            else:
                self._handle_read_error(filepath, e)
                return True  # Weitermachen mit nächster Datei
        except Exception as e:
            self._handle_read_error(filepath, e)
            return True  # Weitermachen

    def _update_speed(self, chunk_time: float):
        """Aktualisiert Geschwindigkeits-Berechnung"""
        self._speed_samples.append(chunk_time)
        if len(self._speed_samples) > self._speed_window:
            self._speed_samples.pop(0)

    def _calculate_speed(self) -> float:
        """Berechnet aktuelle Geschwindigkeit in MB/s"""
        if not self._speed_samples:
            return 0.0

        avg_time = sum(self._speed_samples) / len(self._speed_samples)
        if avg_time <= 0:
            return 0.0

        mb_per_chunk = self.CHUNK_SIZE / (1024 * 1024)
        return mb_per_chunk / avg_time

    def _emit_progress(self):
        """Emittiert Fortschritts-Update"""
        speed = self._calculate_speed()
        self.progress_updated.emit(float(self.bytes_processed), float(self.total_bytes), speed)

    def _handle_pause(self):
        """Behandelt Pause-Request"""
        self.state = TestState.PAUSED
        self._save_session()
        self.status_changed.emit("Pausiert")
        self.logger.info("Test pausiert")

        # Warten auf Resume (Event wird cleared) oder Stop
        while self._pause_event.is_set() and not self._stop_event.is_set():
            time.sleep(0.1)

        if self._stop_event.is_set():
            return

        self.state = TestState.RUNNING
        self.status_changed.emit("Fortgesetzt")
        self.logger.info("Test fortgesetzt")

    def _save_session(self):
        """Speichert aktuellen Session-State"""
        self.session.elapsed_seconds = time.time() - self.start_time
        try:
            self.session_manager.save(self.session)
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Session: {e}")

    def _complete_test(self):
        """Test erfolgreich abgeschlossen"""
        self.state = TestState.COMPLETED
        elapsed = time.time() - self.start_time

        # Finaler Progress-Update: Alle Balken auf 100%
        # Setze Session-Werte auf Maximum damit GUI 100% anzeigt
        self.session.current_file_index = self.session.file_count
        self.session.current_chunk_index = 0

        # Wichtig: bytes_processed könnte durch Rundungsfehler < total_bytes sein
        self.bytes_processed = self.total_bytes
        self.progress_updated.emit(float(self.total_bytes), float(self.total_bytes), self._calculate_speed())
        self.file_progress_updated.emit(100)

        self.logger.section("Test abgeschlossen")
        self.logger.info(f"Dauer: {self._format_time(elapsed)}")
        self.logger.info(f"Fehler: {self.error_count}")

        summary = {
            'elapsed_seconds': elapsed,
            'error_count': self.error_count,
            'bytes_processed': self.bytes_processed,
            'avg_speed_mbps': self._calculate_speed()
        }

        self.test_completed.emit(summary)

        # Session löschen
        try:
            self.session_manager.delete()
        except Exception:
            pass

    def _format_time(self, seconds: float) -> str:
        """Formatiert Zeit"""
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return f"{h}h {m}m {sec}s"
        elif m > 0:
            return f"{m}m {sec}s"
        else:
            return f"{sec}s"

    def _handle_error(self, message: str):
        """Behandelt allgemeine Fehler"""
        self.state = TestState.ERROR
        self.error_occurred.emit({'message': message})
        self.log_entry.emit(f"FEHLER: {message}")

    def _handle_write_error(self, filepath: Path, error: Exception):
        """Behandelt Schreib-Fehler"""
        self.error_count += 1
        self.session.add_error(
            file=filepath.name,
            pattern=self.session.current_pattern_name,
            phase="write",
            message=str(error)
        )
        self.logger.error(f"{filepath.name} - Schreibfehler: {error}")
        self.error_occurred.emit({
            'file': filepath.name,
            'phase': 'write',
            'message': str(error)
        })

    def _handle_read_error(self, filepath: Path, error: Exception):
        """Behandelt Lese-Fehler"""
        self.error_count += 1
        self.session.add_error(
            file=filepath.name,
            pattern=self.session.current_pattern_name,
            phase="verify",
            message=f"Lesefehler: {error}"
        )
        self.logger.error(f"{filepath.name} - Lesefehler: {error}")
        self.error_occurred.emit({
            'file': filepath.name,
            'phase': 'verify',
            'message': str(error)
        })

    def _handle_verification_error(self, filepath: Path, chunk_idx: int,
                                    first_diff_pos: int = None,
                                    expected_byte: int = None,
                                    actual_byte: int = None):
        """Behandelt Verifikations-Fehler mit detaillierter Diagnose"""
        self.error_count += 1

        # Berechne absolute Position im Datei
        if first_diff_pos is not None:
            abs_offset = chunk_idx * self.CHUNK_SIZE + first_diff_pos
            detail_msg = (f"Chunk {chunk_idx}, Offset {first_diff_pos} "
                         f"(Datei-Offset: 0x{abs_offset:X}) - "
                         f"Erwartet: 0x{expected_byte:02X}, Gelesen: 0x{actual_byte:02X}")
        else:
            detail_msg = f"Chunk {chunk_idx} - Daten stimmen nicht ueberein"

        self.session.add_error(
            file=filepath.name,
            pattern=self.session.current_pattern_name,
            phase="verify",
            message=detail_msg
        )
        self.logger.error(f"{filepath.name} - Verifikation fehlgeschlagen: {detail_msg}")
        self.error_occurred.emit({
            'file': filepath.name,
            'phase': 'verify',
            'chunk': chunk_idx,
            'offset': first_diff_pos,
            'expected': expected_byte,
            'actual': actual_byte,
            'message': detail_msg
        })

    def _handle_disk_full(self, filepath: Path, error: OSError):
        """Behandelt Laufwerk-Voll-Fehler - beendet Test"""
        self.error_count += 1
        self.state = TestState.ERROR
        self.session.add_error(
            file=filepath.name,
            pattern=self.session.current_pattern_name,
            phase="write",
            message="Laufwerk voll - kein Speicherplatz mehr verfuegbar"
        )
        self.logger.error(f"LAUFWERK VOLL - Test wird beendet")
        self.logger.error(f"Letzte Datei: {filepath.name}")
        self._save_session()
        self.status_changed.emit("Laufwerk voll - Test beendet")
        self.error_occurred.emit({
            'file': filepath.name,
            'phase': 'write',
            'message': 'Laufwerk voll - kein Speicherplatz mehr verfuegbar',
            'critical': True
        })

    def _handle_drive_error(self, filepath: Path, error: OSError):
        """Behandelt kritische Laufwerksfehler (I/O Error, Gerät entfernt)"""
        self.error_count += 1
        self.state = TestState.ERROR
        error_msg = f"Laufwerksfehler (errno {error.errno}): {error.strerror}"
        self.session.add_error(
            file=filepath.name,
            pattern=self.session.current_pattern_name,
            phase=self.session.current_phase,
            message=error_msg
        )
        self.logger.error(f"KRITISCHER LAUFWERKSFEHLER: {error_msg}")
        self.logger.error(f"Datei: {filepath.name}")
        self._save_session()
        self.status_changed.emit("Laufwerksfehler - Test beendet")
        self.error_occurred.emit({
            'file': filepath.name,
            'phase': self.session.current_phase,
            'message': error_msg,
            'critical': True
        })

    # Public Control Methods

    def pause(self):
        """Pausiert den Test (thread-sicher)"""
        if self.state == TestState.RUNNING:
            self._pause_event.set()

    def resume(self):
        """Setzt den Test fort (thread-sicher)"""
        if self.state == TestState.PAUSED:
            self._pause_event.clear()
            self._stop_after_file_event.clear()

    def stop(self):
        """Stoppt den Test (thread-sicher)"""
        self._stop_event.set()
        if self.state == TestState.PAUSED:
            self._pause_event.clear()  # Aus Pause aufwecken

    def stop_after_current_file(self):
        """Stoppt nach aktueller Datei (thread-sicher)"""
        self._stop_after_file_event.set()
