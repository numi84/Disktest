# DiskTest - Bekannte Probleme

Dokumentation der aufgefallenen Probleme beim Testen der Anwendung.

---

## Issue #1: Muster überschreiben nicht alle Dateien korrekt

**Status:** Behoben
**Priorität:** Kritisch
**Komponente:** `src/core/test_engine.py`

### Beschreibung
Beim ersten Muster (0x00) werden mehrere Testdateien korrekt erstellt. Bei den nachfolgenden Mustern (0xFF, 0xAA, etc.) wird jedoch nur die letzte Datei überschrieben, während die anderen Dateien als fehlerhaft gekennzeichnet werden.

### Erwartetes Verhalten
Alle existierenden Testdateien sollten bei jedem Muster vollständig überschrieben werden:
1. Muster 1 (0x00): Alle Dateien schreiben → Alle Dateien verifizieren
2. Muster 2 (0xFF): Alle Dateien überschreiben → Alle Dateien verifizieren
3. ... und so weiter für alle 5 Muster

### Tatsächliches Verhalten
- Muster 1: Alle Dateien OK
- Muster 2+: Nur letzte Datei wird überschrieben, restliche Dateien zeigen Verifikationsfehler

### Mögliche Ursache
Vermutlich liegt das Problem in der Schreib-Logik (`_write_pattern` Methode, [test_engine.py:247-286](src/core/test_engine.py#L247-L286)):
- Die Skip-Logik für Resume könnte auch neue Muster betreffen
- Zeile 265-268: Die Bedingung überspringt möglicherweise fälschlicherweise Dateien

### Betroffener Code
```python
# test_engine.py, Zeile 265-268
if (self.session.current_pattern_index == pattern_idx and
    self.session.current_phase == "write" and
    file_idx < self.session.current_file_index):
    continue
```

### Reproduktion
1. Test mit mehreren Dateien starten (z.B. 3 GB mit 1 GB Dateigröße)
2. Erstes Muster abwarten
3. Beobachten dass beim zweiten Muster nur die letzte Datei beschrieben wird

### Lösung
Das Problem lag darin, dass die Skip-Logik den aktuellen Session-State nutzte statt den initialen Resume-Punkt. Nach Abschluss des ersten Musters war `current_file_index` noch auf dem letzten Wert, und da `current_pattern_index` sofort auf das neue Muster gesetzt wird, wurden Dateien fälschlicherweise übersprungen.

**Fix:** Neue Variablen `_initial_resume_pattern`, `_initial_resume_phase` und `_initial_resume_file` speichern den ursprünglichen Resume-Punkt. Die Skip-Logik in `_write_pattern` und `_verify_pattern` nutzt nun diese Werte statt des aktuellen Session-States.

---

## Issue #2: Testgröße unter 1 GB nicht möglich

**Status:** Behoben
**Priorität:** Mittel
**Komponente:** `src/gui/main_window.py`, `src/core/file_manager.py`

### Beschreibung
Die Benutzeroberfläche erlaubt aktuell nur die Konfiguration von Tests mit mindestens 1 GB Gesamtgröße. Kleinere Tests für schnelle Funktionstests oder kleine USB-Sticks sind nicht möglich.

### Erwartetes Verhalten
- Testgröße sollte ab 100 MB konfigurierbar sein
- Dateigröße sollte flexibel anpassbar sein (z.B. auch 100 MB, 200 MB)
- Für Tests < 1 GB sollten entsprechend kleinere Testdateien erstellt werden

### Tatsächliches Verhalten
- Minimale Testgröße: 1 GB
- Dateigröße fest auf MB-Basis, aber UI zeigt nur GB für Testgröße

### Betroffener Code
[main_window.py:60-72](src/gui/main_window.py#L60-L72) - ConfigurationWidget:
```python
self.size_slider.setMinimum(1)  # Minimum 1 GB
self.size_spinbox.setMinimum(1)
self.size_spinbox.setSuffix(" GB")
```

[main_window.py:83-89](src/gui/main_window.py#L83-L89) - Dateigröße:
```python
self.file_size_spinbox.setMinimum(100)  # 100 MB
self.file_size_spinbox.setMaximum(10000)  # 10 GB
self.file_size_spinbox.setValue(1000)  # 1 GB default
```

### Lösungsansatz
1. Testgröße in MB statt GB anbieten (oder umschaltbar)
2. Minimum auf 100 MB setzen
3. Dateigröße entsprechend anpassen, dass mindestens 1 Testdatei erstellt wird
4. Validierung einbauen: Testgröße >= Dateigröße

### Lösung
`QSpinBox` wurde durch `QDoubleSpinBox` ersetzt, um Dezimalwerte zu ermöglichen:
- Minimum: 0.1 GB (= 100 MB)
- Dezimalstellen: 1
- Schrittweite: 0.1 GB

Die Slider-SpinBox-Synchronisation wurde angepasst, da der Slider nur Ganzzahlen unterstützt. Für Werte unter 1 GB kann die SpinBox direkt verwendet werden.

---

## Issue #3: Resume-Funktion funktioniert nicht nach Programm-Neustart

**Status:** Behoben
**Priorität:** Hoch
**Komponente:** `src/core/session.py`, `src/gui/test_controller.py`

### Beschreibung
Wenn das Programm während eines laufenden Tests beendet und später neu gestartet wird, kann die Session nicht korrekt wiederhergestellt werden. Die Resume-Funktion funktioniert nicht wie erwartet.

### Erwartetes Verhalten
1. Test läuft
2. Programm wird geschlossen (Session wird in `disktest_session.json` gespeichert)
3. Programm wird neu gestartet
4. User wird gefragt ob Session fortgesetzt werden soll
5. Test setzt exakt an der Stelle fort wo er unterbrochen wurde

### Tatsächliches Verhalten
Nach Programm-Neustart:
- Session-Datei existiert, wird aber nicht erkannt/angeboten
- Oder: Resume schlägt fehl mit Fehlern

### Mögliche Ursache
- Session-Wiederherstellung wird möglicherweise beim Programmstart nicht geprüft
- Die Resume-Logik in `_resume_from_session()` könnte fehlerhaft sein
- Generator-State (besonders für Random-Pattern) wird nicht korrekt wiederhergestellt

### Betroffener Code
[test_engine.py:203-228](src/core/test_engine.py#L203-L228) - `_resume_from_session()` Methode

### Zu prüfen
1. Wird beim Programmstart die Session-Datei gesucht?
2. Wird der User zum Resume aufgefordert?
3. Werden alle State-Variablen korrekt wiederhergestellt?
4. Werden Pattern-Generatoren korrekt auf die richtige Position gebracht?

### Lösung
Das Problem war, dass beim Programmstart kein Pfad im UI eingestellt war, daher wurde `_check_for_existing_session()` nichts gefunden.

**Fix:** Der zuletzt verwendete Pfad wird nun in `QSettings` gespeichert und beim Programmstart automatisch geladen:
- `_save_last_path()`: Speichert Pfad beim Test-Start
- `_load_last_path()`: Lädt Pfad beim Programmstart
- `_update_delete_button()` wird am Ende von `__init__` aufgerufen

---

## Issue #4: Speicherort der Log-Dateien nicht konfigurierbar

**Status:** Behoben
**Priorität:** Niedrig
**Komponente:** `src/utils/logger.py`

### Beschreibung
Log-Dateien werden immer im zu testenden Zielpfad gespeichert. Es gibt keine Möglichkeit, einen alternativen Speicherort zu konfigurieren.

### Erwartetes Verhalten
- Default: Log-Dateien werden im Zielpfad gespeichert (aktuelles Verhalten)
- Option: User kann alternativen Speicherort für Logs wählen
- Sinnvoll wenn das Ziellaufwerk problematisch ist oder wenig Platz hat

### Tatsächliches Verhalten
Log-Dateien werden immer hier erstellt:
- `{target_path}/disktest_YYYYMMDD_HHMMSS.log`

### Lösungsansatz
1. Neues Konfigurationsfeld in UI: "Log-Speicherort"
2. Default: "Zielpfad" (Checkbox oder Radio-Button)
3. Optional: Anderen Pfad wählen
4. Logger-Klasse erweitern um konfigurierbaren Pfad

### Betroffener Code
- [logger.py](src/utils/logger.py) - DiskTestLogger Klasse
- [main_window.py](src/gui/main_window.py) - ConfigurationWidget erweitern

### Lösung
Neue Checkbox "Logs im Benutzerordner speichern" hinzugefügt:
- Wenn aktiviert, werden Logs im Verzeichnis `~/DiskTest_Logs/` gespeichert
- `TestConfig` hat neuen Parameter `log_dir`
- `TestEngine` nutzt `log_dir` wenn angegeben, sonst `target_path`
- `_get_user_log_dir()` erstellt das Verzeichnis bei Bedarf

---

## Issue #5: "Dateien löschen" Button funktioniert nicht

**Status:** Behoben
**Priorität:** Mittel
**Komponente:** `src/gui/test_controller.py`, `src/core/file_manager.py`

### Beschreibung
Der "🗑 Dateien löschen" Button in der Steuerung ist sichtbar, aber funktioniert nicht. Testdateien können nicht über die GUI gelöscht werden.

### Erwartetes Verhalten
1. Button wird aktiviert wenn Testdateien existieren
2. Beim Klick öffnet sich ein Bestätigungsdialog
3. Nach Bestätigung werden alle `disktest_*.dat` Dateien gelöscht
4. Erfolgs-/Fehlermeldung wird angezeigt
5. Log-Eintrag wird erstellt

### Tatsächliches Verhalten
- Button ist meist deaktiviert
- Oder: Beim Klick passiert nichts

### Mögliche Ursache
Die Delete-Funktionalität existiert in FileManager ([file_manager.py:83-103](src/core/file_manager.py#L83-L103)), wird aber vermutlich nicht mit dem Button-Signal verbunden:

```python
def delete_test_files(self) -> tuple[int, int]:
    """Löscht alle Testdateien im Zielpfad"""
    deleted = 0
    errors = 0
    # ... Implementation vorhanden
```

### Zu prüfen
1. Ist das Signal `delete_files_clicked` mit einer Handler-Methode verbunden?
2. Wird der Button-State korrekt aktualisiert wenn Dateien existieren?
3. Wird ein Bestätigungsdialog angezeigt?

### Betroffener Code
- [main_window.py:234](src/gui/main_window.py#L234) - `delete_files_clicked` Signal
- `test_controller.py` - Handler für Delete-Operation fehlt vermutlich
- [file_manager.py:83-103](src/core/file_manager.py#L83-L103) - Delete-Implementation (vorhanden)

### Lösung
Zwei Probleme wurden behoben:
1. **Falscher Methodenname:** `delete_all_files()` wurde zu `delete_test_files()` korrigiert (die Methode im FileManager heißt `delete_test_files`)
2. **Button-Status:** `_update_delete_button()` wird nun am Ende von `__init__` aufgerufen, sodass der Button beim Start korrekt aktiviert wird wenn Testdateien existieren

---

## Zusammenfassung

| # | Titel | Priorität | Status |
|---|-------|-----------|--------|
| 1 | Muster überschreiben nicht alle Dateien | Kritisch | **Behoben** |
| 2 | Keine Tests < 1 GB möglich | Mittel | **Behoben** |
| 3 | Resume nach Neustart funktioniert nicht | Hoch | **Behoben** |
| 4 | Log-Speicherort nicht konfigurierbar | Niedrig | **Behoben** |
| 5 | Dateien löschen Button funktioniert nicht | Mittel | **Behoben** |

**Alle 5 Issues wurden behoben.**
