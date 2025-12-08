"""
End-to-End Test für DiskTest

Testet die vollständige Anwendung mit einem echten, aber kleinen Test.
"""

import sys
import tempfile
import shutil
import time
from pathlib import Path

# Füge src zum Python-Path hinzu
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from core.test_engine import TestEngine, TestConfig
from core.session import SessionManager
from core.file_manager import FileManager


class E2ETest:
    """End-to-End Test Runner"""

    def __init__(self):
        self.temp_dir = None
        self.engine = None
        self.errors = []
        self.test_results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'details': []
        }

    def setup(self):
        """Test-Setup: Temporäres Verzeichnis erstellen"""
        print("\n" + "="*70)
        print("DISKTEST - END-TO-END TEST")
        print("="*70)
        print("\nSetup...")

        self.temp_dir = tempfile.mkdtemp(prefix="disktest_e2e_")
        print(f"[OK] Temporaeres Verzeichnis erstellt: {self.temp_dir}")

    def teardown(self):
        """Test-Cleanup: Temporäres Verzeichnis löschen"""
        print("\nCleanup...")
        if self.temp_dir and Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir)
                print(f"[OK] Temporaeres Verzeichnis geloescht")
            except Exception as e:
                print(f"[FEHLER] Fehler beim Loeschen: {e}")

    def assert_true(self, condition, test_name):
        """Helper: Assertion mit Logging"""
        self.test_results['total_tests'] += 1

        if condition:
            self.test_results['passed'] += 1
            print(f"  [PASS] {test_name}")
            self.test_results['details'].append((test_name, 'PASSED', ''))
        else:
            self.test_results['failed'] += 1
            print(f"  [FAIL] {test_name}")
            self.test_results['details'].append((test_name, 'FAILED', 'Assertion failed'))

    def assert_equal(self, actual, expected, test_name):
        """Helper: Gleichheits-Assertion"""
        self.test_results['total_tests'] += 1

        if actual == expected:
            self.test_results['passed'] += 1
            print(f"  [PASS] {test_name}")
            self.test_results['details'].append((test_name, 'PASSED', ''))
        else:
            self.test_results['failed'] += 1
            print(f"  [FAIL] {test_name}: Expected {expected}, got {actual}")
            self.test_results['details'].append(
                (test_name, 'FAILED', f'Expected {expected}, got {actual}')
            )

    def test_1_small_write_verify_cycle(self):
        """Test 1: Kleiner Write-Verify Zyklus"""
        print("\n--- Test 1: Kleiner Write-Verify Zyklus ---")

        # Sehr kleine Konfiguration: 100 MB gesamt, 50 MB pro Datei = 2 Dateien
        config = TestConfig(
            target_path=self.temp_dir,
            file_size_gb=0.05,  # 50 MB
            total_size_gb=0.1,  # 100 MB
        )

        # Tracking
        progress_updates = []
        log_entries = []
        errors = []
        patterns_seen = []
        phases_seen = []

        # Engine erstellen und Signals verbinden
        self.engine = TestEngine(config)

        self.engine.progress_updated.connect(
            lambda c, t, s: progress_updates.append((c, t, s))
        )
        self.engine.log_entry.connect(
            lambda msg: log_entries.append(msg)
        )
        self.engine.error_occurred.connect(
            lambda err: errors.append(err)
        )
        self.engine.pattern_changed.connect(
            lambda idx, name: patterns_seen.append((idx, name))
        )
        self.engine.phase_changed.connect(
            lambda phase: phases_seen.append(phase)
        )

        # Engine starten und warten
        print("  Starte Test-Engine...")
        start_time = time.time()
        self.engine.start()
        self.engine.wait()  # Warten bis abgeschlossen
        elapsed = time.time() - start_time

        print(f"  Test abgeschlossen nach {elapsed:.1f}s")

        # Assertions
        self.assert_true(len(progress_updates) > 0, "Progress-Updates empfangen")
        self.assert_true(len(log_entries) > 0, "Log-Einträge empfangen")
        self.assert_equal(len(errors), 0, "Keine Fehler aufgetreten")
        self.assert_equal(len(patterns_seen), 5, "Alle 5 Muster durchlaufen")

        # Prüfen ob Testdateien existieren
        file_manager = FileManager(self.temp_dir, 0.05)
        file_count = file_manager.count_existing_files()
        self.assert_equal(file_count, 2, "2 Testdateien erstellt")

        # Dateigröße prüfen
        expected_size = 2 * 0.05 * 1024 * 1024 * 1024  # 2 Dateien × 50 MB
        actual_size = file_manager.get_existing_files_size()
        size_diff = abs(actual_size - expected_size)
        self.assert_true(
            size_diff < 1024 * 1024,  # Max 1 MB Abweichung
            f"Dateigröße korrekt (~{actual_size / 1024 / 1024:.1f} MB)"
        )

    def test_2_session_save_and_restore(self):
        """Test 2: Session Speichern und Wiederherstellen"""
        print("\n--- Test 2: Session Speichern und Wiederherstellen ---")

        # Session erstellen und speichern
        from core.session import SessionData
        session_manager = SessionManager(self.temp_dir)

        session = SessionData(
            target_path=self.temp_dir,
            file_size_gb=0.05,
            total_size_gb=0.1,
            file_count=2,
            current_pattern_index=2,
            current_file_index=1,
            current_phase="verify",
            current_chunk_index=5,
            random_seed=12345
        )

        session.add_error("test.dat", "0xFF", "verify", "Test-Fehler")

        # Speichern
        try:
            session_manager.save(session)
            self.assert_true(True, "Session gespeichert")
        except Exception as e:
            self.assert_true(False, f"Session speichern: {e}")

        # Prüfen ob Datei existiert
        session_file = Path(self.temp_dir) / "disktest_session.json"
        self.assert_true(session_file.exists(), "Session-Datei existiert")

        # Laden
        try:
            loaded_session = session_manager.load()
            self.assert_true(True, "Session geladen")
        except Exception as e:
            self.assert_true(False, f"Session laden: {e}")
            return

        # Vergleichen
        self.assert_equal(
            loaded_session.current_pattern_index,
            2,
            "Pattern-Index korrekt"
        )
        self.assert_equal(
            loaded_session.current_file_index,
            1,
            "File-Index korrekt"
        )
        self.assert_equal(
            loaded_session.current_phase,
            "verify",
            "Phase korrekt"
        )
        self.assert_equal(
            loaded_session.random_seed,
            12345,
            "Random-Seed korrekt"
        )
        self.assert_equal(
            len(loaded_session.errors),
            1,
            "Fehler gespeichert"
        )

        # Löschen
        try:
            session_manager.delete()
            self.assert_true(True, "Session gelöscht")
        except Exception as e:
            self.assert_true(False, f"Session löschen: {e}")

        self.assert_true(
            not session_file.exists(),
            "Session-Datei gelöscht"
        )

    def test_3_file_deletion(self):
        """Test 3: Dateien löschen"""
        print("\n--- Test 3: Dateien löschen ---")

        file_manager = FileManager(self.temp_dir, 0.05)

        # Vor dem Löschen
        count_before = file_manager.count_existing_files()
        self.assert_true(count_before > 0, f"{count_before} Testdateien vorhanden")

        # Löschen (FileManager hat delete_all_files in einer neueren Version)
        try:
            if hasattr(file_manager, 'delete_all_files'):
                deleted = file_manager.delete_all_files()
            else:
                # Manuell löschen wenn Methode nicht existiert
                pattern = f"{file_manager.FILE_PREFIX}*{file_manager.FILE_SUFFIX}"
                files = list(file_manager.target_path.glob(pattern))
                for f in files:
                    f.unlink()
                deleted = len(files)

            self.assert_equal(deleted, count_before, f"{deleted} Dateien gelöscht")
        except Exception as e:
            self.assert_true(False, f"Dateien löschen: {e}")

        # Nach dem Löschen
        count_after = file_manager.count_existing_files()
        self.assert_equal(count_after, 0, "Alle Testdateien gelöscht")

    def test_4_pattern_verification(self):
        """Test 4: Pattern-Generator Verifikation"""
        print("\n--- Test 4: Pattern-Generator Verifikation ---")

        from core.patterns import PatternGenerator, PatternType

        # Test 0x00
        gen = PatternGenerator(PatternType.ZERO)
        chunk = gen.generate_chunk(1024)
        self.assert_true(
            all(b == 0x00 for b in chunk),
            "0x00 Pattern korrekt"
        )

        # Test 0xFF
        gen = PatternGenerator(PatternType.ONE)
        chunk = gen.generate_chunk(1024)
        self.assert_true(
            all(b == 0xFF for b in chunk),
            "0xFF Pattern korrekt"
        )

        # Test 0xAA
        gen = PatternGenerator(PatternType.ALT_AA)
        chunk = gen.generate_chunk(1024)
        self.assert_true(
            all(b == 0xAA for b in chunk),
            "0xAA Pattern korrekt"
        )

        # Test 0x55
        gen = PatternGenerator(PatternType.ALT_55)
        chunk = gen.generate_chunk(1024)
        self.assert_true(
            all(b == 0x55 for b in chunk),
            "0x55 Pattern korrekt"
        )

        # Test Random reproduzierbar
        gen1 = PatternGenerator(PatternType.RANDOM, seed=42)
        gen2 = PatternGenerator(PatternType.RANDOM, seed=42)

        chunk1 = gen1.generate_chunk(1024)
        chunk2 = gen2.generate_chunk(1024)

        self.assert_true(
            chunk1 == chunk2,
            "Random Pattern reproduzierbar mit gleichem Seed"
        )

        # Reset testen
        gen1.reset()
        chunk1_again = gen1.generate_chunk(1024)
        self.assert_true(
            chunk1 == chunk1_again,
            "Random Pattern nach Reset identisch"
        )

    def test_5_disk_info(self):
        """Test 5: DiskInfo Funktionalität"""
        print("\n--- Test 5: DiskInfo Funktionalität ---")

        from utils.disk_info import DiskInfo

        # DiskInfo ist eine statische Klasse
        free = DiskInfo.get_free_space(self.temp_dir)
        total = DiskInfo.get_total_space(self.temp_dir)
        used = DiskInfo.get_used_space(self.temp_dir)

        # Prüfen ob Werte sinnvoll sind
        self.assert_true(total > 0, "Gesamtspeicher > 0")
        self.assert_true(free > 0, "Freier Speicher > 0")
        self.assert_true(used >= 0, "Belegter Speicher >= 0")
        self.assert_true(
            total >= free,
            "Total >= Free"
        )

        # Formatierung testen
        free_formatted = DiskInfo.format_bytes(free)
        self.assert_true(
            "GB" in free_formatted or "TB" in free_formatted or "MB" in free_formatted,
            f"Groesse korrekt formatiert: {free_formatted}"
        )

    def test_6_logger(self):
        """Test 6: Logger Funktionalität"""
        print("\n--- Test 6: Logger Funktionalität ---")

        from utils.logger import DiskTestLogger

        logger = DiskTestLogger(self.temp_dir)

        # Log-Einträge schreiben
        logger.info("Test Info")
        logger.success("Test Success")
        logger.warning("Test Warning")
        logger.error("Test Error")

        # Prüfen ob Log-Datei existiert
        log_files = list(Path(self.temp_dir).glob("disktest_*.log"))
        self.assert_true(len(log_files) > 0, "Log-Datei erstellt")

        if log_files:
            # Log-Datei lesen und prüfen
            log_content = log_files[0].read_text(encoding='utf-8')
            self.assert_true("Test Info" in log_content, "INFO geloggt")
            self.assert_true("Test Success" in log_content, "SUCCESS geloggt")
            self.assert_true("Test Warning" in log_content, "WARNING geloggt")
            self.assert_true("Test Error" in log_content, "ERROR geloggt")

    def print_summary(self):
        """Druckt Test-Zusammenfassung"""
        print("\n" + "="*70)
        print("TEST-ZUSAMMENFASSUNG")
        print("="*70)
        print(f"Total Tests:  {self.test_results['total_tests']}")
        print(f"Passed:       {self.test_results['passed']}")
        print(f"Failed:       {self.test_results['failed']}")

        success_rate = (self.test_results['passed'] / self.test_results['total_tests'] * 100
                       if self.test_results['total_tests'] > 0 else 0)
        print(f"Success Rate: {success_rate:.1f}%")

        if self.test_results['failed'] > 0:
            print("\nFailed Tests:")
            for name, status, details in self.test_results['details']:
                if status == 'FAILED':
                    print(f"  [FAIL] {name}")
                    if details:
                        print(f"    {details}")

        print("="*70)

        if self.test_results['failed'] == 0:
            print("\n*** ALLE TESTS BESTANDEN! ***\n")
            return True
        else:
            print(f"\n*** {self.test_results['failed']} TESTS FEHLGESCHLAGEN ***\n")
            return False

    def run_all_tests(self):
        """Führt alle Tests aus"""
        try:
            self.setup()

            # Tests ausführen
            self.test_1_small_write_verify_cycle()
            self.test_2_session_save_and_restore()
            self.test_3_file_deletion()
            self.test_4_pattern_verification()
            self.test_5_disk_info()
            self.test_6_logger()

            # Zusammenfassung
            success = self.print_summary()

            return 0 if success else 1

        except Exception as e:
            print(f"\n[ERROR] KRITISCHER FEHLER: {e}")
            import traceback
            traceback.print_exc()
            return 2

        finally:
            self.teardown()


def main():
    """Hauptfunktion"""
    # QApplication für QThread-Support (Engine ist ein QThread)
    app = QApplication(sys.argv)

    # Test ausführen
    test = E2ETest()
    exit_code = test.run_all_tests()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
