# Issue #003: Fehlende Input-Validierung

## Status: ✅ Erledigt (2025-12-15)

## Priorität: 🟠 Hoch

## Beschreibung
Mehrere Methoden validieren ihre Eingaben nicht ausreichend, was zu Division-by-Zero, negativen Indizes oder ungültigen Parametern führen kann.

## Betroffene Dateien
1. `src/core/file_manager.py:46-61`
2. `src/core/file_manager.py:63-75`

## Problem 1: Division by Zero

### Aktueller Code
```python
# file_manager.py:46-61
def calculate_file_count(self, total_size_gb: float) -> int:
    if total_size_gb <= 0:
        raise ValueError("Gesamtgröße muss größer als 0 sein")

    count = int(total_size_gb / self.file_size_gb)  # ⚠️ Keine Prüfung von file_size_gb!
    return max(1, count)
```

### Problem
Wenn `self.file_size_gb` = 0 oder negativ:
- Division by Zero → `ZeroDivisionError`
- Constructor validiert dies nicht

### Lösung
```python
def __init__(self, target_path: str, file_size_gb: float):
    """
    Initialisiert den FileManager

    Args:
        target_path: Zielpfad für Testdateien
        file_size_gb: Größe einer einzelnen Testdatei in GB

    Raises:
        ValueError: Wenn Parameter ungültig sind
    """
    # Validierung
    if file_size_gb <= 0:
        raise ValueError(f"Dateigröße muss größer als 0 sein, ist: {file_size_gb}")

    if file_size_gb > 10240:  # 10 TB Limit
        raise ValueError(f"Dateigröße zu groß (max 10 TB), ist: {file_size_gb} GB")

    self.target_path = Path(target_path)
    self.file_size_gb = file_size_gb
    self.file_size_bytes = int(file_size_gb * 1024 * 1024 * 1024)

    # Path-Validierung
    if not self.target_path.exists():
        raise ValueError(f"Pfad existiert nicht: {target_path}")
    if not self.target_path.is_dir():
        raise ValueError(f"Pfad ist kein Verzeichnis: {target_path}")

def calculate_file_count(self, total_size_gb: float) -> int:
    """
    Berechnet die Anzahl der benötigten Testdateien

    Args:
        total_size_gb: Gewünschte Gesamtgröße des Tests in GB

    Returns:
        int: Anzahl der Testdateien (mindestens 1)

    Raises:
        ValueError: Wenn total_size_gb ungültig ist
    """
    if total_size_gb <= 0:
        raise ValueError(f"Gesamtgröße muss größer als 0 sein, ist: {total_size_gb}")

    if total_size_gb > 100000:  # 100 TB Limit
        raise ValueError(f"Gesamtgröße zu groß (max 100 TB), ist: {total_size_gb} GB")

    # file_size_gb wurde bereits im Constructor validiert, also kein Division-by-Zero möglich
    count = int(total_size_gb / self.file_size_gb)
    return max(1, count)
```

## Problem 2: Negativer Index

### Aktueller Code
```python
# file_manager.py:63-75
def get_file_path(self, index: int) -> Path:
    """
    Generiert den Pfad für eine Testdatei

    Args:
        index: Index der Datei (0-basiert)

    Returns:
        Path: Vollständiger Pfad zur Testdatei
    """
    # Index ist 0-basiert, aber Dateinamen starten bei 001
    filename = f"{self.FILE_PREFIX}{index + 1:03d}{self.FILE_SUFFIX}"  # ⚠️ Bei index=-1 → disktest_000.dat
    return self.target_path / filename
```

### Problem
- Bei `index = -1` → `disktest_000.dat`
- Bei `index = -2` → `disktest_-01.dat` (ungültiger Dateiname)
- Keine Obergrenze geprüft

### Lösung
```python
def get_file_path(self, index: int) -> Path:
    """
    Generiert den Pfad für eine Testdatei

    Args:
        index: Index der Datei (0-basiert, 0-999)

    Returns:
        Path: Vollständiger Pfad zur Testdatei

    Raises:
        ValueError: Wenn Index außerhalb des gültigen Bereichs
    """
    if index < 0:
        raise ValueError(f"Index muss >= 0 sein, ist: {index}")

    if index > 999:
        raise ValueError(
            f"Index zu groß (max 999 für 3-stellige Nummern), ist: {index}\n"
            f"Tipp: Nutze größere Dateigrößen statt mehr Dateien"
        )

    # Index ist 0-basiert, aber Dateinamen starten bei 001
    filename = f"{self.FILE_PREFIX}{index + 1:03d}{self.FILE_SUFFIX}"
    return self.target_path / filename
```

## Problem 3: Fehlende Validierung in file_analyzer.py

### Aktueller Code
```python
# file_analyzer.py:80-95
def _extract_file_index(self, filename: str) -> int:
    """Extrahiert Index aus Dateinamen"""
    if not filename.startswith("disktest_") or not filename.endswith(".dat"):
        raise ValueError(f"Ungültiger Dateiname: {filename}")

    index_str = filename[9:-4]  # "042"
    return int(index_str)  # ⚠️ Kann ValueError werfen wenn nicht numerisch
```

### Lösung
```python
def _extract_file_index(self, filename: str) -> int:
    """
    Extrahiert Index aus Dateinamen

    Args:
        filename: z.B. "disktest_042.dat"

    Returns:
        int: Index (z.B. 42)

    Raises:
        ValueError: Wenn Dateiname ungültiges Format hat
    """
    if not filename.startswith("disktest_") or not filename.endswith(".dat"):
        raise ValueError(f"Ungültiger Dateiname: {filename}")

    index_str = filename[9:-4]  # "042"

    try:
        index = int(index_str)
    except ValueError:
        raise ValueError(f"Index ist nicht numerisch: {index_str} in {filename}")

    if index < 1 or index > 999:
        raise ValueError(f"Index außerhalb gültigem Bereich (1-999): {index} in {filename}")

    return index
```

## Testing

### Unit Tests hinzufügen
```python
# test_file_manager.py
import pytest
from core.file_manager import FileManager

def test_file_manager_invalid_file_size():
    """Test dass FileManager ungültige Dateigrößen ablehnt"""
    with pytest.raises(ValueError, match="größer als 0"):
        FileManager(".", 0)

    with pytest.raises(ValueError, match="größer als 0"):
        FileManager(".", -1)

    with pytest.raises(ValueError, match="zu groß"):
        FileManager(".", 20000)  # 20 TB

def test_calculate_file_count_invalid():
    """Test dass calculate_file_count ungültige Werte ablehnt"""
    fm = FileManager(".", 1.0)

    with pytest.raises(ValueError, match="größer als 0"):
        fm.calculate_file_count(0)

    with pytest.raises(ValueError, match="größer als 0"):
        fm.calculate_file_count(-10)

    with pytest.raises(ValueError, match="zu groß"):
        fm.calculate_file_count(200000)  # 200 TB

def test_get_file_path_negative_index():
    """Test dass negative Indizes abgelehnt werden"""
    fm = FileManager(".", 1.0)

    with pytest.raises(ValueError, match="Index muss >= 0"):
        fm.get_file_path(-1)

    with pytest.raises(ValueError, match="Index muss >= 0"):
        fm.get_file_path(-100)

def test_get_file_path_too_large_index():
    """Test dass zu große Indizes abgelehnt werden"""
    fm = FileManager(".", 1.0)

    with pytest.raises(ValueError, match="Index zu groß"):
        fm.get_file_path(1000)

    with pytest.raises(ValueError, match="Index zu groß"):
        fm.get_file_path(9999)

def test_extract_file_index_invalid():
    """Test dass ungültige Dateinamen abgelehnt werden"""
    from core.file_analyzer import FileAnalyzer

    analyzer = FileAnalyzer(".", 1.0)

    # Nicht-numerischer Index
    with pytest.raises(ValueError, match="nicht numerisch"):
        analyzer._extract_file_index("disktest_abc.dat")

    # Index außerhalb Bereich
    with pytest.raises(ValueError, match="außerhalb"):
        analyzer._extract_file_index("disktest_000.dat")

    with pytest.raises(ValueError, match="außerhalb"):
        analyzer._extract_file_index("disktest_1000.dat")
```

## Lösung implementiert ✅

**Commit:** 82f6339 - "Fix Issue #003: Input-Validierung hinzugefuegt"

Alle Validierungen wurden erfolgreich implementiert:

1. ✅ **FileManager.__init__** - Dateigröße-Validierung (0 < size <= 10 TB)
2. ✅ **FileManager.calculate_file_count** - Gesamtgröße-Validierung (0 < size <= 100 TB)
3. ✅ **FileManager.get_file_path** - Index-Validierung (0 <= index <= 999)
4. ✅ **FileAnalyzer._extract_file_index** - Numerische & Bereichs-Validierung (1-999)

**Tests:** Alle Validierungen wurden manuell getestet und funktionieren korrekt.

## Referenzen
- Python ValueError: https://docs.python.org/3/library/exceptions.html#ValueError
- Input Validation Best Practices: https://owasp.org/www-project-proactive-controls/v3/en/c5-validate-inputs
