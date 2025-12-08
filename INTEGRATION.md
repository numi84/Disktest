# DiskTest - GUI-Engine Integration

## Übersicht

Die Integration verbindet die grafische Benutzeroberfläche (GUI) mit der Test-Engine durch einen zentralen Controller.

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                        MainWindow                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Config   │  │ Control  │  │ Progress │  │   Log    │   │
│  │ Widget   │  │ Widget   │  │ Widget   │  │ Widget   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Signal/Slot
                            ▼
                  ┌─────────────────┐
                  │ TestController  │ ◄─── Verbindet GUI & Engine
                  └─────────────────┘
                            │
                            │ Signals/Slots
                            ▼
                  ┌─────────────────┐
                  │   TestEngine    │
                  │   (QThread)     │
                  └─────────────────┘
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Pattern  │ │   File   │ │ Session  │
        │Generator │ │ Manager  │ │ Manager  │
        └──────────┘ └──────────┘ └──────────┘
```

## Komponenten

### 1. TestController

**Datei:** `src/gui/test_controller.py`

**Verantwortlichkeiten:**
- Koordiniert Kommunikation zwischen GUI und Engine
- Verwaltet Test-Lifecycle (Start, Pause, Stop)
- Session-Wiederherstellung beim Programmstart
- Dateiverwaltung (Löschen von Testdateien)
- Error-Handling und -Anzeige
- Progress-Updates an GUI weiterleiten

**Wichtige Methoden:**
```python
on_start_clicked()      # Startet neuen Test oder setzt fort
on_pause_clicked()      # Pausiert laufenden Test
on_stop_clicked()       # Stoppt Test nach Bestätigung
on_delete_files_clicked()  # Löscht Testdateien
on_progress_updated()   # Empfängt Progress von Engine
on_error_occurred()     # Behandelt Fehler von Engine
```

### 2. Signal/Slot Verbindungen

#### GUI → Controller

| Widget          | Signal            | Controller Slot           |
|-----------------|-------------------|---------------------------|
| ControlWidget   | start_clicked     | on_start_clicked()        |
| ControlWidget   | pause_clicked     | on_pause_clicked()        |
| ControlWidget   | stop_clicked      | on_stop_clicked()         |
| ControlWidget   | delete_files_clicked | on_delete_files_clicked() |
| ConfigWidget    | path_changed      | on_path_changed()         |
| ErrorCounter    | clicked           | on_error_counter_clicked() |

#### Engine → Controller

| Engine Signal       | Controller Slot           | Beschreibung              |
|---------------------|---------------------------|---------------------------|
| progress_updated    | on_progress_updated()     | Progress in Bytes, Speed  |
| status_changed      | on_status_changed()       | Status-Text für Statusbar |
| log_entry           | on_log_entry()            | Log-Nachricht             |
| error_occurred      | on_error_occurred()       | Fehler aufgetreten        |
| test_completed      | on_test_completed()       | Test abgeschlossen        |
| pattern_changed     | on_pattern_changed()      | Muster gewechselt         |
| phase_changed       | on_phase_changed()        | Phase gewechselt          |

## Ablauf

### Start eines neuen Tests

```
User klickt "Start"
    │
    ▼
TestController.on_start_clicked()
    │
    ├─ Config validieren
    │
    ├─ TestConfig erstellen
    │
    ├─ TestEngine(config) erstellen
    │
    ├─ Engine-Signals verbinden
    │
    ├─ GUI vorbereiten (Buttons deaktivieren, etc.)
    │
    └─ engine.start()
            │
            ▼
        TestEngine läuft in separatem Thread
            │
            ├─ Emittiert progress_updated
            ├─ Emittiert log_entry
            ├─ Emittiert pattern_changed
            ├─ Emittiert phase_changed
            └─ Bei Abschluss: test_completed
```

### Session-Wiederherstellung

```
Programmstart
    │
    ▼
MainWindow.__init__()
    │
    ├─ _setup_ui()
    │
    └─ TestController.__init__()
            │
            └─ _check_for_existing_session()
                    │
                    ├─ SessionManager prüfen
                    │
                    ├─ Falls Session vorhanden:
                    │   SessionRestoreDialog anzeigen
                    │
                    └─ User-Auswahl:
                        ├─ "Fortsetzen" → _resume_session()
                        ├─ "Neuer Test" → Session löschen
                        └─ "Abbrechen" → Nichts tun
```

### Pause/Resume

```
Pause:
    User klickt "Pause"
        │
        ▼
    TestController.on_pause_clicked()
        │
        └─ engine.pause()
                │
                └─ Engine speichert Session & wartet

Resume:
    User klickt "Fortsetzen"
        │
        ▼
    TestController.on_start_clicked()
        │
        └─ Falls engine existiert:
            engine.resume()
                │
                └─ Engine setzt fort

        Sonst:
            Neue Engine mit session_data erstellen
            engine.start()
```

### Fehlerbehandlung

```
Engine erkennt Fehler
    │
    └─ error_occurred.emit(error_dict)
            │
            ▼
        TestController.on_error_occurred()
            │
            ├─ Fehler zur Liste hinzufügen
            │
            ├─ Error-Counter aktualisieren
            │
            └─ Log-Eintrag erstellen

User klickt auf Error-Counter
    │
    ▼
TestController.on_error_counter_clicked()
    │
    └─ ErrorDetailDialog anzeigen
```

## Test-States

Der Controller verwaltet den Test-State:

```python
class TestState(Enum):
    IDLE = auto()       # Bereit, nicht aktiv
    RUNNING = auto()    # Test läuft
    PAUSED = auto()     # Test pausiert
    STOPPING = auto()   # Test wird gestoppt
    COMPLETED = auto()  # Test abgeschlossen
    ERROR = auto()      # Fehler aufgetreten
```

### State-Transitions

```
        ┌─────┐
        │IDLE │ ◄─────────────┐
        └─────┘               │
           │                  │
     Start │            Stop  │
           ▼                  │
      ┌─────────┐        ┌────────┐
      │RUNNING  │───────►│STOPPING│
      └─────────┘        └────────┘
           │ ▲
    Pause  │ │ Resume
           ▼ │
      ┌─────────┐
      │PAUSED   │
      └─────────┘
           │
  Completed│
           ▼
      ┌──────────┐
      │COMPLETED │
      └──────────┘
```

## Besonderheiten

### 1. Threading

Die TestEngine läuft in einem separaten Thread (QThread), damit die GUI responsiv bleibt:

```python
class TestEngine(QThread):
    def run(self):
        # Wird in separatem Thread ausgeführt
        # ...
```

Alle Kommunikation GUI ↔ Engine erfolgt über Qt Signals/Slots (thread-safe).

### 2. Progress-Berechnung

```python
# Engine berechnet:
current_bytes = bytes_processed
total_bytes = file_count * file_size * 5 * 2  # 5 Muster × 2 Phasen

# Controller berechnet daraus:
percent = (current_bytes / total_bytes) * 100
remaining_time = (total_bytes - current_bytes) / speed
```

### 3. Lazy Import im MainWindow

Um zirkuläre Imports zu vermeiden:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._initialize_state()

        # Import NACH UI-Setup
        from .test_controller import TestController
        self.controller = TestController(self)
```

### 4. Graceful Shutdown

Beim Schließen des Fensters während ein Test läuft:

```python
def closeEvent(self, event):
    if self.controller.current_state == TestState.RUNNING:
        # Bestätigung anfordern
        reply = QMessageBox.question(...)

        if reply == No:
            event.ignore()  # Schließen verhindern
            return

        # Test pausieren & Session speichern
        self.controller.engine.pause()
        self.controller.engine.wait()

    event.accept()
```

## Tests

### Quick GUI Test

Zeigt GUI mit simulierten Werten (ohne echten Disk-Test):

```bash
.venv/Scripts/python.exe test_integration.py --quick
```

### Full Integration Test

Erstellt temporäres Verzeichnis und ermöglicht echten Test:

```bash
.venv/Scripts/python.exe test_integration.py --full
```

### Unit Tests für Controller

```bash
.venv/Scripts/python.exe -m pytest tests/test_controller.py
```

## Erweiterungen

### Neue Signals hinzufügen

1. **In TestEngine:**
   ```python
   new_signal = Signal(int, str)
   ```

2. **Signal emittieren:**
   ```python
   self.new_signal.emit(value, message)
   ```

3. **In TestController:**
   ```python
   def _connect_engine_signals(self):
       # ...
       self.engine.new_signal.connect(self.on_new_signal)

   @Slot(int, str)
   def on_new_signal(self, value, message):
       # Handle signal
       pass
   ```

### Neuen Dialog hinzufügen

1. **Dialog erstellen in `dialogs.py`:**
   ```python
   class MyDialog(QDialog):
       def __init__(self, ...):
           # ...
   ```

2. **Im Controller verwenden:**
   ```python
   dialog = MyDialog(...)
   if dialog.exec() == QDialog.Accepted:
       # ...
   ```

## Debugging

### Logging aktivieren

Die TestEngine loggt automatisch in `disktest_YYYYMMDD_HHMMSS.log`.

### Signals verfolgen

```python
# In TestController.__init__():
self.engine.progress_updated.connect(
    lambda c, t, s: print(f"Progress: {c}/{t} @ {s} MB/s")
)
```

### State-Transitions loggen

```python
# In TestController:
def _set_state(self, new_state):
    print(f"State: {self.current_state} → {new_state}")
    self.current_state = new_state
```

## Bekannte Limitierungen

1. **Keine Parallele Tests:** Nur ein Test zur Zeit möglich
2. **Session-Speicherort fix:** Immer im Zielpfad
3. **Keine Test-Abbruch-Resume:** Stop löscht Session, nur Pause behält sie

## Siehe auch

- [ARCHITECTURE.md](ARCHITECTURE.md) - Gesamtarchitektur
- [UI-SPEC.md](UI-SPEC.md) - GUI-Spezifikation
- [FEATURES.md](FEATURES.md) - Feature-Beschreibungen
