# Issues - DiskTest Code Review

## Issue #1: Session-Datei Atomic Write [HOCH]
**Status:** BEHOBEN
**Datei:** `src/core/session.py:185-221`

Session-Datei wird ohne Atomic Write geschrieben. Bei Absturz während des Schreibens wird die Datei korrupt.

**Fix:** Atomic Write Pattern implementiert: Schreibt zuerst in .tmp-Datei, dann os.replace() für atomaren Austausch.

---

## Issue #2: Unvollständiger Read wird nicht erkannt [HOCH]
**Status:** BEHOBEN
**Datei:** `src/core/test_engine.py:521-527`

`f.read()` kann weniger Bytes zurückgeben als angefordert. Dies wird nicht geprüft und führt zu falschen Verifikationsfehlern.

**Fix:** Prüfung auf len(actual) != CHUNK_SIZE hinzugefügt mit spezifischer Fehlermeldung.

---

## Issue #3: Disk-Full nicht spezifisch behandelt [MITTEL]
**Status:** BEHOBEN
**Datei:** `src/core/test_engine.py:567-580`

Bei vollem Laufwerk wird versucht, mit nächster Datei weiterzumachen. Führt zu Fehlerkaskade.

**Fix:** Spezifische Behandlung für errno.ENOSPC (28), beendet Test statt weiterzumachen.

---

## Issue #4: Laufwerk-Entfernung nicht erkannt [MITTEL]
**Status:** BEHOBEN
**Datei:** `src/core/test_engine.py:567-580, 698-713`

OSError mit spezifischen errno-Werten (EIO, ENODEV, ENXIO) werden nicht erkannt.

**Fix:** Neue Handler _handle_disk_full() und _handle_drive_error() mit spezifischer Fehlerbehandlung.

---

## Issue #5: Verifikationsfehler ohne Details [MITTEL]
**Status:** BEHOBEN
**Datei:** `src/core/test_engine.py:826-863`

Bei Verifikationsfehler wird nur Chunk-Index geloggt, nicht welche Bytes abweichen.

**Fix:** Erweiterte _handle_verification_error() zeigt jetzt: Chunk, Offset, Datei-Offset (hex), erwartetes und gelesenes Byte.

---

## Issue #6: OS-Cache bei Verifikation [HOCH]
**Status:** BEHOBEN
**Datei:** `src/core/test_engine.py:727-787`

Verifikation könnte vom OS-Cache lesen statt von physischer Disk.

**Fix:** Neue Methode _flush_file_cache() die vor Verifikation aufgerufen wird. Windows: FlushFileBuffers, Linux: posix_fadvise mit DONTNEED.

---

## Issue #7: Pattern-Generator ohne Validierung bei Resume [NIEDRIG]
**Status:** BEHOBEN
**Datei:** `src/core/test_engine.py:270-342`

Bei Resume wird Generator-Konsistenz nicht validiert.

**Fix:** Neue Methode _validate_pattern_generator() prüft erstes Sample der Testdatei gegen erwartetes Pattern.

---

## Issue #8: Keine I/O Timeout-Warnung [NIEDRIG]
**Status:** BEHOBEN
**Datei:** `src/core/test_engine.py:506-516, 642-652`

Bei langsamen I/O-Operationen kann Test lange hängen ohne Feedback.

**Fix:** Warnung wenn Chunk länger als 30 Sekunden dauert (IO_TIMEOUT_WARNING_SECONDS).

---

# Changelog

| Datum | Issue | Status |
|-------|-------|--------|
| 2025-12-14 | Alle | Erstellt |
| 2025-12-14 | #1-#8 | BEHOBEN |
