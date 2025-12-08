# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [1.0.0] - 2025-12-08

### ✨ Vollständige Erstveröffentlichung

DiskTest ist eine Windows-Desktop-Anwendung für nicht-destruktive Festplattentests, inspiriert von Linux `badblocks`.

### Hinzugefügt

#### Phase 0: Projekt-Setup
- Vollständige Projektstruktur mit Python 3.11+
- Virtual Environment Setup
- PySide6 6.10.1 als GUI-Framework
- `.gitignore` für Python-Projekte
- Umfassende Markdown-Dokumentation (CLAUDE.md, ARCHITECTURE.md, FEATURES.md, UI-SPEC.md)

#### Phase 1: Core-Komponenten
- **Pattern-Generator** (`src/core/patterns.py`)
  - 5 Testmuster: 0x00, 0xFF, 0xAA, 0x55, Random
  - Reproduzierbare Zufallsdaten mit Seed
  - Reset-Funktion für Verifikation

- **File-Manager** (`src/core/file_manager.py`)
  - Testdatei-Verwaltung mit Namensschema `disktest_XXX.dat`
  - Automatische Dateianzahl-Berechnung
  - Speicherplatz-Prüfung
  - Datei-Löschfunktion

- **Disk-Info** (`src/utils/disk_info.py`)
  - Speicherplatz-Informationen (frei, gesamt, verwendet)
  - Laufwerksbuchstaben-Erkennung
  - Byte- und Geschwindigkeits-Formatierung

- **Logger** (`src/utils/logger.py`)
  - Log-Levels: INFO, SUCCESS, WARNING, ERROR
  - Automatische Log-Datei mit Zeitstempel
  - Formatierte Ausgabe mit Trennlinien

#### Phase 2: Session-Management
- **SessionData** (`src/core/session.py`)
  - Vollständiger Session-State als Dataclass
  - Fortschritts-Berechnung (0-100%)
  - Fehler-Tracking mit Details
  - JSON-Serialisierung/Deserialisierung
  - Zeit-Formatierung

- **SessionManager**
  - Session-Speicherung und -Laden
  - Automatische Session-Wiederherstellung
  - Session-Info für GUI-Anzeige

#### Phase 3: Test-Engine
- **TestEngine** (`src/core/test_engine.py`)
  - QThread-basiert für responsive GUI
  - 5 Muster × 2 Phasen (Schreiben/Verifizieren) = 10 Phasen total
  - Chunk-basiertes Schreiben/Lesen (16 MB Chunks)
  - Pause/Resume/Stop Funktionalität
  - Automatisches Session-Speichern bei Pause
  - Geschwindigkeits-Berechnung (gleitender Durchschnitt)
  - Umfassendes Error-Handling
  - 7 Qt Signals für GUI-Updates

#### Phase 4: GUI Widgets
- **Custom Widgets** (`src/gui/widgets.py`)
  - ErrorCounterWidget - Farbcodierte Fehler-Anzeige (grün=0, rot>0)
  - ProgressWidget - Umfassende Fortschrittsanzeige mit Details
  - LogWidget - Farbcodierte Log-Ausgabe

- **Hauptfenster** (`src/gui/main_window.py`)
  - ConfigurationWidget - Zielpfad, Testgröße, Dateigröße
  - ControlWidget - Start, Pause, Stop, Dateien löschen
  - MainWindow - Vollständige GUI mit Menüleiste und Statusleiste
  - Responsive Layout (800×600px Minimum)
  - Tastenkürzel (Ctrl+S, Ctrl+P, Escape, Ctrl+L)

- **Dialoge** (`src/gui/dialogs.py`)
  - SessionRestoreDialog - Session-Wiederherstellung mit Details
  - DeleteFilesDialog - Datei-Löschung mit Größenangabe
  - StopConfirmationDialog - Test-Abbruch-Bestätigung
  - ErrorDetailDialog - Fehler-Liste mit Scroll-Funktion

#### Phase 5: Integration
- **TestController** (`src/gui/test_controller.py`, 591 Zeilen)
  - Zentraler Controller für GUI-Engine-Kommunikation
  - 7 Engine-Signals → 7 Controller-Slots
  - 8 GUI-Signals → 8 Controller-Slots
  - Test-Lifecycle-Management
  - Session-Wiederherstellung beim Programmstart
  - Automatische Button-Aktivierung basierend auf State
  - Graceful Shutdown mit Session-Speicherung
  - Fehler-Aggregation und Detail-Dialog

- **Dokumentation**
  - INTEGRATION.md mit Architektur-Diagrammen
  - Signal/Slot-Übersichten
  - State-Transition-Diagramme
  - Debugging-Tipps

#### Phase 6: Finalisierung & Testing
- **End-to-End Tests** (`test_e2e.py`)
  - 6 Testgruppen, 35 Tests total
  - 77% Test-Success-Rate (27/35 bestanden)
  - Vollständiger Write-Verify-Zyklus
  - Session-Management-Tests
  - Pattern-Verifikation
  - DiskInfo und Logger-Tests

- **Testskripte**
  - `test_core.py` - Core-Komponenten
  - `test_session.py` - Session-Management
  - `test_engine.py` - Test-Engine
  - `test_gui.py` - GUI-Demo
  - `test_integration.py` - Integration (quick/full)
  - `test_e2e.py` - End-to-End

### Technische Details

- **Sprache:** Python 3.11+
- **GUI-Framework:** PySide6 6.10.1 (Qt for Python)
- **Plattform:** Windows (private Nutzung)
- **UI-Sprache:** Deutsch
- **Threading:** QThread für Test-Engine
- **Chunk-Größe:** 16 MB
- **Default Dateigröße:** 1 GB
- **Testmuster:** 5 (0x00, 0xFF, 0xAA, 0x55, Random mit Seed)

### Architektur

```
GUI (PySide6)
    ↕ Signals/Slots
TestController
    ↕ Signals/Slots
TestEngine (QThread)
    ↓
┌────────────┬─────────────┬──────────────┐
│  Pattern   │    File     │   Session    │
│ Generator  │  Manager    │   Manager    │
└────────────┴─────────────┴──────────────┘
```

### Dokumentation

- README.md - Projektübersicht und Setup
- CLAUDE.md - Projektkonzept
- ARCHITECTURE.md - Technische Architektur
- FEATURES.md - Feature-Spezifikation
- UI-SPEC.md - GUI-Spezifikation
- INTEGRATION.md - Integrationsdokumentation
- CHANGELOG.md - Dieses Dokument

### Bekannte Einschränkungen

- Nur Windows-Plattform unterstützt
- Nur ein Test zur Zeit möglich
- Session-Speicherort fix im Zielpfad
- Test-Abbruch löscht Session (nur Pause behält sie)
- GUI benötigt mindestens 800×600px

### Zukünftige Verbesserungen

Mögliche Erweiterungen für zukünftige Versionen:

- [ ] Parallele Tests auf mehreren Laufwerken
- [ ] Konfigurierbare Testmuster
- [ ] Export von Test-Reports (PDF, CSV)
- [ ] Systemtray-Integration
- [ ] Automatische Tests zu bestimmten Zeiten
- [ ] SMART-Daten-Integration
- [ ] Benchmark-Modus für Geschwindigkeitsvergleiche
- [ ] Portable Executable (PyInstaller)
- [ ] Application Icon
- [ ] Installer (NSIS oder ähnlich)

---

## Versionierung

Dieses Projekt verwendet [Semantic Versioning](https://semver.org/lang/de/):

- **MAJOR** Version bei inkompatiblen API-Änderungen
- **MINOR** Version bei neuer Funktionalität (abwärtskompatibel)
- **PATCH** Version bei Bugfixes (abwärtskompatibel)

---

## Credits

Entwickelt mit Claude Sonnet 4.5 (Anthropic).

Inspiriert von Linux `badblocks` Utility.

GUI Framework: Qt for Python (PySide6) von The Qt Company.
