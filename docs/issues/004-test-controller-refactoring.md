# Issue #004: test_controller.py Refactoring (zu groß)

## Status: ✅ Behoben (2025-12-16)

## Priorität: 🟡 Mittel

## Beschreibung
Die Datei `test_controller.py` ist mit 1590+ Zeilen zu groß und verletzt das Single-Responsibility-Principle. Sie enthält:
- Test-Kontrolle
- Session-Management
- File-Recovery-Logik
- Multi-Session-Scanning
- Recent-Sessions-Verwaltung
- Settings-Management

## Betroffene Dateien
- `src/gui/test_controller.py` (1590 Zeilen)

## Problem
1. **Schwer wartbar:** Zu viel Code in einer Datei
2. **Viele Verantwortlichkeiten:** Test-Logik + Session + Recovery + Scanning
3. **Schwer testbar:** Unit-Tests müssten gesamten Controller mocken
4. **Code-Navigation schwierig:** Scrollen durch 1500+ Zeilen

## Lösungsvorschlag: Aufteilen in 4 Controller

### Neue Struktur
```
src/gui/controllers/
├── __init__.py
├── test_controller.py       # Nur Test-Kontrolle (Start/Pause/Stop)
├── session_controller.py    # Session-Management & Recovery
├── file_controller.py       # File-Recovery & Deletion
└── settings_controller.py   # QSettings & Recent Sessions
```

### 1. test_controller.py (Core Test-Logik)
**Verantwortlichkeit:** Test-Engine starten/stoppen/pausieren

```python
"""
Test-Controller - Steuert Test-Engine
"""
from PySide6.QtCore import QObject, Slot
from core.test_engine import TestEngine, TestConfig, TestState

class TestController(QObject):
    """
    Hauptcontroller für Test-Ausführung

    Verantwortlich für:
    - Test starten/pausieren/stoppen
    - Progress-Updates empfangen
    - Error-Handling während Test
    """

    def __init__(self, main_window, session_controller, file_controller):
        super().__init__()
        self.window = main_window
        self.session_controller = session_controller
        self.file_controller = file_controller

        self.engine = None
        self.current_state = TestState.IDLE
        self.errors = []

        self._connect_signals()

    @Slot()
    def on_start_clicked(self):
        """Startet einen neuen Test"""
        # Config aus GUI holen
        config = self._create_test_config()

        # Engine erstellen und starten
        self.engine = TestEngine(config)
        self._connect_engine_signals()
        self.engine.start()

    @Slot()
    def on_pause_clicked(self):
        """Pausiert laufenden Test"""
        if self.engine:
            self.engine.pause()

    @Slot()
    def on_stop_clicked(self):
        """Stoppt laufenden Test"""
        if self.engine:
            self.engine.stop()

    # ... weitere Test-Control-Methoden
```

**Geschätzte Zeilen:** ~300-400

---

### 2. session_controller.py (Session-Management)
**Verantwortlichkeit:** Session laden/speichern/wiederherstellen

```python
"""
Session-Controller - Verwaltet Test-Sessions
"""
from PySide6.QtCore import QObject
from core.session import SessionManager, SessionData
from .dialogs import SessionRestoreDialog, MultiSessionSelectionDialog

class SessionController(QObject):
    """
    Controller für Session-Management

    Verantwortlich für:
    - Session-Wiederherstellung beim Start
    - Multi-Session-Scanning
    - Session-Dialoge anzeigen
    - Recent Sessions verwalten
    """

    def __init__(self, main_window, settings_controller):
        super().__init__()
        self.window = main_window
        self.settings = settings_controller

    def check_for_existing_sessions(self):
        """Prüft beim Start auf existierende Sessions"""
        # Multi-Session-Scan
        sessions = self._scan_for_sessions()

        if len(sessions) == 0:
            self._show_drive_selection()
        elif len(sessions) == 1:
            self._handle_single_session(sessions[0])
        else:
            self._show_multi_session_dialog(sessions)

    def _scan_for_sessions(self) -> List[SessionInfo]:
        """Scannt nach Sessions (Recent + All Drives)"""
        sessions = []

        # 1. Recent Sessions
        if self.settings.get_bool("session_scan_enabled"):
            sessions.extend(self._scan_recent_sessions())

        # 2. Full Scan
        sessions.extend(self._scan_all_drives())

        return self._deduplicate_sessions(sessions)

    def resume_session(self, session_data: SessionData):
        """Setzt Session fort"""
        # Prüfe auf fehlende Dateien
        self._check_for_missing_files(session_data)

        # Erstelle Config für Resume
        config = self._create_resume_config(session_data)

        # Signalisiere Test-Controller
        self.session_ready_for_resume.emit(config)

    # ... weitere Session-Methoden
```

**Geschätzte Zeilen:** ~400-500

---

### 3. file_controller.py (File-Management)
**Verantwortlichkeit:** Testdatei-Operationen

```python
"""
File-Controller - Verwaltet Testdateien
"""
from PySide6.QtCore import QObject
from core.file_manager import FileManager
from core.file_analyzer import FileAnalyzer
from .dialogs import FileRecoveryDialog, DeleteFilesDialog

class FileController(QObject):
    """
    Controller für Datei-Operationen

    Verantwortlich für:
    - Orphaned Files Recovery
    - Datei-Expansion
    - Testdateien löschen
    - Fehlende Dateien füllen
    """

    def __init__(self, main_window):
        super().__init__()
        self.window = main_window

    def check_for_orphaned_files(self, path: str) -> bool:
        """Prüft auf verwaiste Testdateien"""
        config = self.window.config_widget.get_config()
        file_size_gb = config.get('file_size_mb', 1000) / 1024.0

        analyzer = FileAnalyzer(path, file_size_gb)
        results = analyzer.analyze_existing_files()

        if not results:
            return False

        # Kategorisiere Dateien
        categories = analyzer.categorize_files(results)

        # Zeige Recovery-Dialog
        dialog = FileRecoveryDialog(categories, self.window)
        result = dialog.exec()

        if result == FileRecoveryDialog.RESULT_RECOVER:
            return self._recover_files(categories)

        return False

    def delete_test_files(self, path: str) -> tuple[int, int]:
        """Löscht Testdateien"""
        # Zeige Bestätigungs-Dialog
        dialog = DeleteFilesDialog(path, self.window)

        if dialog.exec():
            file_manager = FileManager(path, 1.0)
            return file_manager.delete_test_files()

        return (0, 0)

    def fill_missing_files(self, session_data: SessionData) -> bool:
        """Füllt fehlende Dateien in Sequenz"""
        # Analysiere vorhandene Dateien
        # Erkenne Lücken
        # Erstelle fehlende Dateien
        pass

    # ... weitere File-Methoden
```

**Geschätzte Zeilen:** ~300-400

---

### 4. settings_controller.py (Settings-Management)
**Verantwortlichkeit:** QSettings und Persistierung

```python
"""
Settings-Controller - Verwaltet App-Einstellungen
"""
from PySide6.QtCore import QSettings
import json
from datetime import datetime

class SettingsController:
    """
    Controller für persistente Einstellungen

    Verantwortlich für:
    - QSettings laden/speichern
    - Recent Sessions verwalten
    - User-Präferenzen
    """

    def __init__(self):
        self.settings = QSettings("DiskTest", "DiskTest")

    # Last Path
    def get_last_path(self) -> str:
        """Lädt letzten Pfad"""
        return self.settings.value("last_target_path", "")

    def save_last_path(self, path: str):
        """Speichert letzten Pfad"""
        self.settings.setValue("last_target_path", path)

    # Recent Sessions
    def get_recent_sessions(self, max_count: int = 10) -> List[dict]:
        """Lädt Recent Sessions"""
        recent = self.settings.value("recent_sessions", "[]")
        try:
            sessions = json.loads(recent)
            return sessions[:max_count]
        except (json.JSONDecodeError, TypeError):
            return []

    def add_recent_session(self, path: str):
        """Fügt Session zu Recent hinzu"""
        sessions = self.get_recent_sessions()

        # Entferne Duplikate
        sessions = [s for s in sessions if s.get('path') != path]

        # Füge am Anfang ein
        sessions.insert(0, {
            'path': path,
            'last_used': datetime.now().isoformat()
        })

        # Speichere
        max_recent = self.get_int("recent_sessions_max", 10)
        self.settings.setValue("recent_sessions", json.dumps(sessions[:max_recent]))

    # Generic getters
    def get_bool(self, key: str, default: bool = False) -> bool:
        return self.settings.value(key, default, type=bool)

    def get_int(self, key: str, default: int = 0) -> int:
        return self.settings.value(key, default, type=int)

    def get_string(self, key: str, default: str = "") -> str:
        return self.settings.value(key, default)

    # Setters
    def set_value(self, key: str, value):
        self.settings.setValue(key, value)
```

**Geschätzte Zeilen:** ~150-200

---

### Migration: Schritt für Schritt

#### Phase 1: Neue Struktur erstellen
```bash
mkdir src/gui/controllers
touch src/gui/controllers/__init__.py
touch src/gui/controllers/test_controller.py
touch src/gui/controllers/session_controller.py
touch src/gui/controllers/file_controller.py
touch src/gui/controllers/settings_controller.py
```

#### Phase 2: SettingsController extrahieren (einfachster Start)
1. Alle `self.settings.*` Aufrufe nach `settings_controller.py` verschieben
2. Im alten TestController: `self.settings = SettingsController()` verwenden
3. Testen dass alles funktioniert

#### Phase 3: FileController extrahieren
1. Alle File-Recovery Methoden nach `file_controller.py`
2. Alle `delete_files` Methoden verschieben
3. TestController nutzt `self.file_controller.delete_test_files()`

#### Phase 4: SessionController extrahieren
1. Alle Session-Scan Methoden verschieben
2. Alle Session-Dialog Methoden verschieben
3. `check_for_existing_session()` komplett verschieben

#### Phase 5: TestController aufräumen
1. Nur Test-Start/Stop/Pause Logik behalten
2. Delegates an andere Controller
3. Alte `test_controller.py` löschen, neue nutzen

#### Phase 6: MainWindow anpassen
```python
# main_window.py
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Controller initialisieren (Reihenfolge wichtig!)
        self.settings_controller = SettingsController()
        self.file_controller = FileController(self)
        self.session_controller = SessionController(self, self.settings_controller)
        self.test_controller = TestController(self, self.session_controller, self.file_controller)
```

## Testing
Nach jedem Schritt:
1. App starten
2. Session-Resume testen
3. Test starten/pausieren/stoppen
4. Dateien löschen testen
5. Recent Sessions testen

## Vorteile nach Refactoring
1. ✅ **Wartbarkeit:** Jeder Controller hat klare Verantwortlichkeit
2. ✅ **Testbarkeit:** Controller können einzeln getestet werden
3. ✅ **Code-Navigation:** Max 500 Zeilen pro Datei
4. ✅ **Wiederverwendbarkeit:** Controller können in anderen Projekten genutzt werden
5. ✅ **Team-Arbeit:** Verschiedene Entwickler können an verschiedenen Controllern arbeiten

## Zeitaufwand
- Phase 1-2: ~2 Stunden
- Phase 3: ~3 Stunden
- Phase 4: ~4 Stunden
- Phase 5-6: ~2 Stunden
- Testing: ~2 Stunden
**Gesamt:** ~13 Stunden

---

## Lösung (2025-12-16)

### Umgesetzte Struktur

```
src/gui/controllers/
├── __init__.py              # Package-Exports
├── settings_controller.py   # ~180 Zeilen - QSettings & Recent Sessions
├── file_controller.py       # ~400 Zeilen - File-Recovery & Deletion
├── session_controller.py    # ~350 Zeilen - Session-Management & Recovery
└── test_controller.py       # ~550 Zeilen - Test-Steuerung (Start/Pause/Stop)
```

### Änderungen

1. **Neues `controllers/` Package erstellt** mit 4 spezialisierten Controllern
2. **SettingsController:** Alle QSettings-Zugriffe, Recent Sessions
3. **FileController:** Datei-Operationen (Lücken füllen, Recovery, Löschen)
4. **SessionController:** Session-Scan, -Wiederherstellung, -Dialoge
5. **TestController:** Nur noch Test-Logik, koordiniert Sub-Controller
6. **MainWindow angepasst:** Import von `controllers` statt `test_controller`
7. **Alte `test_controller.py` gelöscht** (1865 Zeilen → 4 Dateien ~1480 Zeilen gesamt)

### Ergebnis

- ✅ Klare Verantwortlichkeiten (Single Responsibility Principle)
- ✅ Bessere Testbarkeit (Controller einzeln testbar)
- ✅ Einfachere Navigation (max ~550 Zeilen pro Datei)
- ✅ Wiederverwendbare Komponenten
