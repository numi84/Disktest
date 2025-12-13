---
name: Multi-Session-Unterstützung beim Programmstart
about: Mehrere Sessions auf verschiedenen Laufwerken erkennen und auswählen können
title: 'Multi-Session-Unterstützung beim Programmstart'
labels: enhancement, startup, session-management
assignees: ''
---

## Problem / Feature Request

Beim Programmstart soll der User zwischen mehreren bestehenden Sessions wählen können (z.B. auf verschiedenen Laufwerken). Außerdem soll beim Wählen eines neuen Laufwerks automatisch geprüft werden, ob dort Sessions oder Testdateien vorhanden sind.

## Aktuelles Verhalten

### Startup-Flow (aktuell)
1. **Programmstart** → `MainWindow.__init__()` → `TestController.__init__()`
2. **Letzten Pfad laden** (`_load_last_path()`) aus Registry
3. **Session-Check NUR für diesen einen Pfad** (`_check_for_existing_session()`)
4. **Falls kein Pfad:** DriveSelectionDialog zeigen
5. **Falls Session gefunden:** SessionRestoreDialog zeigen (Fortsetzen/Neu/Abbrechen)

### Kritische Limitation

**Single-Session-Ansatz:**
- Session-Check erfolgt nur für `config.get('target_path')` (zuletzt verwendeter Pfad)
- Sessions auf anderen Laufwerken werden NICHT erkannt
- User muss manuell zu anderem Laufwerk navigieren um dortige Session zu finden

**Code-Referenz:** [test_controller.py:106-115](c:\#AI\VSCode\Disktest\src\gui\test_controller.py#L106-L115)
```python
def _check_for_existing_session(self):
    config = self.window.config_widget.get_config()
    target_path = config.get('target_path', '')

    if not target_path or not os.path.exists(target_path):
        self._show_drive_selection_dialog()
        return

    # NUR für diesen einen Pfad prüfen
    session_manager = SessionManager(target_path)
    if not session_manager.exists():
        self._check_for_orphaned_files(target_path)
```

## Beispiel-Szenarien

### Szenario 1: Mehrere Sessions auf verschiedenen Laufwerken
```
Status vor Programmstart:
- C:\Test\disktest_session.json (50% fertig, 0xFF pattern)
- D:\Backup\disktest_session.json (80% fertig, 0xAA pattern)
- E:\Storage\disktest_session.json (20% fertig, 0x00 pattern)
- Letzter Pfad in Registry: C:\Test

Aktuelles Verhalten:
→ Nur C:\Test Session wird erkannt
→ User muss D:\ und E:\ manuell finden

Gewünschtes Verhalten:
→ Alle 3 Sessions beim Start anzeigen
→ User wählt welche fortgesetzt werden soll
→ Option "Neues Laufwerk wählen" zusätzlich
```

### Szenario 2: Session auf anderem Laufwerk + Neue Auswahl
```
Status:
- Letzter Pfad: D:\Test (keine Session mehr vorhanden)
- E:\Data\disktest_session.json (existiert, aber unbekannt)

Aktuelles Verhalten:
1. Programmstart prüft D:\Test → keine Session
2. DriveSelectionDialog gezeigt
3. User wählt E:\Data
4. JETZT erst wird E:\Data Session erkannt

Gewünschtes Verhalten:
1. Programmstart scannt ALLE Laufwerke nach Sessions
2. Dialog zeigt:
   - E:\Data (Session vorhanden, 60% fertig)
   - Neues Laufwerk wählen...
```

### Szenario 3: Orphaned Files auf mehreren Laufwerken
```
Status:
- C:\Test\disktest_001.dat, disktest_002.dat (orphaned)
- D:\Backup\disktest_001.dat bis 010.dat (orphaned)
- Keine Session-Dateien

Aktuelles Verhalten:
→ Nur C:\Test wird geprüft (falls letzter Pfad)
→ D:\Backup bleibt unentdeckt

Gewünschtes Verhalten:
→ Beide Pfade in Dialog anzeigen
→ "C:\Test (2 Testdateien gefunden - Recovery möglich)"
→ "D:\Backup (10 Testdateien gefunden - Recovery möglich)"
→ User wählt welches Laufwerk recovert werden soll
```

## Gewünschtes Verhalten

### 1. Globaler Session-Scan beim Start

**Neue Funktion:** `_scan_all_drives_for_sessions()`

```python
def _scan_all_drives_for_sessions(self) -> List[SessionInfo]:
    """Scannt alle Laufwerke nach Sessions und Testdateien"""
    sessions = []

    # Windows: A-Z scannen
    for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive_path = f"{drive_letter}:\\"
        if not os.path.exists(drive_path):
            continue

        # 1. Session direkt im Root prüfen
        if self._check_path_for_session(drive_path):
            sessions.append(...)

        # 2. Einen Ordner-Ebene tiefer scannen (z.B. D:\Test\)
        # (Optional, konfigurierbar wie tief gescannt wird)
        for subdir in os.listdir(drive_path):
            subpath = os.path.join(drive_path, subdir)
            if os.path.isdir(subpath):
                if self._check_path_for_session(subpath):
                    sessions.append(...)

    return sessions

def _check_path_for_session(self, path: str) -> Optional[SessionInfo]:
    """Prüft einzelnen Pfad auf Session oder Testdateien"""
    session_manager = SessionManager(path)

    # 1. Session-Datei vorhanden?
    if session_manager.exists():
        session_data = session_manager.load()
        return SessionInfo(
            path=path,
            type="session",
            progress=session_data.get_progress_percentage(),
            pattern_index=session_data.current_pattern_index,
            file_count=session_data.file_count
        )

    # 2. Orphaned Files vorhanden?
    test_files = list(Path(path).glob("disktest_*.dat"))
    if test_files:
        return SessionInfo(
            path=path,
            type="orphaned",
            file_count=len(test_files)
        )

    return None
```

### 2. Neuer Multi-Session-Auswahl-Dialog

**Neuer Dialog:** `MultiSessionSelectionDialog`

**Anzeige:**
```
┌─────────────────────────────────────────────────────────────┐
│  Bestehende Sessions gefunden                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ○ C:\Test\                                                 │
│    Session: 50% fertig (Pattern 2/5: 0xFF)                  │
│    Fehler: 0                                                │
│                                                             │
│  ○ D:\Backup\                                               │
│    Session: 80% fertig (Pattern 4/5: 0x55)                  │
│    Fehler: 3                                                │
│                                                             │
│  ○ E:\Storage\disktest\                                     │
│    Testdateien: 15 Dateien gefunden (Recovery möglich)      │
│    Pattern: 0xAA erkannt, Größe: ~15 GB                     │
│                                                             │
│  ○ Neues Laufwerk wählen...                                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                              [Fortsetzen] [Abbrechen]       │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Radio-Buttons für alle gefundenen Sessions/Testdateien
- Detaillierte Info für jede Session (Progress, Pattern, Fehler)
- "Neues Laufwerk wählen" Option am Ende
- Bei Auswahl von "Neues Laufwerk": Öffnet DriveSelectionDialog

### 3. DriveSelectionDialog: Automatische Session-Prüfung

**Erweiterung:** Nach Laufwerk-Auswahl SOFORT prüfen

```python
def _on_drive_selected(self, selected_path):
    """Callback nach Laufwerk-Auswahl"""

    # 1. Session vorhanden?
    session_info = self._check_path_for_session(selected_path)

    if session_info and session_info.type == "session":
        # Session gefunden - Restore-Dialog zeigen
        self._show_session_restore_dialog(session_info)

    elif session_info and session_info.type == "orphaned":
        # Testdateien gefunden - Recovery-Dialog zeigen
        self._check_for_orphaned_files(selected_path)

    else:
        # Leer - Direkt neuen Test starten
        self.window.log_widget.add_log(
            self._get_timestamp(),
            "INFO",
            f"Neues Laufwerk gewählt: {selected_path} (keine Sessions gefunden)"
        )
```

**Vorteil:** User erhält sofort Feedback ob auf dem gewählten Laufwerk Sessions/Testdateien sind.

### 4. Scan-Tiefe konfigurierbar

**Problem:** Ganzes Laufwerk zu scannen ist langsam (viele Ordner)

**Lösung:** Einstellung für Scan-Tiefe

```python
# In Settings/Config
SCAN_DEPTH_OPTIONS = {
    "root_only": "Nur Laufwerk-Root (C:\, D:\, ...)",
    "one_level": "Root + 1 Ebene tiefer (C:\Test\, D:\Backup\, ...)",
    "two_levels": "Root + 2 Ebenen (C:\Users\Name\Documents\, ...)",
    "custom_paths": "Nur vordefinierte Pfade"
}

# In QSettings
self.settings.setValue("scan_depth", "one_level")
```

**Performance:**
- `root_only`: ~200ms (nur 26 Laufwerke A-Z)
- `one_level`: ~2-5s (abhängig von Ordneranzahl)
- `two_levels`: ~10-30s (kann sehr lange dauern)

**Default:** `one_level` (guter Kompromiss)

### 5. Recent Sessions Registry

**Alternative/Ergänzung:** Statt vollem Scan - zuletzt verwendete Pfade merken

```python
# In QSettings
recent_sessions = [
    {"path": "C:\Test", "last_used": "2025-12-13 14:30:00"},
    {"path": "D:\Backup", "last_used": "2025-12-10 09:15:00"},
    {"path": "E:\Storage\disktest", "last_used": "2025-12-05 18:45:00"}
]
```

**Vorteil:**
- Sehr schnell (keine Disk-Scans)
- Nur Pfade prüfen die User tatsächlich verwendet hat
- Funktioniert auch bei tiefen Ordnerstrukturen

**Nachteil:**
- Findet keine "vergessenen" Sessions
- Wenn User Session-Datei manuell verschiebt, nicht mehr auffindbar

**Empfehlung:** Kombination aus beidem:
1. Recent Sessions als "Quick List" prüfen (0.1s)
2. Optional: "Alle Laufwerke scannen" Button für Deep-Scan

## Technische Änderungen

### Betroffene Dateien

#### 1. `src/gui/test_controller.py`

**Neue Methoden:**
- `_scan_all_drives_for_sessions()` - Scannt Laufwerke A-Z
- `_check_path_for_session()` - Prüft einzelnen Pfad
- `_show_multi_session_dialog()` - Zeigt Auswahl-Dialog
- `_save_recent_session()` - Speichert in Registry
- `_load_recent_sessions()` - Lädt aus Registry

**Geänderte Methoden:**
- `_check_for_existing_session()` - Ruft jetzt Multi-Session-Scan auf
- `_show_drive_selection_dialog()` - Nach Auswahl Session-Check

#### 2. `src/gui/dialogs.py`

**Neuer Dialog:**
```python
class MultiSessionSelectionDialog(QDialog):
    """Dialog zur Auswahl zwischen mehreren Sessions"""

    RESULT_SESSION_SELECTED = 1
    RESULT_NEW_DRIVE = 2
    RESULT_CANCEL = 0

    def __init__(self, sessions: List[SessionInfo], parent=None):
        # Radio-Buttons für jede Session
        # "Neues Laufwerk" Option
        # Detaillierte Info-Anzeige

    def get_selected_session(self) -> Optional[SessionInfo]:
        """Gibt ausgewählte Session zurück"""
```

**Datenstruktur:**
```python
@dataclass
class SessionInfo:
    path: str
    type: str  # "session" oder "orphaned"

    # Für type="session"
    progress: Optional[float] = None
    pattern_index: Optional[int] = None
    pattern_name: Optional[str] = None
    error_count: Optional[int] = None
    file_count: Optional[int] = None

    # Für type="orphaned"
    detected_pattern: Optional[str] = None
    orphaned_file_count: Optional[int] = None
    total_size: Optional[int] = None

    # Metadata
    last_modified: Optional[str] = None
```

#### 3. `src/core/session.py`

**Keine strukturellen Änderungen nötig** - SessionManager funktioniert bereits pfad-basiert.

Optional: Hilfsmethode hinzufügen
```python
@staticmethod
def find_sessions_in_directory(directory: str, recursive: bool = False) -> List[Path]:
    """Findet alle disktest_session.json Dateien in Verzeichnis"""
    if recursive:
        return list(Path(directory).rglob(SessionManager.SESSION_FILENAME))
    else:
        return list(Path(directory).glob(SessionManager.SESSION_FILENAME))
```

#### 4. Settings/Config

**Neue Einstellungen** (optional, für Advanced Users):

```python
# Scan-Verhalten
self.settings.setValue("session_scan_enabled", True)
self.settings.setValue("session_scan_depth", "one_level")
self.settings.setValue("session_scan_timeout_ms", 5000)  # Abbruch nach 5s

# Recent Sessions (JSON)
self.settings.setValue("recent_sessions", json.dumps([...]))
self.settings.setValue("recent_sessions_max", 10)
```

**UI-Einstellungen-Dialog erweitern:**
```
[x] Beim Start nach Sessions auf allen Laufwerken suchen
    Scan-Tiefe: [Dropdown: Root + 1 Ebene]
    Timeout: [5000] ms
```

## Alternativen & Überlegungen

### Alternative 1: Nur Recent Sessions (kein Scan)
**Vorteil:** Schnell, keine Performance-Probleme
**Nachteil:** Findet keine "vergessenen" Sessions
**Empfehlung:** Als Hybrid-Lösung verwenden

### Alternative 2: Background-Scan
**Idee:** Scan läuft im Hintergrund, UI öffnet sofort
**Vorteil:** Keine Verzögerung beim Start
**Nachteil:** Komplexer, Session-Dialog erscheint asynchron
**Empfehlung:** Erst bei Performance-Problemen implementieren

### Alternative 3: Session-Index-Datei
**Idee:** Zentrale Datei in AppData mit allen Session-Pfaden
```
C:\Users\Name\AppData\Local\DiskTest\session_index.json
[
  {"path": "C:\Test", "last_modified": "..."},
  {"path": "D:\Backup", "last_modified": "..."}
]
```
**Vorteil:** Sehr schnell, keine Scans nötig
**Nachteil:** Kann out-of-sync sein wenn User Session manuell löscht
**Empfehlung:** Gute Ergänzung zu Recent Sessions

## Akzeptanzkriterien

- [ ] Beim Start werden alle Laufwerke nach Sessions gescannt (konfigurierbare Tiefe)
- [ ] Multi-Session-Dialog zeigt alle gefundenen Sessions mit Details
- [ ] "Neues Laufwerk wählen" Option im Dialog verfügbar
- [ ] Nach Laufwerk-Auswahl automatische Session-Prüfung
- [ ] Orphaned Files auf mehreren Laufwerken werden erkannt
- [ ] Recent Sessions werden in Registry gespeichert
- [ ] Scan-Timeout verhindert Hängen bei langsamen Laufwerken
- [ ] User kann Scan deaktivieren (Settings)
- [ ] Performance: Scan < 5s bei one_level Tiefe
- [ ] Bestehende Funktionalität bleibt erhalten (rückwärtskompatibel)

## Priorität

**Medium** - Komfort-Feature das besonders bei mehreren Laufwerken/Backups hilfreich ist. Aktuell ist Funktionalität vorhanden, aber umständlich (manuelles Navigieren nötig).

## Zusätzliche Hinweise

- **Windows-spezifisch:** Laufwerk-Enumeration A-Z ist Windows-Konvention
- **Performance:** Bei vielen Laufwerken/Ordnern kann Scan langsam sein → Timeout einbauen
- **UX:** User muss verstehen welche Session welche ist → Pfad + Timestamp anzeigen
- **Migration:** Keine Session-Datei-Änderungen nötig, nur UI-Flow
