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

### Testablauf
1. Alle Testdateien mit Muster 1 schreiben
2. Alle Testdateien mit Muster 1 verifizieren
3. Alle Testdateien mit Muster 2 überschreiben
4. Alle Testdateien mit Muster 2 verifizieren
5. ... und so weiter für alle 5 Muster

### Dateikonventionen
- **Testdateien:** `disktest_001.dat`, `disktest_002.dat`, ...
- **Session-Datei:** `disktest_session.json`
- **Log-Datei:** `disktest_YYYYMMDD_HHMMSS.log`

### Performance-Parameter
- **Chunk-Größe:** 16 MB (Lesen/Schreiben)
- **Testdatei-Größe:** Default 1 GB (konfigurierbar)

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
