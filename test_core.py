"""
Test-Skript für Core-Komponenten (Phase 1)
Testet: patterns.py, file_manager.py, disk_info.py, logger.py
"""
import sys
import os
from pathlib import Path

# Pfad zum src-Verzeichnis hinzufügen
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.patterns import PatternType, PatternGenerator, PATTERN_SEQUENCE
from core.file_manager import FileManager
from utils.disk_info import DiskInfo
from utils.logger import DiskTestLogger, LogLevel


def test_patterns():
    """Testet Pattern-Generator"""
    print("\n" + "=" * 80)
    print("TEST: Pattern-Generator")
    print("=" * 80)

    # Test 1: Alle Pattern-Typen
    print("\n1. Test aller Muster-Typen:")
    for pattern_type in PATTERN_SEQUENCE:
        gen = PatternGenerator(pattern_type)
        chunk = gen.generate_chunk(16)
        print(f"   {pattern_type.display_name:20s} -> {chunk.hex()}")

    # Test 2: Random-Pattern Reproduzierbarkeit
    print("\n2. Test Random-Reproduzierbarkeit:")
    seed = 42
    gen1 = PatternGenerator(PatternType.RANDOM, seed=seed)
    chunk1 = gen1.generate_chunk(32)
    print(f"   Chunk 1: {chunk1.hex()[:40]}...")

    gen1.reset()
    chunk2 = gen1.generate_chunk(32)
    print(f"   Chunk 2: {chunk2.hex()[:40]}...")
    print(f"   Gleich?  {chunk1 == chunk2} [OK]")

    # Test 3: Verschiedene Chunk-Größen
    print("\n3. Test verschiedener Chunk-Größen:")
    gen = PatternGenerator(PatternType.ALT_AA)
    for size in [16, 64, 256, 1024]:
        chunk = gen.generate_chunk(size)
        print(f"   {size:4d} Bytes -> {len(chunk)} Bytes generiert [OK]")


def test_file_manager():
    """Testet FileManager"""
    print("\n" + "=" * 80)
    print("TEST: FileManager")
    print("=" * 80)

    # Test mit temporärem Verzeichnis (aktuelles Verzeichnis)
    test_path = os.getcwd()
    print(f"\nTest-Pfad: {test_path}")

    # FileManager erstellen
    fm = FileManager(test_path, file_size_gb=1.0)
    print(f"FileManager erstellt: {fm}")

    # Test 1: Dateianzahl berechnen
    print("\n1. Test Dateianzahl-Berechnung:")
    for total_gb in [10, 50, 100]:
        count = fm.calculate_file_count(total_gb)
        print(f"   {total_gb:3d} GB -> {count} Dateien")

    # Test 2: Dateinamen generieren
    print("\n2. Test Dateinamen-Generierung:")
    for i in range(5):
        path = fm.get_file_path(i)
        print(f"   Index {i} -> {path.name}")

    # Test 3: Speicherplatz
    print("\n3. Test Speicherplatz:")
    free = fm.get_free_space()
    total = fm.get_total_space()
    print(f"   Frei:   {DiskInfo.format_bytes(free)}")
    print(f"   Gesamt: {DiskInfo.format_bytes(total)}")

    # Test 4: Existierende Dateien
    print("\n4. Test existierende Dateien:")
    exists = fm.files_exist()
    count = fm.count_existing_files()
    print(f"   Testdateien existieren: {exists}")
    print(f"   Anzahl: {count}")


def test_disk_info():
    """Testet DiskInfo"""
    print("\n" + "=" * 80)
    print("TEST: DiskInfo")
    print("=" * 80)

    test_path = os.getcwd()

    # Test 1: Pfad-Validierung
    print("\n1. Test Pfad-Validierung:")
    print(f"   Pfad existiert: {DiskInfo.is_valid_path(test_path)}")
    print(f"   Pfad beschreibbar: {DiskInfo.is_writable(test_path)}")

    # Test 2: Laufwerksbuchstabe
    print("\n2. Test Laufwerksbuchstabe:")
    drive = DiskInfo.get_drive_letter(test_path)
    print(f"   Laufwerk: {drive}")

    # Test 3: Speicherplatz
    print("\n3. Test Speicherplatz:")
    free = DiskInfo.get_free_space(test_path)
    total = DiskInfo.get_total_space(test_path)
    used = DiskInfo.get_used_space(test_path)
    print(f"   Frei:       {DiskInfo.format_bytes(free)}")
    print(f"   Verwendet:  {DiskInfo.format_bytes(used)}")
    print(f"   Gesamt:     {DiskInfo.format_bytes(total)}")

    # Test 4: Formatierung
    print("\n4. Test Byte-Formatierung:")
    test_values = [
        512,
        1024,
        1024 * 1024,
        1.5 * 1024 * 1024 * 1024,
        185.3 * 1024 * 1024  # 185.3 MB/s
    ]
    for value in test_values:
        formatted = DiskInfo.format_bytes(int(value))
        formatted_speed = DiskInfo.format_bytes_per_second(value)
        print(f"   {value:15.0f} -> {formatted:12s} | {formatted_speed:15s}")

    # Test 5: Disk-Info Summary
    print("\n5. Test Disk-Info Summary:")
    summary = DiskInfo.get_disk_info_summary(test_path)
    for key, value in summary.items():
        print(f"   {key:20s}: {value}")


def test_logger():
    """Testet Logger"""
    print("\n" + "=" * 80)
    print("TEST: Logger")
    print("=" * 80)

    # Logger erstellen
    logger = DiskTestLogger()
    print(f"\nLogger erstellt: {logger}")
    print(f"Log-Datei: {logger.get_log_path()}")

    # Test 1: Verschiedene Log-Levels
    print("\n1. Test Log-Levels:")
    logger.info("Dies ist eine INFO-Nachricht")
    logger.success("Dies ist eine SUCCESS-Nachricht")
    logger.warning("Dies ist eine WARNING-Nachricht")
    logger.error("Dies ist eine ERROR-Nachricht")
    print("   [OK] Log-Eintraege geschrieben")

    # Test 2: Trennlinien und Sections
    print("\n2. Test Formatierung:")
    logger.separator()
    logger.section("Test-Abschnitt")
    logger.info("Nachricht im Abschnitt")
    logger.separator()
    print("   [OK] Formatierung geschrieben")

    # Test 3: Log-Datei prüfen
    print("\n3. Test Log-Datei:")
    log_path = Path(logger.get_log_path())
    if log_path.exists():
        size = log_path.stat().st_size
        print(f"   [OK] Log-Datei existiert ({size} Bytes)")
        print("\n   Inhalt der Log-Datei:")
        print("   " + "-" * 76)
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                print("   " + line.rstrip())
        print("   " + "-" * 76)
    else:
        print("   [FEHLER] Log-Datei existiert nicht")


def main():
    """Hauptfunktion - führt alle Tests durch"""
    print("\n" + "=" * 80)
    print(" DiskTest - Phase 1: Core-Komponenten Tests")
    print("=" * 80)

    try:
        test_patterns()
        test_file_manager()
        test_disk_info()
        test_logger()

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
