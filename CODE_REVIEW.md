# Code-Review: DiskTest - Datenzugriff & Fehlerszenarien

**Datum:** 2025-12-14
**Reviewer:** Claude Code Review

---

## 1. Datenzugriff - Verbesserungspotential

### 1.1 Fehlende Datenpersistenz-Garantien

**Betroffen:** `src/core/test_engine.py:412-418`

```python
with open(filepath, file_mode, buffering=self.IO_BUFFER_SIZE) as f:
    for chunk_idx in range(start_chunk, chunks_total):
        chunk = generator.generate_chunk(self.CHUNK_SIZE)
        f.write(chunk)  # <- Kein flush/fsync!
```

**Risiko:** Bei Systemabsturz könnten Daten im OS-Buffer verloren gehen. Die geschriebenen Daten sind nicht garantiert physisch auf der Disk.

**Empfehlung:**
```python
f.write(chunk)
if chunk_idx % 10 == 0:  # Alle 10 Chunks
    f.flush()
    os.fsync(f.fileno())  # Garantiert physisches Schreiben
```

**Abwägung:** `fsync()` reduziert Performance erheblich. Sinnvoll wäre eine Option "Sichere Schreibweise" für kritische Tests.

---

### 1.2 Session-Datei ohne Atomic Write

**Betroffen:** `src/core/session.py:194-200`

```python
with open(self.session_path, 'w', encoding='utf-8') as f:
    json.dump(session_dict, f, indent=2, ensure_ascii=False)
```

**Risiko:** Bei Absturz während des Schreibens wird die Session-Datei korrupt. Der User verliert seinen Fortschritt.

**Empfehlung:** Atomic Write Pattern implementieren:
```python
temp_path = self.session_path.with_suffix('.tmp')
with open(temp_path, 'w', encoding='utf-8') as f:
    json.dump(session_dict, f, indent=2, ensure_ascii=False)
    f.flush()
    os.fsync(f.fileno())
os.replace(temp_path, self.session_path)  # Atomic auf NTFS
```

**Priorität:** HOCH - Session-Verlust ist kritisch für Benutzer.

---

### 1.3 Verifikation liest möglicherweise vom OS-Cache

**Betroffen:** `src/core/test_engine.py:496-506`

```python
with open(filepath, 'rb', buffering=self.IO_BUFFER_SIZE) as f:
    actual = f.read(self.CHUNK_SIZE)
```

**Risiko:** Das Betriebssystem cached gelesene/geschriebene Daten. Bei der Verifikation könnte man vom Cache lesen statt von der physischen Disk - fehlerhafte Sektoren werden dann möglicherweise nicht erkannt!

**Empfehlung für Windows:**
1. Cache-Flush vor Verifikation pro Datei
2. Oder: `FILE_FLAG_NO_BUFFERING` über `ctypes` bei Windows für echte Disk-Reads

**Hinweis:** Linux hat `os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)`, Windows benötigt P/Invoke.

---

### 1.4 Unvollständige Read-Prüfung

**Betroffen:** `src/core/test_engine.py:506`

```python
actual = f.read(self.CHUNK_SIZE)
```

**Risiko:** `f.read(n)` kann weniger als `n` Bytes zurückgeben (z.B. bei Netzlaufwerken, USB-Disconnects, EOF). Der Code prüft dies nicht.

**Empfehlung:**
```python
actual = f.read(self.CHUNK_SIZE)
if len(actual) != self.CHUNK_SIZE:
    self._handle_read_error(filepath,
        Exception(f"Unvollständiger Read: {len(actual)}/{self.CHUNK_SIZE} Bytes"))
    return False
```

**Priorität:** HOCH - Kann zu falschen Verifikationsfehlern führen.

---

## 2. Nicht erkannte Fehlerszenarien

### 2.1 Laufwerk wird während Test entfernt

**Betroffen:** `src/core/test_engine.py:412`, `src/core/test_engine.py:497`

Der Code fängt generelle `Exception` ab, aber:
- Keine spezifische Behandlung für `OSError [Errno 5]` (I/O Error)
- Keine Prüfung ob Laufwerk noch existiert nach Fehler
- User bekommt unspezifische Fehlermeldung

**Empfehlung:**
```python
except OSError as e:
    if e.errno in (5, 22, 1):  # I/O Error, Invalid argument, Operation not permitted
        self._handle_drive_disconnected(filepath)
        return False
    raise
```

---

### 2.2 Datei wurde extern modifiziert

**Problem:** Keine Prüfung ob die Testdatei zwischen Schreiben und Verifizieren geändert wurde (z.B. durch Antivirus, User, andere Prozesse).

**Empfehlung:** mtime/ctime prüfen vor Verifikation:
```python
stat_before = filepath.stat()
# ... Verifikation ...
stat_after = filepath.stat()
if stat_before.st_mtime != stat_after.st_mtime:
    self.logger.warning(f"{filepath.name} wurde während Verifikation geändert")
```

---

### 2.3 Laufwerk voll während des Tests

**Betroffen:** `src/core/test_engine.py:474-476`

```python
except Exception as e:
    self._handle_write_error(filepath, e)
    return True  # Weitermachen mit nächster Datei
```

**Risiko:** Bei "Disk Full" wird versucht, mit der nächsten Datei weiterzumachen - das wird auch fehlschlagen. Unnötige Fehlerkaskade.

**Empfehlung:**
```python
except OSError as e:
    if e.errno == 28:  # ENOSPC - No space left
        self._handle_disk_full()
        return False  # Test beenden statt weitermachen
    self._handle_write_error(filepath, e)
    return True
```

---

### 2.4 Pattern-Generator Konsistenz bei Resume

**Betroffen:** `src/core/test_engine.py:407-408`

```python
for _ in range(start_chunk):
    generator.generate_chunk(self.CHUNK_SIZE)
```

**Risiko:** Wenn der Random-Seed in der Session korrupt ist, wird eine falsche Sequenz generiert. Die Verifikation schlägt dann fälschlicherweise für ALLE Dateien fehl.

**Empfehlung:** Validierung nach Generator-Setup:
```python
# Prüfe ersten Chunk gegen vorhandene Datei
with open(filepath, 'rb') as f:
    first_chunk = f.read(1024)

gen_test = PatternGenerator(pattern_type, seed=self.session.random_seed)
expected_sample = gen_test.generate_chunk(1024)

if first_chunk != expected_sample:
    self.logger.error(f"Generator-Konsistenz-Fehler - Seed möglicherweise korrupt")
```

---

### 2.5 Verifikationsfehler ohne Details

**Betroffen:** `src/core/test_engine.py:510-511`

```python
if expected != actual:
    self._handle_verification_error(filepath, chunk_idx)
```

**Risiko:** Bei einem Verifikationsfehler wird nur der Chunk geloggt, aber nicht WELCHE Bytes abweichen. Für Diagnose bei echten Disk-Fehlern wäre das wichtig.

**Empfehlung:**
```python
if expected != actual:
    # Finde erste abweichende Position
    first_diff = next((i for i, (e, a) in enumerate(zip(expected, actual)) if e != a), None)

    self._handle_verification_error(
        filepath, chunk_idx,
        first_diff_offset=chunk_idx * self.CHUNK_SIZE + first_diff,
        expected_byte=expected[first_diff] if first_diff else None,
        actual_byte=actual[first_diff] if first_diff else None
    )
```

---

### 2.6 Fehlende Timeout-Behandlung bei I/O

**Problem:** Keine Timeouts bei I/O-Operationen.

**Risiko:** Bei Laufwerks-Problemen (z.B. sterbende HDD mit langen Read-Retries, "Click of Death") kann der Test unendlich hängen.

**Empfehlung:**
1. Chunk-Zeit messen und User warnen wenn > X Sekunden
2. Oder: Timeout-Thread mit kill-Option anbieten

---

### 2.7 FileAnalyzer: Race Condition bei Analyse

**Betroffen:** `src/core/file_analyzer.py:108-109`

```python
actual_size = filepath.stat().st_size
# ... Zeit vergeht ...
detected_pattern = self._detect_pattern(filepath)  # Datei könnte verändert sein
```

**Risiko:** Datei könnte zwischen `stat()` und Pattern-Erkennung geändert werden.

**Empfehlung:** Datei mit Share-Lock öffnen oder Exception handling verbessern.

---

### 2.8 Log-Datei Standardpfad

**Betroffen:** `src/core/test_engine.py:104`

**Problem:** Log-Datei wird standardmäßig auf dem gleichen Laufwerk wie der Test gespeichert. Bei Laufwerks-Problemen geht auch das Log verloren.

**Status:** Option `log_in_userdir` existiert, ist aber nicht Default.

**Empfehlung:** Bei Erkennung von Schreibfehlern automatisch auf User-Verzeichnis wechseln.

---

## 3. Zusammenfassung der Prioritäten

| Priorität | Problem | Aufwand | Zeile |
|-----------|---------|---------|-------|
| **HOCH** | Session-Datei Atomic Write | Niedrig | session.py:194 |
| **HOCH** | Unvollständiger Read-Check | Niedrig | test_engine.py:506 |
| **HOCH** | OS-Cache bei Verifikation | Mittel | test_engine.py:496 |
| **MITTEL** | Laufwerk-Entfernung erkennen | Niedrig | test_engine.py:474 |
| **MITTEL** | Disk-Full graceful handling | Niedrig | test_engine.py:474 |
| **MITTEL** | Verifikationsfehler Details | Niedrig | test_engine.py:510 |
| **NIEDRIG** | fsync nach Chunks | Niedrig | test_engine.py:418 |
| **NIEDRIG** | Pattern-Generator Validierung | Mittel | test_engine.py:407 |
| **NIEDRIG** | I/O Timeout-Warnung | Mittel | test_engine.py:416 |

---

## 4. Positiv hervorzuheben

- Gute Chunk-basierte Verarbeitung mit Progress-Updates
- Session-Wiederherstellung funktioniert robust
- Pattern-Generator mit Seed für Reproduzierbarkeit
- Saubere Trennung von GUI und Core-Logik
- Thread-sichere Events für Pause/Stop
- Gute Fehler-Kategorisierung im FileAnalyzer

---

## 5. Empfohlene nächste Schritte

1. **Quick Wins** (1-2h):
   - Atomic Write für Session-Datei
   - Read-Length-Check hinzufügen
   - Disk-Full spezifisch behandeln

2. **Mittelfristig** (4-8h):
   - Cache-Bypass für Verifikation unter Windows
   - Detaillierte Verifikationsfehler
   - Drive-Disconnect-Erkennung

3. **Langfristig**:
   - Optional: Direct I/O Modus für echte Disk-Tests
   - Timeout-Überwachung mit User-Feedback
