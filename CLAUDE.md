# DiskTest - Projektübersicht

## Was ist DiskTest?

DiskTest ist eine Windows-Desktop-Anwendung für nicht-destruktive Festplattentests. Inspiriert von Linux `badblocks`, arbeitet es jedoch auf Dateisystem-Ebene mit Testdateien statt auf Raw-Device-Ebene.

## Kernkonzept

- Erstellt Testdateien auf einem bestehenden Dateisystem
- Schreibt verschiedene Bitmuster und verifiziert diese durch Zurücklesen
- Keine Zerstörung bestehender Daten
- Kein Administrator-Zugriff erforderlich

## Technologie-Stack

- **Sprache:** Python 3.11+
- **GUI-Framework:** PySide6
- **Zielplattform:** Windows (private Nutzung)

## Projektstruktur

```
disktest/
├── CLAUDE.md              # Diese Datei
├── ARCHITECTURE.md        # Technische Architektur
├── FEATURES.md            # Feature-Spezifikation
├── UI-SPEC.md             # GUI-Spezifikation
└── src/
    ├── main.py            # Einstiegspunkt
    ├── gui/
    │   ├── __init__.py
    │   ├── main_window.py # Hauptfenster
    │   └── widgets.py     # Custom Widgets
    ├── core/
    │   ├── __init__.py
    │   ├── test_engine.py # Test-Logik
    │   ├── patterns.py    # Bitmuster-Generierung
    │   ├── file_manager.py# Testdatei-Verwaltung
    │   └── session.py     # Session-Management
    ├── utils/
    │   ├── __init__.py
    │   ├── logger.py      # Logging
    │   └── disk_info.py   # Laufwerksinformationen
    └── resources/
        └── icons/         # App-Icons
```

## Wichtige Implementierungsdetails

### Testmuster (in dieser Reihenfolge)
1. `0x00` - Alle Bits 0
2. `0xFF` - Alle Bits 1
3. `0xAA` - Alternierende Bits (10101010)
4. `0x55` - Alternierende Bits (01010101)
5. `Random` - Zufallsdaten (mit Seed für Reproduzierbarkeit)

**Pattern-Auswahl:**
- User kann via Checkboxen auswählen welche Muster getestet werden
- Default: Alle 5 Muster ausgewählt
- Mindestens 1 Muster muss ausgewählt sein
- Auswahl wird in Session gespeichert (Pause/Resume)

### Testablauf
1. Alle Testdateien mit Muster 1 schreiben
2. Alle Testdateien mit Muster 1 verifizieren
3. Alle Testdateien mit Muster 2 überschreiben
4. Alle Testdateien mit Muster 2 verifizieren
5. ... und so weiter für alle ausgewählten Muster

### Dateikonventionen
- **Testdateien:** `disktest_001.dat`, `disktest_002.dat`, ...
- **Session-Datei:** `disktest_session.json`
- **Log-Datei:** `disktest_YYYYMMDD_HHMMSS.log`

### Performance-Parameter
- **Chunk-Größe:** 16 MB (Lesen/Schreiben)
- **Testdatei-Größe:** Default 1 GB (konfigurierbar)
- **Random Pattern:** Optimiert mit `randbytes()` - ~289 MB/s (29x schneller als byte-für-byte)

## Wichtige Verhaltensweisen

### Session-Wiederherstellung
Beim Programmstart prüfen, ob `disktest_session.json` existiert. Falls ja, User fragen ob fortgesetzt werden soll.

### Pause-Funktion
- Aktuellen Chunk fertig schreiben/lesen
- Session-State speichern
- Beim Fortsetzen: Exakt an dieser Stelle weitermachen

### Fehlerbehandlung
- Schreibfehler: Loggen, Datei markieren, mit nächster Datei fortfahren
- Verifikationsfehler: Loggen, in Fehler-Counter aufnehmen, fortfahren
- Laufwerk voll: Graceful handling, Test mit vorhandenen Dateien fortsetzen

## Entwicklungsrichtlinien

- Klare Trennung zwischen GUI und Core-Logik
- Test-Engine läuft in separatem Thread (GUI bleibt responsiv)
- Signals/Slots für Kommunikation zwischen Thread und GUI
- Alle Texte auf Deutsch (private Nutzung)
- Ausführliche Logging für Debugging

## Abhängigkeiten

```
PySide6>=6.5.0
```

Keine weiteren externen Abhängigkeiten - nur Python-Standardbibliothek und PySide6.

## Windows-Spezifische Hinweise

### Entwicklungsumgebung
- **Virtual Environment:** `.venv` im Projektverzeichnis (nicht `venv`)
- **Python Launcher:** `.venv/Scripts/python.exe` für alle Python-Befehle verwenden
- **Git Bash:** Bevorzugt für Kommandozeilen-Befehle (nicht CMD/PowerShell)

### Bekannte Windows-Probleme

**1. Kommandozeilen-Befehle:**
- **Problem:** Nicht alle Unix-Befehle funktionieren in Git Bash unter Windows
- **Beispiele:**
  - `dir /s /b` (Windows CMD) funktioniert nicht in Bash
  - `ls -la` funktioniert, aber `find` hat andere Syntax
- **Lösung:** Bei Fehlern alternative Windows-kompatible Befehle verwenden
- **Tipp:** Mehrere Versuche mit verschiedenen Befehlsvarianten sind normal

**2. Unicode-Encoding:**
- **Problem:** Windows CMD/PowerShell verwendet CP1252 statt UTF-8
- **Symptom:** `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`
- **Betroffene Zeichen:** ✓ ✗ → ← und andere Unicode-Symbole
- **Lösung:**
  - In Python-Scripts: Nur ASCII-Zeichen für Output verwenden
  - In Git Commits: Unicode ist OK (Git verwendet UTF-8)
  - In Logs: Deutsche Umlaute funktionieren (ä, ö, ü)

**3. PySide6 Signal Overflow:**
- **Problem:** `Signal(int, int, float)` limitiert auf 32-bit signed int (~2.1 GB)
- **Symptom:** `OverflowError: Value exceeds limits of type [signed] "int"`
- **Lösung:** `Signal(float, float, float)` verwenden
- **Begründung:** float64 kann Ganzzahlen bis 2^53 (~9 PB) exakt darstellen

**4. Pfad-Konventionen:**
- **Windows-Pfade:** `c:\#AI\VSCode\Disktest` mit Backslashes
- **Git Bash:** Pfade in Quotes bei Leerzeichen: `cd "c:\#AI\VSCode\Disktest"`
- **Python:** Nutzt forward slashes (`/`) oder rohe Strings (`r"C:\path"`)

### Testing unter Windows
```bash
# Virtual Environment aktivieren
cd "c:\#AI\VSCode\Disktest"
.venv/Scripts/python.exe test_engine.py

# GUI starten
.venv/Scripts/python.exe src/main.py

# Performance-Test
.venv/Scripts/python.exe -c "from src.core.patterns import PatternGenerator, PatternType; ..."
```

### Import-Struktur
- **Relative Imports:** `from ..core.patterns import X` funktionieren nur in Packages
- **Absolute Imports:** `from core.patterns import X` in `src/gui/widgets.py`
- **Reason:** `main.py` führt aus, daher `src/` ist Top-Level
