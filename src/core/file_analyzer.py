"""
File Analyzer für DiskTest
Analysiert vorhandene Testdateien und erkennt Muster
"""
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .patterns import PatternType, PatternGenerator


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

    def __init__(self, target_path: str, expected_file_size_gb: float):
        """
        Initialisiert den Analyzer

        Args:
            target_path: Pfad zum Test-Verzeichnis
            expected_file_size_gb: Erwartete Dateigröße in GB
        """
        self.target_path = Path(target_path)
        self.expected_size = int(expected_file_size_gb * 1024 * 1024 * 1024)

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
        Extrahiert Index aus Dateinamen

        Args:
            filename: z.B. "disktest_042.dat"

        Returns:
            int: Index (z.B. 42)
        """
        # Format: disktest_NNN.dat
        if not filename.startswith("disktest_") or not filename.endswith(".dat"):
            raise ValueError(f"Ungültiger Dateiname: {filename}")

        index_str = filename[9:-4]  # "042"
        return int(index_str)

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
        Erkennt das Bitmuster einer Datei

        Liest die ersten SAMPLE_SIZE Bytes und vergleicht mit bekannten Mustern

        Args:
            filepath: Pfad zur Datei

        Returns:
            PatternType oder None wenn nicht erkennbar
        """
        try:
            with open(filepath, 'rb') as f:
                sample = f.read(self.SAMPLE_SIZE)

            if len(sample) == 0:
                return None

            # Prüfe gegen bekannte Muster
            # 0x00 - Alle Bytes 0
            if all(b == 0x00 for b in sample):
                return PatternType.ZERO

            # 0xFF - Alle Bytes 1
            if all(b == 0xFF for b in sample):
                return PatternType.ONE

            # 0xAA - Alternierende Bits (10101010)
            if all(b == 0xAA for b in sample):
                return PatternType.ALT_01

            # 0x55 - Alternierende Bits (01010101)
            if all(b == 0x55 for b in sample):
                return PatternType.ALT_10

            # Random - Variiert, nicht alle gleich
            # Heuristik: Wenn nicht alle Bytes gleich sind, ist es wahrscheinlich Random
            unique_bytes = len(set(sample))
            if unique_bytes > 10:  # Mindestens 10 verschiedene Byte-Werte
                return PatternType.RANDOM

            # Unbekannt
            return None

        except Exception:
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
