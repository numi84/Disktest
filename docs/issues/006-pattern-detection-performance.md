# Issue #006: Pattern-Detection Performance-Optimierung

## Priorität: 🟢 Niedrig (Nice-to-have)

## Beschreibung
Die Pattern-Detection in `file_analyzer.py` iteriert für jedes Pattern über alle Sample-Bytes (1024 Bytes), was bei vielen Dateien ineffizient ist. Mit Sampling kann dies ~5x schneller werden.

## Betroffene Dateien
- `src/core/file_analyzer.py:124-171`

## Aktueller Code
```python
# file_analyzer.py:124-171
def _detect_pattern(self, filepath: Path) -> Optional[PatternType]:
    """Erkennt das Bitmuster einer Datei"""
    try:
        with open(filepath, 'rb') as f:
            sample = f.read(self.SAMPLE_SIZE)  # 1024 Bytes

        if len(sample) == 0:
            return None

        # 0x00 - Alle Bytes 0
        if all(b == 0x00 for b in sample):  # ⚠️ O(n) für jedes Pattern
            return PatternType.ZERO

        # 0xFF - Alle Bytes 1
        if all(b == 0xFF for b in sample):  # ⚠️ O(n)
            return PatternType.ONE

        # 0xAA
        if all(b == 0xAA for b in sample):  # ⚠️ O(n)
            return PatternType.ALT_AA

        # 0x55
        if all(b == 0x55 for b in sample):  # ⚠️ O(n)
            return PatternType.ALT_55

        # Random
        unique_bytes = len(set(sample))  # ⚠️ O(n)
        if unique_bytes > 10:
            return PatternType.RANDOM
```

## Problem-Analyse

### Worst-Case
- 5 Pattern-Checks à 1024 Bytes = 5120 Byte-Vergleiche
- Bei 100 Dateien: 512.000 Vergleiche

### Besser mit Early-Exit
- Prüfe nur ersten Chunk (100 Bytes)
- Bei Mismatch: Nächstes Pattern
- Nur bei Match: Validiere kompletten Sample

## Lösungsvorschlag

### Option 1: Sampling (Schnell & Einfach)

```python
def _detect_pattern(self, filepath: Path) -> Optional[PatternType]:
    """
    Erkennt das Bitmuster einer Datei mit optimiertem Sampling

    Strategie:
    1. Lese ersten Chunk (100 Bytes) für Quick-Check
    2. Bei potentiellem Match: Validiere mit weiteren Samples
    3. Early-Exit bei Mismatch
    """
    try:
        with open(filepath, 'rb') as f:
            # Quick-Check: Erste 100 Bytes
            quick_sample = f.read(100)

            if len(quick_sample) == 0:
                return None

            # Prüfe 0x00 (Null)
            if quick_sample == bytes(100):
                # Validiere mit weiterem Sample
                f.seek(500)  # Mitte der Datei
                mid_sample = f.read(100)
                if mid_sample == bytes(100):
                    return PatternType.ZERO

            # Prüfe 0xFF (Eins)
            if quick_sample == bytes([0xFF] * 100):
                f.seek(500)
                mid_sample = f.read(100)
                if mid_sample == bytes([0xFF] * 100):
                    return PatternType.ONE

            # Prüfe 0xAA
            if quick_sample == bytes([0xAA] * 100):
                f.seek(500)
                mid_sample = f.read(100)
                if mid_sample == bytes([0xAA] * 100):
                    return PatternType.ALT_AA

            # Prüfe 0x55
            if quick_sample == bytes([0x55] * 100):
                f.seek(500)
                mid_sample = f.read(100)
                if mid_sample == bytes([0x55] * 100):
                    return PatternType.ALT_55

            # Random: Prüfe Varianz
            # Lese mehr Samples für bessere Random-Erkennung
            f.seek(0)
            full_sample = f.read(self.SAMPLE_SIZE)
            unique_bytes = len(set(full_sample))
            if unique_bytes > 10:
                return PatternType.RANDOM

            return None

    except Exception as e:
        logger.warning(f"Fehler beim Lesen von {filepath}: {e}")
        return None
```

**Performance-Gewinn:** ~3x schneller (nur 200 Bytes statt 5x 1024 Bytes)

---

### Option 2: Byte-Array-Vergleich (Schnellster)

```python
def _detect_pattern(self, filepath: Path) -> Optional[PatternType]:
    """
    Erkennt Bitmuster mit optimierten Byte-Array-Vergleichen

    Nutzt memcmp-ähnliche Vergleiche statt Python-Loops
    """
    try:
        with open(filepath, 'rb') as f:
            sample = f.read(self.SAMPLE_SIZE)

        if len(sample) == 0:
            return None

        # Erstelle Pattern-Arrays (einmalig pro Aufruf)
        zero_pattern = bytes(len(sample))
        one_pattern = bytes([0xFF] * len(sample))
        aa_pattern = bytes([0xAA] * len(sample))
        ff_pattern = bytes([0x55] * len(sample))

        # Direkte Byte-Array-Vergleiche (sehr schnell in C)
        if sample == zero_pattern:
            return PatternType.ZERO

        if sample == one_pattern:
            return PatternType.ONE

        if sample == aa_pattern:
            return PatternType.ALT_AA

        if sample == ff_pattern:
            return PatternType.ALT_55

        # Random: Varianz-Check
        unique_bytes = len(set(sample))
        if unique_bytes > 10:
            return PatternType.RANDOM

        return None

    except Exception as e:
        logger.warning(f"Fehler beim Lesen von {filepath}: {e}")
        return None
```

**Performance-Gewinn:** ~5x schneller (memcmp ist in C implementiert)

---

### Option 3: Numpy (Wenn bereits als Dependency)

```python
import numpy as np

def _detect_pattern_numpy(self, filepath: Path) -> Optional[PatternType]:
    """
    Erkennt Bitmuster mit NumPy (sehr schnell für große Arrays)

    Note: Benötigt numpy als Dependency
    """
    try:
        with open(filepath, 'rb') as f:
            sample = np.fromfile(f, dtype=np.uint8, count=self.SAMPLE_SIZE)

        if len(sample) == 0:
            return None

        # NumPy-Vergleiche (SIMD-optimiert)
        if np.all(sample == 0x00):
            return PatternType.ZERO

        if np.all(sample == 0xFF):
            return PatternType.ONE

        if np.all(sample == 0xAA):
            return PatternType.ALT_AA

        if np.all(sample == 0x55):
            return PatternType.ALT_55

        # Random: Unique-Count
        if len(np.unique(sample)) > 10:
            return PatternType.RANDOM

        return None

    except Exception as e:
        logger.warning(f"Fehler beim Lesen von {filepath}: {e}")
        return None
```

**Performance-Gewinn:** ~10x schneller (SIMD-Optimierung), aber Numpy-Dependency

---

## Empfehlung

**Option 2 (Byte-Array-Vergleich)** ist der beste Kompromiss:
- ✅ Keine zusätzlichen Dependencies
- ✅ ~5x Performance-Gewinn
- ✅ Code bleibt einfach
- ✅ Python's `bytes ==` nutzt memcmp (C-Level)

## Benchmark

```python
# benchmark_pattern_detection.py
import time
from pathlib import Path
from core.file_analyzer import FileAnalyzer

def benchmark_pattern_detection():
    """Benchmark verschiedener Pattern-Detection Varianten"""
    # Erstelle Testdateien
    test_dir = Path("benchmark_test")
    test_dir.mkdir(exist_ok=True)

    patterns = {
        'zero': bytes(1024 * 1024),  # 1 MB Null
        'one': bytes([0xFF] * 1024 * 1024),
        'aa': bytes([0xAA] * 1024 * 1024),
        'random': os.urandom(1024 * 1024)
    }

    for name, data in patterns.items():
        filepath = test_dir / f"test_{name}.dat"
        with open(filepath, 'wb') as f:
            f.write(data)

    # Benchmark
    analyzer = FileAnalyzer(str(test_dir), 1.0)

    iterations = 100
    start = time.time()
    for _ in range(iterations):
        analyzer.analyze_existing_files()
    elapsed = time.time() - start

    print(f"Pattern-Detection: {elapsed:.2f}s für {iterations} Iterationen")
    print(f"Durchschnitt: {elapsed/iterations*1000:.2f}ms pro Iteration")

    # Cleanup
    import shutil
    shutil.rmtree(test_dir)

if __name__ == '__main__':
    benchmark_pattern_detection()
```

**Erwartete Ergebnisse:**
- Aktuell (all()): ~50ms pro Iteration
- Mit Byte-Array: ~10ms pro Iteration
- Mit Numpy: ~5ms pro Iteration

## Testing

```python
# test_pattern_detection.py
import pytest
from pathlib import Path
from core.file_analyzer import FileAnalyzer
from core.patterns import PatternType

@pytest.fixture
def test_files(tmp_path):
    """Erstellt Testdateien mit verschiedenen Patterns"""
    files = {}

    # 0x00
    zero_file = tmp_path / "test_zero.dat"
    with open(zero_file, 'wb') as f:
        f.write(bytes(4096))
    files['zero'] = zero_file

    # 0xFF
    one_file = tmp_path / "test_one.dat"
    with open(one_file, 'wb') as f:
        f.write(bytes([0xFF] * 4096))
    files['one'] = one_file

    # 0xAA
    aa_file = tmp_path / "test_aa.dat"
    with open(aa_file, 'wb') as f:
        f.write(bytes([0xAA] * 4096))
    files['aa'] = aa_file

    # 0x55
    ff_file = tmp_path / "test_55.dat"
    with open(ff_file, 'wb') as f:
        f.write(bytes([0x55] * 4096))
    files['55'] = ff_file

    # Random
    random_file = tmp_path / "test_random.dat"
    with open(random_file, 'wb') as f:
        f.write(os.urandom(4096))
    files['random'] = random_file

    return files

def test_pattern_detection_accuracy(test_files):
    """Test dass alle Pattern korrekt erkannt werden"""
    analyzer = FileAnalyzer(".", 1.0)

    assert analyzer._detect_pattern(test_files['zero']) == PatternType.ZERO
    assert analyzer._detect_pattern(test_files['one']) == PatternType.ONE
    assert analyzer._detect_pattern(test_files['aa']) == PatternType.ALT_AA
    assert analyzer._detect_pattern(test_files['55']) == PatternType.ALT_55
    assert analyzer._detect_pattern(test_files['random']) == PatternType.RANDOM

def test_pattern_detection_empty_file(tmp_path):
    """Test dass leere Dateien korrekt behandelt werden"""
    empty_file = tmp_path / "empty.dat"
    empty_file.touch()

    analyzer = FileAnalyzer(".", 1.0)
    assert analyzer._detect_pattern(empty_file) is None
```

## Migration

1. Implementiere neue `_detect_pattern()` Methode
2. Führe Benchmark durch (verify Performance-Gewinn)
3. Führe Tests durch (verify Korrektheit)
4. Ersetze alte Methode
5. Dokumentiere Änderung im CHANGELOG

## Zeitaufwand
- Implementierung: 30 Min
- Benchmark: 30 Min
- Tests: 30 Min
- Dokumentation: 15 Min
**Gesamt:** ~2 Stunden

## Nutzen
- ⚠️ Sehr gering für kleine Dateianzahlen (< 50 Dateien)
- ✅ Merkbar bei vielen Dateien (> 100 Dateien)
- ✅ Wichtig für File-Recovery mit hunderten Dateien

→ **Nice-to-have, aber nicht kritisch**
