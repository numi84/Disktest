"""
File Analyzer für DiskTest
Analysiert vorhandene Testdateien und erkennt Muster
"""
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .patterns import PatternType, PatternGenerator

# Modul-Logger
logger = logging.getLogger(__name__)


@dataclass
class FileAnalysisResult:
    """Ergebnis der Dateianalyse"""
    filepath: Path
    file_index: int
    detected_pattern: Optional[PatternType]
    is_complete: bool  # Datei hat erwartete Größe
    actual_size: int
    expected_size: int


class FileAnalyzer:
    """
    Analysiert vorhandene Testdateien

    - Erkennt Bitmuster durch Lesen der ersten Bytes
    - Prüft ob Dateien vollständig sind
    - Hilft bei Session-Recovery
    """

    SAMPLE_SIZE = 1024  # Erste 1 KB zum Pattern-Check
    CHUNK_SIZE = 16 * 1024 * 1024  # Muss mit test_engine.py übereinstimmen

    def __init__(self, target_path: str, expected_file_size_gb: float):
        """
        Initialisiert den Analyzer

        Args:
            target_path: Pfad zum Test-Verzeichnis
            expected_file_size_gb: Erwartete Dateigröße in GB
        """
        self.target_path = Path(target_path)

        # Berechne erwartete Größe GENAU wie test_engine.py
        # (mit Integer-Division für Chunk-Anzahl)
        file_size_bytes = int(expected_file_size_gb * 1024 * 1024 * 1024)
        chunks_total = file_size_bytes // self.CHUNK_SIZE
        self.expected_size = chunks_total * self.CHUNK_SIZE

    def analyze_existing_files(self) -> List[FileAnalysisResult]:
        """
        Analysiert alle vorhandenen Testdateien

        Returns:
            Liste von FileAnalysisResult, sortiert nach Dateiindex
        """
        results = []

        # Finde alle disktest_*.dat Dateien
        pattern_files = sorted(self.target_path.glob("disktest_*.dat"))

        for filepath in pattern_files:
            # Extrahiere Index aus Dateinamen
            try:
                index = self._extract_file_index(filepath.name)
            except ValueError:
                continue

            # Analysiere Datei
            result = self._analyze_file(filepath, index)
            results.append(result)

        return sorted(results, key=lambda r: r.file_index)

    def _extract_file_index(self, filename: str) -> int:
        """
        Extrahiert Index aus Dateinamen (flexibel für 3-6 Stellen)

        Args:
            filename: z.B. "disktest_042.dat" oder "disktest_00042.dat"

        Returns:
            int: Index (z.B. 42)

        Raises:
            ValueError: Wenn Dateiname ungültiges Format hat
        """
        # Format: disktest_NNN.dat (3-6 Stellen)
        if not filename.startswith("disktest_") or not filename.endswith(".dat"):
            raise ValueError(f"Ungültiger Dateiname: {filename}")

        index_str = filename[9:-4]  # "042" oder "00042" etc.

        try:
            index = int(index_str)
        except ValueError:
            raise ValueError(f"Index ist nicht numerisch: {index_str} in {filename}")

        if index < 1 or index > 999999:
            raise ValueError(f"Index außerhalb gültigem Bereich (1-999999): {index} in {filename}")

        return index

    def _analyze_file(self, filepath: Path, index: int) -> FileAnalysisResult:
        """
        Analysiert eine einzelne Datei

        Args:
            filepath: Pfad zur Datei
            index: Dateiindex

        Returns:
            FileAnalysisResult
        """
        # Dateigröße prüfen
        actual_size = filepath.stat().st_size
        is_complete = (actual_size == self.expected_size)

        # Pattern erkennen
        detected_pattern = self._detect_pattern(filepath)

        return FileAnalysisResult(
            filepath=filepath,
            file_index=index,
            detected_pattern=detected_pattern,
            is_complete=is_complete,
            actual_size=actual_size,
            expected_size=self.expected_size
        )

    def _detect_pattern(self, filepath: Path) -> Optional[PatternType]:
        """
        Erkennt das Bitmuster einer Datei mit optimierten Byte-Array-Vergleichen.

        Nutzt direkte bytes-Vergleiche statt Python-Loops fuer ~5x Performance.
        Python's `bytes ==` verwendet intern memcmp (C-Level), was sehr schnell ist.

        Args:
            filepath: Pfad zur Datei

        Returns:
            PatternType oder None wenn nicht erkennbar
        """
        try:
            with open(filepath, 'rb') as f:
                sample = f.read(self.SAMPLE_SIZE)

            sample_len = len(sample)
            if sample_len == 0:
                return None

            # Erstelle Pattern-Arrays fuer direkten Vergleich
            # bytes-Vergleiche sind in C implementiert (memcmp) - sehr schnell
            zero_pattern = bytes(sample_len)
            one_pattern = bytes([0xFF] * sample_len)
            aa_pattern = bytes([0xAA] * sample_len)
            ff_pattern = bytes([0x55] * sample_len)

            # Direkte Byte-Array-Vergleiche (C-Level memcmp)
            # 0x00 - Alle Bytes 0
            if sample == zero_pattern:
                return PatternType.ZERO

            # 0xFF - Alle Bytes 1
            if sample == one_pattern:
                return PatternType.ONE

            # 0xAA - Alternierende Bits (10101010)
            if sample == aa_pattern:
                return PatternType.ALT_AA

            # 0x55 - Alternierende Bits (01010101)
            if sample == ff_pattern:
                return PatternType.ALT_55

            # Random - Variiert, nicht alle gleich
            # Heuristik: Wenn nicht alle Bytes gleich sind, ist es wahrscheinlich Random
            unique_bytes = len(set(sample))
            if unique_bytes > 10:  # Mindestens 10 verschiedene Byte-Werte
                return PatternType.RANDOM

            # Unbekannt
            return None

        except Exception as e:
            logger.warning(f"Fehler beim Lesen von {filepath}: {e}")
            return None

    def find_last_complete_file(self, results: List[FileAnalysisResult]) -> Optional[FileAnalysisResult]:
        """
        Findet die letzte vollständige Datei

        Args:
            results: Liste von Analyse-Ergebnissen

        Returns:
            FileAnalysisResult der letzten vollständigen Datei oder None
        """
        complete_files = [r for r in results if r.is_complete]
        if not complete_files:
            return None

        return max(complete_files, key=lambda r: r.file_index)

    def find_incomplete_files(self, results: List[FileAnalysisResult]) -> List[FileAnalysisResult]:
        """
        Findet alle unvollständigen Dateien

        Args:
            results: Liste von Analyse-Ergebnissen

        Returns:
            Liste von unvollständigen Dateien
        """
        return [r for r in results if not r.is_complete]

    def find_smaller_files(self, results: List[FileAnalysisResult]) -> List[FileAnalysisResult]:
        """
        Findet alle Dateien die kleiner als erwartet sind (aber vollständig für ihre alte Größe)

        Args:
            results: Liste von Analyse-Ergebnissen

        Returns:
            Liste von zu kleinen Dateien
        """
        return [r for r in results if r.actual_size > 0 and r.actual_size < self.expected_size]

    def categorize_files(self, results: List[FileAnalysisResult]) -> dict:
        """
        Kategorisiert Dateien in gegenseitig ausschließende Gruppen

        Diese Methode löst das Problem der überlappenden Kategorien
        (z.B. "zu klein" war Subset von "unvollständig").

        Logik:
        - complete: actual_size == expected_size && detected_pattern != None
        - smaller_consistent: 0 < actual_size < expected_size && detected_pattern != None
        - corrupted_incomplete: detected_pattern == None || actual_size == 0 || actual_size > expected_size

        Args:
            results: Liste von FileAnalysisResult

        Returns:
            dict mit:
            - 'complete': Liste vollständiger Dateien
            - 'smaller_consistent': Liste zu kleiner konsistenter Dateien (können vergrößert werden)
            - 'corrupted_incomplete': Liste beschädigter/unfertiger Dateien (müssen überschrieben werden)
        """
        complete = []
        smaller_consistent = []
        corrupted_incomplete = []

        for result in results:
            # Kategorie 3: Beschädigt (kein Muster, leer, oder zu groß)
            if (result.detected_pattern is None or
                result.actual_size == 0 or
                result.actual_size > self.expected_size):
                corrupted_incomplete.append(result)
            # Kategorie 1: Vollständig (richtige Größe + Muster erkannt)
            elif result.actual_size == self.expected_size:
                complete.append(result)
            # Kategorie 2: Zu klein aber konsistent (alte Testgröße)
            elif 0 < result.actual_size < self.expected_size:
                smaller_consistent.append(result)

        return {
            'complete': complete,
            'smaller_consistent': smaller_consistent,
            'corrupted_incomplete': corrupted_incomplete
        }

    def get_pattern_summary(self, results: List[FileAnalysisResult]) -> dict:
        """
        Erstellt eine Zusammenfassung der erkannten Muster

        Args:
            results: Liste von Analyse-Ergebnissen

        Returns:
            dict mit Pattern -> Anzahl Dateien
        """
        summary = {}

        for result in results:
            if result.detected_pattern:
                pattern_name = result.detected_pattern.value
                summary[pattern_name] = summary.get(pattern_name, 0) + 1

        return summary

    def estimate_current_pattern(self, results: List[FileAnalysisResult]) -> Optional[Tuple[PatternType, int]]:
        """
        Schätzt das aktuelle Muster basierend auf vorhandenen Dateien

        Logik:
        - Sucht das häufigste Muster
        - Zählt wie viele vollständige Dateien mit diesem Muster vorhanden sind

        Args:
            results: Liste von Analyse-Ergebnissen

        Returns:
            Tuple (PatternType, Anzahl vollständiger Dateien) oder None
        """
        complete_results = [r for r in results if r.is_complete and r.detected_pattern]

        if not complete_results:
            return None

        # Zähle Muster
        pattern_counts = {}
        for result in complete_results:
            pattern = result.detected_pattern
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        # Häufigstes Muster
        most_common_pattern = max(pattern_counts.items(), key=lambda x: x[1])

        return most_common_pattern

    def expand_file_to_target_size(self, filepath: Path, pattern_type: PatternType,
                                   progress_callback=None) -> bool:
        """
        Vergrößert eine Datei auf die erwartete Zielgröße durch Wiederholen des Musters

        Args:
            filepath: Pfad zur zu vergrößernden Datei
            pattern_type: Das Bitmuster das wiederholt werden soll
            progress_callback: Optional callback(current_bytes, total_bytes) für Fortschritt

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            current_size = filepath.stat().st_size

            if current_size >= self.expected_size:
                return True  # Bereits groß genug

            bytes_to_add = self.expected_size - current_size

            # Pattern-Generator erstellen mit dem erkannten Muster
            pattern_gen = PatternGenerator(pattern_type)

            # Datei im Append-Modus öffnen
            with open(filepath, 'ab') as f:
                bytes_written = 0

                while bytes_written < bytes_to_add:
                    # Chunk-Größe begrenzen auf verbleibende Bytes
                    chunk_size = min(self.CHUNK_SIZE, bytes_to_add - bytes_written)

                    # Pattern generieren
                    chunk = pattern_gen.generate_chunk(chunk_size)

                    # Schreiben
                    f.write(chunk)
                    bytes_written += chunk_size

                    # Progress-Callback
                    if progress_callback:
                        progress_callback(current_size + bytes_written, self.expected_size)

            return True

        except Exception as e:
            logger.error(f"Fehler beim Vergrößern von {filepath}: {e}")
            return False

    def expand_files(self, files_to_expand: List[FileAnalysisResult],
                    progress_callback=None) -> Tuple[int, int]:
        """
        Vergrößert mehrere Dateien auf Zielgröße

        Args:
            files_to_expand: Liste von FileAnalysisResult die vergrößert werden sollen
            progress_callback: Optional callback(file_index, total_files, filename) für Fortschritt

        Returns:
            Tuple (erfolgreiche_dateien, fehlerhafte_dateien)
        """
        success_count = 0
        error_count = 0
        total_files = len(files_to_expand)

        for i, file_result in enumerate(files_to_expand):
            if progress_callback:
                progress_callback(i, total_files, file_result.filepath.name)

            # Pattern muss bekannt sein
            if not file_result.detected_pattern:
                error_count += 1
                continue

            # Vergrößern
            if self.expand_file_to_target_size(file_result.filepath, file_result.detected_pattern):
                success_count += 1
            else:
                error_count += 1

        return (success_count, error_count)
