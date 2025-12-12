"""
Test-Script für FileExpansionDialog

Simuliert die Vergrößerung von Dateien mit Progress-Anzeige
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gui.dialogs import FileExpansionDialog
from core.file_analyzer import FileAnalyzer, FileAnalysisResult
from core.patterns import PatternType


def create_test_files():
    """Erstellt Test-Daten für die Demo"""
    # Simuliere 3 zu kleine Dateien
    test_files = [
        FileAnalysisResult(
            filepath=Path("W:/disktest_001.dat"),
            file_index=1,
            detected_pattern=PatternType.ZERO,
            is_complete=False,
            actual_size=512 * 1024 * 1024,  # 512 MB
            expected_size=1024 * 1024 * 1024  # 1 GB
        ),
        FileAnalysisResult(
            filepath=Path("W:/disktest_002.dat"),
            file_index=2,
            detected_pattern=PatternType.ONE,
            is_complete=False,
            actual_size=512 * 1024 * 1024,
            expected_size=1024 * 1024 * 1024
        ),
        FileAnalysisResult(
            filepath=Path("W:/disktest_003.dat"),
            file_index=3,
            detected_pattern=PatternType.ALT_01,
            is_complete=False,
            actual_size=768 * 1024 * 1024,  # 768 MB
            expected_size=1024 * 1024 * 1024
        ),
    ]
    return test_files


def main():
    app = QApplication(sys.argv)

    # HINWEIS: Dieser Test würde echte Dateien vergrößern!
    # Nur ausführen wenn die Dateien wirklich existieren und du sie vergrößern möchtest

    print("WARNUNG: Dieser Test würde echte Dateien vergrößern!")
    print("Die Demo zeigt wie der Progress-Dialog aussieht.")
    print("\nZum Testen mit echten Dateien:")
    print("1. Erstelle Testdateien in W:/")
    print("2. Kommentiere die sys.exit() Zeile aus")
    print("3. Führe das Script aus")

    sys.exit(0)

    # Test-Daten
    test_files = create_test_files()

    # FileAnalyzer erstellen
    analyzer = FileAnalyzer("W:/", expected_file_size_gb=1.0)

    # Dialog anzeigen
    dialog = FileExpansionDialog(analyzer, test_files)
    result = dialog.exec()

    # Ergebnisse
    success, errors = dialog.get_results()
    print(f"\nErgebnisse:")
    print(f"  Erfolgreich: {success}")
    print(f"  Fehler: {errors}")

    sys.exit(0)


if __name__ == '__main__':
    main()
