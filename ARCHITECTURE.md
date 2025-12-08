# DiskTest - Technische Architektur

## Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                        GUI (PySide6)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Kontrolle   │  │ Fortschritt │  │ Log-Ausgabe         │  │
│  │ Start/Pause │  │ Anzeigen    │  │ (scrollbar)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │ Signals/Slots
┌─────────────────────────▼───────────────────────────────────┐
│                    TestEngine (QThread)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ FileManager │  │ Patterns    │  │ Session             │  │
│  │             │  │             │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     Dateisystem                             │
│  Testdateien (disktest_XXX.dat) + Session + Log             │
└─────────────────────────────────────────────────────────────┘
```

## Komponenten im Detail

### 1. GUI-Schicht (`gui/`)

#### main_window.py
Das Hauptfenster der Anwendung.

**Verantwortlichkeiten:**
- Layout und Widget-Anordnung
- Event-Handling für Buttons
- Signal/Slot-Verbindungen zur TestEngine
- Aktualisierung der Fortschrittsanzeigen

**Wichtige Methoden:**
```python
class MainWindow(QMainWindow):
    def __init__(self)
    def setup_ui(self)
    def on_start_clicked(self)
    def on_pause_clicked(self)
    def on_stop_clicked(self)
    def on_browse_clicked(self)
    def update_progress(self, current, total, speed_mbps)
    def update_status(self, message)
    def append_log(self, entry)
    def on_error(self, error_info)
    def on_test_complete(self, summary)
    def check_existing_session(self)
```

#### widgets.py
Wiederverwendbare Custom-Widgets.

**Widgets:**
- `SpeedLabel` - Formatierte Geschwindigkeitsanzeige (MB/s)
- `ProgressCard` - Fortschrittsanzeige mit Label und Prozent
- `ErrorCounter` - Auffällige Fehler-Anzeige

### 2. Core-Schicht (`core/`)

#### test_engine.py
Herzstück der Anwendung - führt die Tests durch.

**Klasse: TestEngine(QThread)**

**Signals:**
```python
progress_updated = Signal(float, float, float)  # current_bytes, total_bytes, speed_mbps
                                                # Hinweis: float verwendet für Unterstützung
                                                # großer Dateien (>2GB) ohne Overflow unter Windows
status_changed = Signal(str)                    # Statusnachricht
log_entry = Signal(str)                         # Log-Eintrag
error_occurred = Signal(dict)                   # Fehler-Details
test_completed = Signal(dict)                   # Zusammenfassung
```

**States:**
```python
class TestState(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    COMPLETED = auto()
    ERROR = auto()
```

**Wichtige Methoden:**
```python
class TestEngine(QThread):
    def __init__(self, config: TestConfig)
    def run(self)                    # Thread-Hauptmethode
    def pause(self)                  # Setzt Pause-Flag
    def resume(self)                 # Setzt Resume-Flag
    def stop(self)                   # Setzt Stop-Flag
    def _write_pattern(self, pattern_type)
    def _verify_pattern(self, pattern_type)
    def _write_file(self, filepath, pattern_generator)
    def _verify_file(self, filepath, pattern_generator)
    def _calculate_speed(self, bytes_written, elapsed_time)
```

#### patterns.py
Generierung der Testmuster.

```python
class PatternType(Enum):
    ZERO = "00"      # 0x00
    ONE = "FF"       # 0xFF
    ALT_AA = "AA"    # 0xAA
    ALT_55 = "55"    # 0x55
    RANDOM = "RND"   # Zufallsdaten

class PatternGenerator:
    def __init__(self, pattern_type: PatternType, seed: int = None)
    def generate_chunk(self, size: int) -> bytes
    def reset(self)  # Für Verifikation: Generator zurücksetzen
```

**Wichtig für Random-Muster:**
- Seed wird in Session gespeichert
- Bei Verifikation wird Generator mit gleichem Seed neu initialisiert
- Damit sind Zufallsdaten reproduzierbar

#### file_manager.py
Verwaltung der Testdateien.

```python
class FileManager:
    def __init__(self, target_path: str, file_size_gb: float)
    def calculate_file_count(self, total_size_gb: float) -> int
    def get_file_path(self, index: int) -> str
    def get_all_file_paths(self) -> list[str]
    def delete_test_files(self)
    def get_free_space(self) -> int  # Bytes
    def files_exist(self) -> bool
```

**Dateinamen-Schema:**
```
{target_path}/disktest_001.dat
{target_path}/disktest_002.dat
...
{target_path}/disktest_NNN.dat
```

#### session.py
Session-Management für Pause/Resume.

```python
@dataclass
class SessionData:
    target_path: str
    file_size_gb: float
    total_size_gb: float
    file_count: int
    current_pattern_index: int      # 0-4
    current_file_index: int         # 0 bis file_count-1
    current_phase: str              # "write" oder "verify"
    current_chunk_index: int        # Position in Datei
    random_seed: int                # Für reproduzierbare Random-Daten
    errors: list[dict]              # Bisherige Fehler
    start_time: str                 # ISO-Format
    elapsed_seconds: float          # Bisherige Laufzeit

class SessionManager:
    def __init__(self, session_path: str)
    def save(self, data: SessionData)
    def load(self) -> SessionData | None
    def exists(self) -> bool
    def delete(self)
```

**Session-Datei Format (JSON):**
```json
{
  "version": 1,
  "target_path": "D:\\",
  "file_size_gb": 1.0,
  "total_size_gb": 50.0,
  "file_count": 50,
  "current_pattern_index": 2,
  "current_file_index": 23,
  "current_phase": "verify",
  "current_chunk_index": 48,
  "random_seed": 123456789,
  "errors": [
    {
      "file": "disktest_015.dat",
      "pattern": "FF",
      "phase": "verify",
      "message": "Daten stimmen nicht überein"
    }
  ],
  "start_time": "2024-12-07T14:30:00",
  "elapsed_seconds": 3600.5
}
```

### 3. Utils-Schicht (`utils/`)

#### logger.py
Logging-Funktionalität.

```python
class DiskTestLogger:
    def __init__(self, log_dir: str)
    def info(self, message: str)
    def error(self, message: str)
    def warning(self, message: str)
    def success(self, message: str)
    def get_log_path(self) -> str
```

**Log-Format:**
```
[2024-12-07 14:30:22] INFO    Test gestartet - Ziel: D:\
[2024-12-07 14:30:22] INFO    Konfiguration: 50 Dateien à 1 GB
[2024-12-07 14:35:44] SUCCESS disktest_001.dat - Muster 0x00 - Schreiben OK
[2024-12-07 14:40:12] SUCCESS disktest_001.dat - Muster 0x00 - Verifizierung OK
[2024-12-07 15:22:33] ERROR   disktest_023.dat - Muster 0xFF - Verifizierung FEHLGESCHLAGEN
```

#### disk_info.py
Laufwerksinformationen abrufen.

```python
class DiskInfo:
    @staticmethod
    def get_free_space(path: str) -> int          # Bytes
    @staticmethod
    def get_total_space(path: str) -> int         # Bytes
    @staticmethod
    def get_drive_letter(path: str) -> str
    @staticmethod
    def is_valid_path(path: str) -> bool
    @staticmethod
    def format_bytes(bytes: int) -> str           # "1.5 GB"
```

## Datenfluss

### Test starten
```
User klickt "Start"
    │
    ▼
MainWindow.on_start_clicked()
    │
    ├── Validierung (Pfad existiert? Genug Platz?)
    │
    ├── TestConfig erstellen
    │
    ├── TestEngine(config) erstellen
    │
    ├── Signals verbinden
    │
    └── TestEngine.start()
            │
            ▼
        TestEngine.run()
            │
            ├── Session initialisieren
            │
            ├── Für jedes Pattern:
            │   ├── Für jede Datei: Schreiben
            │   └── Für jede Datei: Verifizieren
            │
            └── test_completed.emit(summary)
```

### Pause/Resume
```
User klickt "Pause"
    │
    ▼
MainWindow.on_pause_clicked()
    │
    └── TestEngine.pause()
            │
            ├── Setzt self._pause_requested = True
            │
            └── In run()-Loop:
                    │
                    ├── Nach aktuellem Chunk prüfen
                    │
                    ├── Session speichern
                    │
                    └── Warten auf resume()
```

## Threading-Modell

```
┌─────────────────┐         ┌─────────────────┐
│   Main Thread   │         │  Worker Thread  │
│   (GUI)         │         │  (TestEngine)   │
│                 │         │                 │
│  Qt Event Loop  │◄────────│  Signals emit   │
│                 │  Slots  │                 │
│  Button Clicks  │────────►│  Control Flags  │
│                 │         │                 │
└─────────────────┘         └─────────────────┘
```

**Wichtig:**
- GUI läuft im Main Thread
- TestEngine läuft in separatem QThread
- Kommunikation nur über Signals/Slots (thread-safe)
- Keine direkte Manipulation von GUI-Elementen aus Worker Thread

## Fehlerbehandlung

### Fehlertypen
1. **Schreibfehler** - Datei kann nicht geschrieben werden
2. **Lesefehler** - Datei kann nicht gelesen werden
3. **Verifikationsfehler** - Gelesene Daten ≠ Geschriebene Daten
4. **Speicherplatz-Fehler** - Laufwerk voll
5. **Abbruch durch User** - Stop-Button

### Strategie
- Bei Fehler: Loggen → Fehler-Counter erhöhen → Weitermachen
- Bei kritischem Fehler (z.B. Laufwerk nicht mehr erreichbar): Test abbrechen
- Alle Fehler werden in Session gespeichert (für Resume)
