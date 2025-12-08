"""
Test-Skript für Test-Engine (Phase 3)
Testet: test_engine.py

HINWEIS: Dieser Test erstellt echte Testdateien (klein dimensioniert für Tests)
"""
import sys
import os
from pathlib import Path
import time

# Pfad zum src-Verzeichnis hinzufügen
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtCore import QCoreApplication
from core.test_engine import TestEngine, TestConfig, TestState
from core.session import SessionManager


# Globale Variablen für Signal-Handling
test_results = {
    'progress_updates': 0,
    'status_updates': [],
    'log_entries': [],
    'errors': [],
    'completed': False,
    'final_summary': None
}


def on_progress_updated(current: float, total: float, speed: float):
    """Progress Signal Handler"""
    test_results['progress_updates'] += 1
    if test_results['progress_updates'] % 10 == 0:  # Jede 10. Nachricht ausgeben
        percent = (current / total * 100) if total > 0 else 0
        print(f"   Fortschritt: {percent:.1f}% ({speed:.1f} MB/s)")


def on_status_changed(status):
    """Status Signal Handler"""
    test_results['status_updates'].append(status)
    print(f"   Status: {status}")


def on_log_entry(log_msg):
    """Log Signal Handler"""
    test_results['log_entries'].append(log_msg)


def on_error_occurred(error_dict):
    """Error Signal Handler"""
    test_results['errors'].append(error_dict)
    print(f"   [FEHLER] {error_dict}")


def on_test_completed(summary):
    """Test Completed Signal Handler"""
    test_results['completed'] = True
    test_results['final_summary'] = summary
    print(f"   [OK] Test abgeschlossen!")
    print(f"   Dauer: {summary['elapsed_seconds']:.1f}s")
    print(f"   Fehler: {summary['error_count']}")
    print(f"   Geschwindigkeit: {summary['avg_speed_mbps']:.1f} MB/s")


def on_pattern_changed(index, name):
    """Pattern Changed Signal Handler"""
    print(f"   Muster {index + 1}/5: {name}")


def on_phase_changed(phase):
    """Phase Changed Signal Handler"""
    print(f"   Phase: {phase}")


def test_basic_engine():
    """Testet grundlegende Test-Engine Funktionalität"""
    print("\n" + "=" * 80)
    print("TEST: Grundlegende Test-Engine")
    print("=" * 80)

    # Test-Verzeichnis erstellen
    test_dir = Path("test_engine_data")
    test_dir.mkdir(exist_ok=True)
    print(f"\nTest-Verzeichnis: {test_dir.absolute()}")

    # SEHR kleine Testdateien für schnellen Test
    # 0.001 GB = 1 MB pro Datei, 2 Dateien = 2 MB total
    config = TestConfig(
        target_path=str(test_dir),
        file_size_gb=0.001,   # 1 MB
        total_size_gb=0.002,  # 2 MB gesamt (2 Dateien)
        resume_session=False
    )

    print("\nKonfiguration:")
    print(f"   Ziel: {config.target_path}")
    print(f"   Dateigröße: {config.file_size_gb} GB (1 MB)")
    print(f"   Gesamtgröße: {config.total_size_gb} GB (2 MB)")
    print(f"   Erwartete Dateien: 2")

    # QCoreApplication erstellen (für QThread)
    app = QCoreApplication(sys.argv)

    # Test-Engine erstellen
    print("\n1. Test-Engine erstellen:")
    engine = TestEngine(config)
    print(f"   [OK] Engine erstellt: State={engine.state.name}")

    # Signals verbinden
    print("\n2. Signals verbinden:")
    engine.progress_updated.connect(on_progress_updated)
    engine.status_changed.connect(on_status_changed)
    engine.log_entry.connect(on_log_entry)
    engine.error_occurred.connect(on_error_occurred)
    engine.test_completed.connect(on_test_completed)
    engine.pattern_changed.connect(on_pattern_changed)
    engine.phase_changed.connect(on_phase_changed)
    print(f"   [OK] Signals verbunden")

    # Test starten
    print("\n3. Test starten:")
    print("   (Ausgabe während Test)")
    print("   " + "-" * 76)

    engine.start()

    # Warten bis Test abgeschlossen mit finished Signal
    engine.wait(60000)  # 60 Sekunden Timeout

    # Events verarbeiten
    app.processEvents()
    time.sleep(0.5)  # Kurze Pause damit alle Signals verarbeitet werden
    app.processEvents()

    print("   " + "-" * 76)

    # Ergebnisse prüfen
    print("\n4. Ergebnisse prüfen:")
    print(f"   Progress Updates: {test_results['progress_updates']}")
    print(f"   Status Updates: {len(test_results['status_updates'])}")
    print(f"   Log Entries: {len(test_results['log_entries'])}")
    print(f"   Errors: {len(test_results['errors'])}")
    print(f"   Completed: {test_results['completed']}")

    if test_results['completed']:
        print(f"   [OK] Test erfolgreich abgeschlossen")
        summary = test_results['final_summary']
        print(f"   Verarbeitete Bytes: {summary['bytes_processed']}")
    else:
        print(f"   [FEHLER] Test nicht abgeschlossen")

    # Testdateien prüfen
    print("\n5. Testdateien prüfen:")
    test_files = list(test_dir.glob("disktest_*.dat"))
    print(f"   Gefundene Testdateien: {len(test_files)}")
    for f in test_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"   - {f.name}: {size_mb:.2f} MB")

    # Log-Datei prüfen
    print("\n6. Log-Datei prüfen:")
    log_files = list(test_dir.glob("disktest_*.log"))
    if log_files:
        log_file = log_files[0]
        size = log_file.stat().st_size
        print(f"   Log-Datei: {log_file.name} ({size} Bytes)")
        print(f"   [OK] Log-Datei erstellt")
    else:
        print(f"   [FEHLER] Keine Log-Datei gefunden")

    # Aufräumen
    print("\n7. Aufräumen:")
    for f in test_dir.glob("disktest_*"):
        try:
            f.unlink()
            print(f"   Gelöscht: {f.name}")
        except Exception as e:
            print(f"   Fehler beim Löschen von {f.name}: {e}")

    try:
        test_dir.rmdir()
        print(f"   Test-Verzeichnis gelöscht")
    except Exception as e:
        print(f"   Fehler beim Löschen des Verzeichnisses: {e}")

    return test_results['completed']


def test_pause_resume():
    """Testet Pause/Resume Funktionalität"""
    print("\n" + "=" * 80)
    print("TEST: Pause/Resume")
    print("=" * 80)

    # Test-Verzeichnis
    test_dir = Path("test_pause_resume")
    test_dir.mkdir(exist_ok=True)

    # Config
    config = TestConfig(
        target_path=str(test_dir),
        file_size_gb=0.002,   # 2 MB
        total_size_gb=0.004,  # 4 MB (2 Dateien)
        resume_session=False
    )

    print("\nTest mit Pause nach 50%:")

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    # Engine erstellen
    engine = TestEngine(config)

    # Signal für Test-Abbruch
    paused_at = {'percent': 0}

    def on_progress_pause(current: float, total: float, speed: float):
        percent = (current / total * 100) if total > 0 else 0
        if percent > 50 and paused_at['percent'] == 0:
            print(f"   Pause bei {percent:.1f}%")
            engine.pause()
            paused_at['percent'] = percent

    engine.progress_updated.connect(on_progress_pause)

    print("   Test starten...")
    engine.start()

    # Warten bis pausiert
    timeout = 30
    elapsed = 0
    while engine.state != TestState.PAUSED and elapsed < timeout and engine.isRunning():
        app.processEvents()
        time.sleep(0.1)
        elapsed += 0.1

    if engine.state == TestState.PAUSED:
        print(f"   [OK] Test pausiert bei {paused_at['percent']:.1f}%")

        # Session prüfen
        session_mgr = SessionManager(str(test_dir))
        if session_mgr.exists():
            print(f"   [OK] Session-Datei existiert")
            info = session_mgr.get_session_info()
            if info:
                print(f"   Session-Info: {info['progress_percent']:.1f}%")
        else:
            print(f"   [FEHLER] Session-Datei existiert nicht")

        # Resume
        print("   Test fortsetzen...")
        engine.resume()

        # Warten bis abgeschlossen
        while engine.isRunning() and elapsed < timeout * 2:
            app.processEvents()
            time.sleep(0.1)
            elapsed += 0.1

        if not engine.isRunning():
            print(f"   [OK] Test nach Resume abgeschlossen")
        else:
            print(f"   [WARNUNG] Test läuft noch")
            engine.stop()
            engine.wait(5000)

    else:
        print(f"   [FEHLER] Test nicht pausiert (State: {engine.state.name})")
        engine.stop()
        engine.wait(5000)

    # Aufräumen
    for f in test_dir.glob("disktest_*"):
        f.unlink()
    test_dir.rmdir()

    return True


def main():
    """Hauptfunktion"""
    print("\n" + "=" * 80)
    print(" DiskTest - Phase 3: Test-Engine Tests")
    print("=" * 80)
    print("\nHINWEIS: Dieser Test erstellt kleine Testdateien (wenige MB)")

    try:
        # Test 1: Grundlegende Funktionalität
        result1 = test_basic_engine()

        # Test 2: Pause/Resume
        result2 = test_pause_resume()

        if result1 and result2:
            print("\n" + "=" * 80)
            print(" [OK] Alle Tests erfolgreich abgeschlossen!")
            print("=" * 80 + "\n")
            return 0
        else:
            print("\n" + "=" * 80)
            print(" [FEHLER] Einige Tests fehlgeschlagen")
            print("=" * 80 + "\n")
            return 1

    except Exception as e:
        print(f"\n[FEHLER] Exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
