"""
Integrations-Test für DiskTest

Testet die vollständige Integration von GUI und Test-Engine.
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Füge src zum Python-Path hinzu
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from gui import MainWindow


def test_integration():
    """
    Führt einen Integrationstest durch.

    - Erstellt temporäres Verzeichnis
    - Startet GUI
    - Simuliert Benutzerinteraktion
    """
    app = QApplication(sys.argv)

    # Temporäres Verzeichnis für Test
    temp_dir = tempfile.mkdtemp(prefix="disktest_")
    print(f"Temporäres Testverzeichnis: {temp_dir}")

    # Hauptfenster erstellen
    window = MainWindow()

    # Test-Konfiguration setzen
    config = {
        'target_path': temp_dir,
        'test_size_gb': 1,  # Nur 1 GB für schnellen Test
        'file_size_mb': 100,  # Kleine Dateien (100 MB)
        'whole_drive': False
    }
    window.config_widget.set_config(config)

    print("\nKonfiguration gesetzt:")
    print(f"  Zielpfad: {temp_dir}")
    print(f"  Testgröße: 1 GB")
    print(f"  Dateigröße: 100 MB")
    print(f"  -> Erwartet: ~10 Dateien")

    # Fenster anzeigen
    window.show()

    print("\n" + "="*60)
    print("GUI INTEGRATIONSTEST")
    print("="*60)
    print("\nDas Hauptfenster wird angezeigt.")
    print("\nManuelle Tests:")
    print("1. Prüfen Sie die Konfigurationsanzeige")
    print("2. Prüfen Sie den 'Freier Speicher' Wert")
    print("3. Optional: Klicken Sie 'Start' für einen echten Test")
    print("   (Achtung: Dies erstellt Testdateien!)")
    print("4. Optional: Testen Sie Pause/Resume")
    print("5. Schließen Sie das Fenster zum Beenden")
    print("\nHINWEIS: Bei Programmende wird das Temp-Verzeichnis gelöscht.")
    print("="*60)

    # Cleanup-Funktion registrieren
    def cleanup():
        print("\n\nRäume auf...")
        try:
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)
                print(f"Temporäres Verzeichnis gelöscht: {temp_dir}")
        except Exception as e:
            print(f"Fehler beim Löschen: {e}")

    app.aboutToQuit.connect(cleanup)

    # Event-Loop starten
    sys.exit(app.exec())


def quick_gui_test():
    """
    Schneller GUI-Test ohne echten Disk-Test.

    Zeigt GUI mit voreingestellten Werten und simulierten Progress.
    """
    app = QApplication(sys.argv)

    window = MainWindow()

    # Beispiel-Konfiguration
    temp_dir = tempfile.gettempdir()
    config = {
        'target_path': temp_dir,
        'test_size_gb': 50,
        'file_size_mb': 1000,
        'whole_drive': False
    }
    window.config_widget.set_config(config)

    # Simulierte Progress-Werte setzen
    window.progress_widget.set_progress(42)
    window.progress_widget.set_time_remaining("2h 15m")
    window.progress_widget.set_pattern("2/5 (0xFF)")
    window.progress_widget.set_phase("Verifizieren")
    window.progress_widget.set_file("23/50 (disktest_023.dat)")
    window.progress_widget.set_speed("185.3 MB/s")
    window.progress_widget.set_error_count(0)

    # Beispiel-Logs
    window.log_widget.add_log("14:30:22", "INFO", "Test gestartet - Ziel: D:\\")
    window.log_widget.add_log("14:30:22", "INFO", "Konfiguration: 50 Dateien à 1 GB")
    window.log_widget.add_log("14:35:44", "SUCCESS", "disktest_001.dat - 0x00 - Schreiben OK")
    window.log_widget.add_log("14:40:12", "SUCCESS", "disktest_001.dat - 0x00 - Verifizierung OK")
    window.log_widget.add_log("14:45:33", "SUCCESS", "disktest_002.dat - 0x00 - Schreiben OK")
    window.log_widget.add_log("14:50:55", "WARNING", "Geschwindigkeit unter Durchschnitt")
    window.log_widget.add_log("14:55:12", "ERROR", "disktest_023.dat - Verifizierung FEHLGESCHLAGEN")

    # Simuliere "Running" State
    window.control_widget.set_state_running()
    window.config_widget.set_enabled(False)

    window.show()

    print("\n" + "="*60)
    print("QUICK GUI TEST - Simulierte Werte")
    print("="*60)
    print("\nDie GUI zeigt simulierte Testwerte an.")
    print("Dies ist KEIN echter Test - nur zur visuellen Überprüfung.")
    print("\nPrüfen Sie:")
    print("  - Fortschrittsbalken (42%)")
    print("  - Restzeit (2h 15m)")
    print("  - Muster-Anzeige (2/5 - 0xFF)")
    print("  - Geschwindigkeit (185.3 MB/s)")
    print("  - Log-Einträge mit Farbcodierung")
    print("  - Button-States (Start deaktiviert, Pause/Stop aktiviert)")
    print("="*60)

    sys.exit(app.exec())


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='DiskTest Integration Tests')
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Schneller GUI-Test mit simulierten Werten (kein echter Disk-Test)'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Vollständiger Integrationstest mit echtem Temp-Verzeichnis'
    )

    args = parser.parse_args()

    if args.quick:
        quick_gui_test()
    elif args.full:
        test_integration()
    else:
        # Default: Quick Test
        print("Verwende --quick für schnellen GUI-Test oder --full für vollständigen Test")
        print("Standard: --quick\n")
        quick_gui_test()
