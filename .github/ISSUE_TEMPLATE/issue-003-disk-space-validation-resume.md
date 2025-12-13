---
name: Fehlende Speicherplatz-Validierung beim Resume
about: Bug - Resume akzeptiert zu große Testgrößen ohne Validierung
title: 'Fehlende Speicherplatz-Validierung beim Resume'
labels: bug, critical, session-management
assignees: ''
---

## Problem / Bug

Beim Fortsetzen eines Tests mit vergrößerter Testgröße wird KEINE Speicherplatz-Validierung durchgeführt. Das führt dazu, dass der Test startet, obwohl nicht genug Speicher verfügbar ist, und später mit Disk-Full-Errors abbricht.

## Betroffene Version

Alle aktuellen Versionen

## Reproduktion

### Schritt-für-Schritt

1. **Test starten** mit 50 GB auf Laufwerk mit 60 GB freiem Speicher
2. Test läuft → erstellt z.B. 10 Dateien à 5 GB = 50 GB
3. Freier Speicher jetzt: ~10 GB
4. **Test pausieren**
5. **Testgröße erhöhen** auf 100 GB (Slider/Spinbox)
   - UI zeigt: "Freier Speicher: 60 GB" ✅ KORREKT (10 GB frei + 50 GB in Testdateien)
6. **Resume klicken**
   - ❌ KEINE Validierung
   - Test startet
7. **Test schreibt neue Dateien** (51. Datei, 52. Datei, ...)
8. **Nach ~10 GB → Disk Full Error** 💥

### Erwartetes Verhalten

Bei Schritt 6 sollte Dialog erscheinen:
```
┌───────────────────────────────────────────────┐
│  Nicht genügend Speicherplatz                 │
├───────────────────────────────────────────────┤
│  Angefordert: 100.0 GB                        │
│  Verfügbar: 60.0 GB                           │
│    (Frei: 10.0 GB + Testdateien: 50.0 GB)    │
│                                               │
│  Bitte reduzieren Sie die Testgröße oder     │
│  wählen Sie einen anderen Speicherort.        │
│                                               │
│                                [OK]           │
└───────────────────────────────────────────────┘
```

## Aktuelles Verhalten

### Neuer Test → Validierung vorhanden ✅

**Datei:** `src/gui/test_controller.py` (Zeilen 832-861)

```python
def _start_new_test(self):
    # ... Config laden ...

    # Speicherplatz prüfen
    try:
        disk_usage = shutil.disk_usage(config['target_path'])
        free_space_gb = disk_usage.free / (1024 ** 3)

        # Vorhandene Testdateien einrechnen
        from core.file_manager import FileManager
        file_size_gb = config['file_size_mb'] / 1024.0
        fm = FileManager(config['target_path'], file_size_gb)
        existing_size_gb = fm.get_existing_files_size() / (1024 ** 3)
        available_gb = free_space_gb + existing_size_gb  # ✅ KORREKT

        if config['test_size_gb'] > available_gb:
            QMessageBox.warning(
                self.window,
                "Nicht genügend Speicherplatz",
                f"Angefordert: {config['test_size_gb']:.1f} GB\n"
                f"Verfügbar: {available_gb:.1f} GB\n"
                f"  (Frei: {free_space_gb:.1f} GB + Testdateien: {existing_size_gb:.1f} GB)\n\n"
                "Bitte reduzieren Sie die Testgröße oder wählen Sie "
                "einen anderen Speicherort."
            )
            return
    except Exception as e:
        # ... Error Handling ...
```

**Berechnung:**
- `free_space_gb` = OS-freier Speicher
- `existing_size_gb` = Größe vorhandener Testdateien (werden überschrieben)
- `available_gb = free_space_gb + existing_size_gb` ✅

Diese Berechnung ist **korrekt**, weil vorhandene Testdateien beim Überschreiben Platz freigeben.

### Resume Test → KEINE Validierung ❌

**Datei:** `src/gui/test_controller.py` (Zeilen 915-990)

```python
def _resume_test(self):
    """Setzt pausierte Test fort"""
    if not self.engine:
        # Session laden
        session_manager = SessionManager(self.window.config_widget.path_edit.text())
        session_data = session_manager.load()

        # User kann Testgröße ändern
        current_config = self.window.config_widget.get_config()
        new_total_size_gb = current_config.get('test_size_gb', session_data.total_size_gb)

        # ❌ HIER FEHLT DISK SPACE CHECK!

        # Direkt Engine erstellen ohne Validierung
        test_config = TestConfig(
            target_path=session_data.target_path,
            file_size_gb=session_data.file_size_gb,
            total_size_gb=new_total_size_gb,  # Kann größer sein als verfügbar!
            resume_session=True,
            session_data=session_data,
            selected_patterns=new_selected_patterns
        )

        self.engine = TestEngine(test_config)
        self.engine.start()  # Startet ohne Prüfung!
```

**Problem:** User kann `test_size_gb` erhöhen, aber es gibt KEINE Validierung ob genug Platz vorhanden ist.

## Technische Analyse

### UI zeigt korrekten verfügbaren Speicher

**Datei:** `src/gui/main_window.py` (Zeilen 167-192)

```python
def _get_available_test_space(self, path: str) -> float:
    """Berechnet verfügbaren Speicher für Test inkl. vorhandener Testdateien."""
    if not path or not os.path.exists(path):
        return 0.0

    try:
        import shutil
        from core.file_manager import FileManager

        # OS-freier Speicher
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024 ** 3)

        # Größe vorhandener Testdateien
        file_size_gb = self.file_size_spinbox.value() / 1024.0  # MB to GB
        fm = FileManager(path, file_size_gb)
        existing_size_gb = fm.get_existing_files_size() / (1024 ** 3)

        return free_gb + existing_size_gb  # ✅ KORREKT
    except Exception:
        return 0.0
```

Die UI **berechnet** den verfügbaren Speicher korrekt und **zeigt** ihn auch korrekt an, aber **erzwingt** die Einhaltung nicht beim Resume.

### Vergleich: Neuer Test vs Resume

| Aspekt | Neuer Test (`_start_new_test`) | Resume (`_resume_test`) |
|--------|--------------------------------|-------------------------|
| **Disk Space Check** | ✅ Ja (Zeilen 832-854) | ❌ **FEHLT** |
| **Available Space Berechnung** | ✅ `free_gb + existing_size_gb` | ❌ Keine |
| **Validierung** | ✅ Warnung + Abbruch | ❌ Keine |
| **Existing Files berücksichtigt** | ✅ Ja | ❌ Nein |

## Lösungsvorschlag

### Option 1: Validierung in `_resume_test()` hinzufügen (Empfohlen)

**Änderung in `src/gui/test_controller.py`:**

```python
def _resume_test(self):
    """Setzt pausierte Test fort"""
    if not self.engine:
        session_manager = SessionManager(self.window.config_widget.path_edit.text())
        session_data = session_manager.load()

        current_config = self.window.config_widget.get_config()
        new_total_size_gb = current_config.get('test_size_gb', session_data.total_size_gb)

        # ✅ NEU: Speicherplatz-Validierung hinzufügen
        try:
            disk_usage = shutil.disk_usage(session_data.target_path)
            free_space_gb = disk_usage.free / (1024 ** 3)

            # Vorhandene Testdateien einrechnen
            from core.file_manager import FileManager
            fm = FileManager(session_data.target_path, session_data.file_size_gb)
            existing_size_gb = fm.get_existing_files_size() / (1024 ** 3)
            available_gb = free_space_gb + existing_size_gb

            if new_total_size_gb > available_gb:
                QMessageBox.warning(
                    self.window,
                    "Nicht genügend Speicherplatz",
                    f"Angefordert: {new_total_size_gb:.1f} GB\n"
                    f"Verfügbar: {available_gb:.1f} GB\n"
                    f"  (Frei: {free_space_gb:.1f} GB + Testdateien: {existing_size_gb:.1f} GB)\n\n"
                    "Bitte reduzieren Sie die Testgröße."
                )
                return  # Abbruch, Engine wird NICHT gestartet
        except Exception as e:
            QMessageBox.warning(
                self.window,
                "Fehler bei Speicherplatz-Prüfung",
                f"Konnte verfügbaren Speicher nicht ermitteln:\n{str(e)}"
            )
            return

        # Rest des Codes...
        test_config = TestConfig(...)
        self.engine = TestEngine(test_config)
        self.engine.start()
```

**Vorteil:** Code-Duplikation von `_start_new_test()`, aber funktioniert

### Option 2: Validierung in separate Methode auslagern (Best Practice)

```python
def _validate_disk_space(self, target_path: str, file_size_gb: float, test_size_gb: float) -> bool:
    """
    Prüft ob genug Speicherplatz verfügbar ist.

    Returns:
        True wenn genug Platz, False bei zu wenig Platz
    """
    try:
        disk_usage = shutil.disk_usage(target_path)
        free_space_gb = disk_usage.free / (1024 ** 3)

        from core.file_manager import FileManager
        fm = FileManager(target_path, file_size_gb)
        existing_size_gb = fm.get_existing_files_size() / (1024 ** 3)
        available_gb = free_space_gb + existing_size_gb

        if test_size_gb > available_gb:
            QMessageBox.warning(
                self.window,
                "Nicht genügend Speicherplatz",
                f"Angefordert: {test_size_gb:.1f} GB\n"
                f"Verfügbar: {available_gb:.1f} GB\n"
                f"  (Frei: {free_space_gb:.1f} GB + Testdateien: {existing_size_gb:.1f} GB)\n\n"
                "Bitte reduzieren Sie die Testgröße oder wählen Sie "
                "einen anderen Speicherort."
            )
            return False

        return True
    except Exception as e:
        QMessageBox.warning(
            self.window,
            "Fehler bei Speicherplatz-Prüfung",
            f"Konnte verfügbaren Speicher nicht ermitteln:\n{str(e)}"
        )
        return False

def _start_new_test(self):
    config = self.window.config_widget.get_config()

    # Validierung
    if not self._validate_disk_space(
        config['target_path'],
        config['file_size_mb'] / 1024.0,
        config['test_size_gb']
    ):
        return  # Validierung fehlgeschlagen

    # Rest des Codes...

def _resume_test(self):
    session_manager = SessionManager(self.window.config_widget.path_edit.text())
    session_data = session_manager.load()

    current_config = self.window.config_widget.get_config()
    new_total_size_gb = current_config.get('test_size_gb', session_data.total_size_gb)

    # Validierung
    if not self._validate_disk_space(
        session_data.target_path,
        session_data.file_size_gb,
        new_total_size_gb
    ):
        return  # Validierung fehlgeschlagen

    # Rest des Codes...
```

**Vorteil:**
- DRY (Don't Repeat Yourself)
- Einfacher zu testen
- Konsistente Fehlerbehandlung

## Betroffene Dateien

### Hauptdatei
- **`src/gui/test_controller.py`**
  - Zeile 915-990: `_resume_test()` - Validierung hinzufügen
  - Zeile 832-861: `_start_new_test()` - Ggf. in separate Methode extrahieren

### Hilfsdateien (bereits korrekt)
- **`src/gui/main_window.py`**
  - Zeilen 167-192: `_get_available_test_space()` - Funktioniert korrekt
- **`src/core/file_manager.py`**
  - `get_existing_files_size()` - Funktioniert korrekt

## Testfälle

### Test 1: Resume ohne Größenänderung
- Pausierter Test: 50 GB
- Freier Speicher: 60 GB
- Resume ohne Änderung
- ✅ Sollte funktionieren (genug Platz)

### Test 2: Resume mit Vergrößerung (genug Platz)
- Pausierter Test: 50 GB (50 GB in Dateien)
- Freier OS-Speicher: 20 GB
- Verfügbar: 70 GB (20 + 50)
- Erhöhe auf 70 GB
- ✅ Sollte funktionieren

### Test 3: Resume mit Vergrößerung (nicht genug Platz) ← BUG
- Pausierter Test: 50 GB (50 GB in Dateien)
- Freier OS-Speicher: 10 GB
- Verfügbar: 60 GB (10 + 50)
- Erhöhe auf 100 GB
- ❌ Aktuell: Test startet und crashed
- ✅ Nach Fix: Warnung + Abbruch

### Test 4: Resume mit Verkleinerung
- Pausierter Test: 100 GB
- Verkleinere auf 50 GB
- ✅ Sollte immer funktionieren (keine neue Speicheranforderung)

## Priorität

**CRITICAL** - Der Bug führt zu:
1. **Datenverlust** bei Disk-Full-Errors während des Tests
2. **Schlechte User Experience** - Test startet, crashed dann
3. **Inkonsistenz** - Neue Tests haben Validierung, Resume nicht
4. **Verschwendete Zeit** - User wartet auf Test der eh scheitert

## Akzeptanzkriterien

- [ ] `_resume_test()` validiert Speicherplatz vor Engine-Start
- [ ] Berechnung identisch zu `_start_new_test()`: `available_gb = free_gb + existing_size_gb`
- [ ] Bei zu wenig Platz: Warnung-Dialog + Abbruch (Engine startet NICHT)
- [ ] Bei Validierungs-Fehler: Fehler-Dialog + Abbruch
- [ ] Code-Duplikation minimiert (Option 2: Separate Validierungs-Methode)
- [ ] Alle 4 Testfälle funktionieren korrekt
- [ ] Keine Regression bei `_start_new_test()` Validierung

## Zusätzliche Hinweise

- **Root Cause:** Validierung wurde nur für neuen Test implementiert, Resume wurde übersehen
- **Quick Fix:** Code aus `_start_new_test()` kopieren (Option 1)
- **Clean Fix:** Refactoring in `_validate_disk_space()` Methode (Option 2)
- **Wichtig:** `available_gb = free_gb + existing_size_gb` ist die korrekte Formel!
