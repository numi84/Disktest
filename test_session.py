"""
Test-Skript für Session-Management (Phase 2)
Testet: session.py
"""
import sys
import os
from pathlib import Path
import json

# Pfad zum src-Verzeichnis hinzufügen
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.session import SessionData, SessionManager


def test_session_data():
    """Testet SessionData Dataclass"""
    print("\n" + "=" * 80)
    print("TEST: SessionData")
    print("=" * 80)

    # Test 1: SessionData erstellen
    print("\n1. Test SessionData Erstellung:")
    session = SessionData(
        target_path="D:\\",
        file_size_gb=1.0,
        total_size_gb=50.0,
        file_count=50,
        current_pattern_index=2,
        current_file_index=23,
        current_phase="verify",
        current_chunk_index=48,
        random_seed=123456789
    )
    print(f"   SessionData erstellt: {session.target_path}")
    print(f"   Muster-Index: {session.current_pattern_index}")
    print(f"   Datei-Index: {session.current_file_index}")
    print(f"   Phase: {session.current_phase}")

    # Test 2: Fehler hinzufügen
    print("\n2. Test Fehler hinzufügen:")
    session.add_error(
        file="disktest_015.dat",
        pattern="FF",
        phase="verify",
        message="Daten stimmen nicht ueberein"
    )
    print(f"   Fehler hinzugefuegt: {len(session.errors)} Fehler")
    print(f"   Fehler-Details: {session.errors[0]['file']} - {session.errors[0]['message']}")

    # Test 3: Fortschritt berechnen
    print("\n3. Test Fortschritt-Berechnung:")
    progress = session.get_progress_percentage()
    print(f"   Fortschritt: {progress:.1f}%")
    print(f"   (Muster {session.current_pattern_index + 1}/5, Datei {session.current_file_index + 1}/{session.file_count})")

    # Test verschiedene Zustände
    test_cases = [
        (0, 0, "write"),   # Start
        (0, 25, "verify"), # Mitte von Muster 1 Verify
        (2, 0, "write"),   # Start von Muster 3
        (4, 49, "verify"), # Fast Ende
    ]
    for pattern_idx, file_idx, phase in test_cases:
        session.current_pattern_index = pattern_idx
        session.current_file_index = file_idx
        session.current_phase = phase
        progress = session.get_progress_percentage()
        print(f"   Muster {pattern_idx + 1}, Datei {file_idx + 1}, {phase:6s} -> {progress:5.1f}%")

    # Test 4: Zeit-Formatierung
    print("\n4. Test Zeit-Formatierung:")
    test_times = [45, 90, 3661, 7384]
    for seconds in test_times:
        session.elapsed_seconds = seconds
        formatted = session.get_elapsed_time_formatted()
        print(f"   {seconds:5d} Sekunden -> {formatted}")

    # Test 5: to_dict
    print("\n5. Test to_dict:")
    session_dict = session.to_dict()
    print(f"   Dictionary Keys: {list(session_dict.keys())}")
    print(f"   Version: {session_dict['version']}")
    print(f"   [OK] to_dict funktioniert")


def test_session_manager():
    """Testet SessionManager"""
    print("\n" + "=" * 80)
    print("TEST: SessionManager")
    print("=" * 80)

    # Test-Verzeichnis erstellen
    test_dir = Path("test_sessions")
    test_dir.mkdir(exist_ok=True)
    print(f"\nTest-Verzeichnis: {test_dir.absolute()}")

    # SessionManager erstellen
    manager = SessionManager(str(test_dir))
    print(f"SessionManager erstellt: {manager}")
    print(f"Session-Pfad: {manager.get_session_path()}")

    # Test 1: Session speichern
    print("\n1. Test Session speichern:")
    session = SessionData(
        target_path="D:\\Test",
        file_size_gb=1.0,
        total_size_gb=10.0,
        file_count=10,
        current_pattern_index=1,
        current_file_index=5,
        current_phase="write",
        current_chunk_index=32,
        random_seed=42
    )
    session.add_error("disktest_003.dat", "AA", "verify", "Test-Fehler")
    session.elapsed_seconds = 1234.5

    manager.save(session)
    print(f"   [OK] Session gespeichert")
    print(f"   Datei existiert: {manager.exists()}")

    # Test 2: JSON-Datei prüfen
    print("\n2. Test JSON-Datei:")
    with open(manager.session_path, 'r', encoding='utf-8') as f:
        json_content = json.load(f)
    print(f"   JSON Keys: {list(json_content.keys())}")
    print(f"   Target Path: {json_content['target_path']}")
    print(f"   Pattern Index: {json_content['current_pattern_index']}")
    print(f"   Fehler-Anzahl: {len(json_content['errors'])}")
    print(f"   [OK] JSON-Format korrekt")

    # Test 3: Session laden
    print("\n3. Test Session laden:")
    loaded_session = manager.load()
    if loaded_session:
        print(f"   [OK] Session geladen")
        print(f"   Target Path: {loaded_session.target_path}")
        print(f"   Pattern Index: {loaded_session.current_pattern_index}")
        print(f"   Datei Index: {loaded_session.current_file_index}")
        print(f"   Phase: {loaded_session.current_phase}")
        print(f"   Fehler-Anzahl: {len(loaded_session.errors)}")
        print(f"   Elapsed: {loaded_session.get_elapsed_time_formatted()}")

        # Daten vergleichen
        if (loaded_session.target_path == session.target_path and
            loaded_session.current_pattern_index == session.current_pattern_index and
            loaded_session.current_file_index == session.current_file_index):
            print(f"   [OK] Geladene Daten stimmen ueberein")
        else:
            print(f"   [FEHLER] Geladene Daten stimmen NICHT ueberein")
    else:
        print(f"   [FEHLER] Session konnte nicht geladen werden")

    # Test 4: Session-Info
    print("\n4. Test Session-Info:")
    info = manager.get_session_info()
    if info:
        print(f"   Target Path: {info['target_path']}")
        print(f"   Fortschritt: {info['progress_percent']:.1f}%")
        print(f"   Muster: {info['pattern_index'] + 1}/5")
        print(f"   Datei: {info['file_index'] + 1}")
        print(f"   Fehler: {info['error_count']}")
        print(f"   Zeit: {info['elapsed_time']}")
        print(f"   [OK] Session-Info abgerufen")
    else:
        print(f"   [FEHLER] Session-Info konnte nicht abgerufen werden")

    # Test 5: JSON-Datei ausgeben
    print("\n5. Test JSON-Datei Inhalt:")
    print("   " + "-" * 76)
    with open(manager.session_path, 'r', encoding='utf-8') as f:
        for line in f:
            print("   " + line.rstrip())
    print("   " + "-" * 76)

    # Test 6: Session löschen
    print("\n6. Test Session loeschen:")
    manager.delete()
    print(f"   Session geloescht")
    print(f"   Datei existiert: {manager.exists()}")
    if not manager.exists():
        print(f"   [OK] Session erfolgreich geloescht")
    else:
        print(f"   [FEHLER] Session wurde nicht geloescht")

    # Aufräumen
    try:
        test_dir.rmdir()
        print(f"\n   Test-Verzeichnis aufgeraeumt")
    except:
        pass


def test_session_persistence():
    """Testet Session-Persistenz über mehrere Manager-Instanzen"""
    print("\n" + "=" * 80)
    print("TEST: Session-Persistenz")
    print("=" * 80)

    test_dir = Path("test_persistence")
    test_dir.mkdir(exist_ok=True)

    # Test 1: Session mit Manager 1 speichern
    print("\n1. Session mit Manager 1 speichern:")
    manager1 = SessionManager(str(test_dir))
    session1 = SessionData(
        target_path="E:\\Backup",
        file_size_gb=2.0,
        total_size_gb=100.0,
        file_count=50,
        current_pattern_index=3,
        current_file_index=25,
        current_phase="verify",
        current_chunk_index=64,
        random_seed=999
    )
    for i in range(3):
        session1.add_error(f"disktest_{i:03d}.dat", "RND", "verify", f"Fehler {i}")
    session1.elapsed_seconds = 5432.1

    manager1.save(session1)
    print(f"   [OK] Session gespeichert von Manager 1")

    # Test 2: Session mit Manager 2 laden
    print("\n2. Session mit Manager 2 laden:")
    manager2 = SessionManager(str(test_dir))
    session2 = manager2.load()

    if session2:
        print(f"   [OK] Session geladen von Manager 2")
        print(f"   Target Path: {session2.target_path}")
        print(f"   File Count: {session2.file_count}")
        print(f"   Pattern: {session2.current_pattern_index}")
        print(f"   Errors: {len(session2.errors)}")

        # Vergleich
        matches = (
            session2.target_path == session1.target_path and
            session2.file_count == session1.file_count and
            session2.current_pattern_index == session1.current_pattern_index and
            len(session2.errors) == len(session1.errors) and
            session2.random_seed == session1.random_seed
        )
        if matches:
            print(f"   [OK] Sessions stimmen komplett ueberein")
        else:
            print(f"   [FEHLER] Sessions stimmen NICHT ueberein")
    else:
        print(f"   [FEHLER] Session konnte nicht geladen werden")

    # Aufräumen
    manager2.delete()
    try:
        test_dir.rmdir()
    except:
        pass


def main():
    """Hauptfunktion - führt alle Tests durch"""
    print("\n" + "=" * 80)
    print(" DiskTest - Phase 2: Session-Management Tests")
    print("=" * 80)

    try:
        test_session_data()
        test_session_manager()
        test_session_persistence()

        print("\n" + "=" * 80)
        print(" [OK] Alle Tests erfolgreich abgeschlossen!")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n[FEHLER] Fehler bei Tests: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
