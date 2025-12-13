"""
Test-Engine für DiskTest
Führt die Festplattentests durch - Herzstück der Anwendung
"""
import time
import threading
from enum import Enum, auto
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from .patterns import PatternType, PatternGenerator, PATTERN_SEQUENCE
from .file_manager import FileManager
from .session import SessionData, SessionManager
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
    status_changed = Signal(str)
    log_entry = Signal(str)
    error_occurred = Signal(dict)
    test_completed = Signal(dict)
    pattern_changed = Signal(int, str)  # index, name
    phase_changed = Signal(str)  # "write" oder "verify"

    # Konstanten
    CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB

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

        # Komponenten
        self.file_manager = FileManager(config.target_path, config.file_size_gb)
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
                if self.session.current_pattern_index > pattern_idx:
                    continue

                self.session.current_pattern_index = pattern_idx
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
                success = self._write_pattern(gen, pattern_idx)
                if not success:
                    break

                # Verifikations-Phase
                gen.reset()  # Wichtig für Random!
                success = self._verify_pattern(gen, pattern_idx)
                if not success:
                    break

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
            current_pattern_index=0,
            current_file_index=0,
            current_phase="write",
            current_chunk_index=0,
            random_seed=self.random_seed,
            selected_patterns=[p.value for p in self.selected_patterns]
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
        self._initial_resume_pattern = self.session.current_pattern_index
        self._initial_resume_phase = self.session.current_phase
        self._initial_resume_file = self.session.current_file_index

        # Pattern-Auswahl aus Session wiederherstellen
        if self.session.selected_patterns:
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

    def _calculate_processed_bytes(self) -> int:
        """Berechnet bereits verarbeitete Bytes"""
        file_size_bytes = int(self.session.file_size_gb * 1024 * 1024 * 1024)

        # Vollständig abgeschlossene Muster
        completed_patterns = self.session.current_pattern_index
        bytes_per_pattern = self.session.file_count * file_size_bytes * 2  # Write + Verify

        # Aktuelle Phase
        current_phase_files = self.session.current_file_index
        bytes_in_phase = current_phase_files * file_size_bytes

        # Aktueller Chunk
        bytes_in_file = self.session.current_chunk_index * self.CHUNK_SIZE

        total = (completed_patterns * bytes_per_pattern) + bytes_in_phase + bytes_in_file
        return total

    def _write_pattern(self, generator: PatternGenerator, pattern_idx: int) -> bool:
        """
        Schreibt Testmuster in alle Dateien

        Args:
            generator: Pattern-Generator
            pattern_idx: Index des Musters

        Returns:
            bool: True wenn erfolgreich, False bei Abbruch
        """
        self.session.current_phase = "write"
        self.phase_changed.emit("Schreiben")

        self.logger.info(f"Phase: Schreiben")

        for file_idx in range(self.session.file_count):
            # Skip wenn Resume und bereits geschrieben
            # Nutze den initialen Resume-Punkt, nicht den aktuellen Session-State
            if (self._initial_resume_pattern == pattern_idx and
                self._initial_resume_phase == "write" and
                file_idx < self._initial_resume_file):
                continue

            self.session.current_file_index = file_idx
            filepath = self.file_manager.get_file_path(file_idx)

            self.status_changed.emit(
                f"Schreibe Datei {file_idx + 1}/{self.session.file_count}"
            )

            success = self._write_file(filepath, generator)

            if not success or self._stop_event.is_set():
                return False

            # Pause-Handling
            if self._pause_event.is_set():
                self._handle_pause()

        return True

    def _verify_pattern(self, generator: PatternGenerator, pattern_idx: int) -> bool:
        """
        Verifiziert Testmuster in allen Dateien

        Args:
            generator: Pattern-Generator (muss resettet sein!)
            pattern_idx: Index des Musters

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
            if (self._initial_resume_pattern == pattern_idx and
                self._initial_resume_phase == "verify" and
                file_idx < self._initial_resume_file):
                # Generator muss aber bis zur richtigen Position vorspulen
                chunks_per_file = int(self.session.file_size_gb * 1024 * 1024 * 1024) // self.CHUNK_SIZE
                for _ in range(chunks_per_file):
                    generator.generate_chunk(self.CHUNK_SIZE)
                continue

            self.session.current_file_index = file_idx
            filepath = self.file_manager.get_file_path(file_idx)

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
            with open(filepath, file_mode) as f:
                for chunk_idx in range(start_chunk, chunks_total):
                    # Chunk generieren und schreiben
                    chunk_start = time.time()
                    chunk = generator.generate_chunk(self.CHUNK_SIZE)
                    f.write(chunk)
                    chunk_elapsed = time.time() - chunk_start

                    # Statistiken aktualisieren
                    self.bytes_processed += self.CHUNK_SIZE
                    self._update_speed(chunk_elapsed)
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
            return True

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

        try:
            with open(filepath, 'rb') as f:
                # Seek zur richtigen Position wenn Resume
                if start_chunk > 0:
                    f.seek(start_chunk * self.CHUNK_SIZE)

                for chunk_idx in range(start_chunk, chunks_total):
                    # Chunk lesen und vergleichen
                    chunk_start = time.time()
                    expected = generator.generate_chunk(self.CHUNK_SIZE)
                    actual = f.read(self.CHUNK_SIZE)
                    chunk_elapsed = time.time() - chunk_start

                    # Verifikation
                    if expected != actual:
                        self._handle_verification_error(filepath, chunk_idx)

                    # Statistiken aktualisieren
                    self.bytes_processed += self.CHUNK_SIZE
                    self._update_speed(chunk_elapsed)
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
            return True

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
        pattern = PATTERN_SEQUENCE[self.session.current_pattern_index]
        self.session.add_error(
            file=filepath.name,
            pattern=pattern.value,
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
        pattern = PATTERN_SEQUENCE[self.session.current_pattern_index]
        self.session.add_error(
            file=filepath.name,
            pattern=pattern.value,
            phase="verify",
            message=f"Lesefehler: {error}"
        )
        self.logger.error(f"{filepath.name} - Lesefehler: {error}")
        self.error_occurred.emit({
            'file': filepath.name,
            'phase': 'verify',
            'message': str(error)
        })

    def _handle_verification_error(self, filepath: Path, chunk_idx: int):
        """Behandelt Verifikations-Fehler"""
        self.error_count += 1
        pattern = PATTERN_SEQUENCE[self.session.current_pattern_index]
        self.session.add_error(
            file=filepath.name,
            pattern=pattern.value,
            phase="verify",
            message=f"Chunk {chunk_idx} - Daten stimmen nicht überein"
        )
        self.logger.error(f"{filepath.name} - Verifikation fehlgeschlagen (Chunk {chunk_idx})")
        self.error_occurred.emit({
            'file': filepath.name,
            'phase': 'verify',
            'chunk': chunk_idx,
            'message': 'Daten stimmen nicht überein'
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

    def stop(self):
        """Stoppt den Test (thread-sicher)"""
        self._stop_event.set()
        if self.state == TestState.PAUSED:
            self._pause_event.clear()  # Aus Pause aufwecken
