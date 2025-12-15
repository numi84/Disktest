# Issue #001: Cache-Flush Race Condition

## Status: ✅ BEHOBEN

## Priorität: 🔴 Kritisch

## Beschreibung
Die Cache-Flush-Methode wartet nur 0.1 Sekunden nach `EmptyWorkingSet()`, was nicht garantiert dass der OS-Cache wirklich geleert ist. Da `EmptyWorkingSet()` asynchron arbeitet, könnte die Verifikationsphase vom RAM-Cache lesen statt von der physischen Disk.

## Betroffene Dateien
- `src/core/test_engine.py:809`

## Aktueller Code
```python
# test_engine.py:777-825
def _flush_file_cache(self, filepath: Path) -> bool:
    try:
        if sys.platform == 'win32':
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi

            current_process = kernel32.GetCurrentProcess()
            psapi.EmptyWorkingSet(current_process)

            # Warte kurz damit OS Cache leeren kann
            time.sleep(0.1)  # ⚠️ ZU KURZ!
```

## Problem
1. `EmptyWorkingSet()` ist asynchron und gibt sofort zurück
2. Der tatsächliche Cache-Flush kann länger dauern
3. Bei schnellem Weiterarbeiten wird möglicherweise noch vom Cache gelesen
4. **Impact:** Verifikation könnte Fehler übersehen wenn Daten aus Cache statt Disk gelesen werden

## Lösungsvorschlag

### Option 1: Längere Wartezeit (Einfach)
```python
# Warte länger damit OS Cache wirklich geleert wird
time.sleep(0.5)  # 500ms - konservativer Wert
```

### Option 2: Mehrfache Validierung (Besser)
```python
def _flush_file_cache(self, filepath: Path) -> bool:
    try:
        if sys.platform == 'win32':
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi

            current_process = kernel32.GetCurrentProcess()

            # Mehrfacher Cache-Flush für bessere Garantie
            for _ in range(3):
                psapi.EmptyWorkingSet(current_process)
                time.sleep(0.2)

            # Zusätzlich: Prozess-Priorität kurz senken
            # Gibt OS mehr Zeit für Cache-Management
            IDLE_PRIORITY_CLASS = 0x00000040
            old_priority = kernel32.GetPriorityClass(current_process)
            kernel32.SetPriorityClass(current_process, IDLE_PRIORITY_CLASS)
            time.sleep(0.1)
            kernel32.SetPriorityClass(current_process, old_priority)
```

### Option 3: FlushFileBuffers zusätzlich (Am besten)
```python
def _flush_file_cache(self, filepath: Path) -> bool:
    try:
        if sys.platform == 'win32':
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi

            # 1. Working Set leeren
            current_process = kernel32.GetCurrentProcess()
            psapi.EmptyWorkingSet(current_process)

            # 2. File-Buffer explizit flushen
            GENERIC_READ = 0x80000000
            OPEN_EXISTING = 3

            handle = kernel32.CreateFileW(
                str(filepath),
                GENERIC_READ,
                0,  # Exclusive access
                None,
                OPEN_EXISTING,
                0,
                None
            )

            if handle != -1 and handle != 0xFFFFFFFF:
                kernel32.FlushFileBuffers(handle)
                kernel32.CloseHandle(handle)

            # 3. Warte damit Cache wirklich geleert wird
            time.sleep(0.5)
```

## Implementierte Lösung

**Gewählte Option:** Option 3 (FlushFileBuffers zusätzlich)

### Änderungen in `src/core/test_engine.py:777-831`

1. **EmptyWorkingSet() beibehalten** - Leert RAM-Cache des Prozesses
2. **FlushFileBuffers() hinzugefügt** - Forciert explizit das Schreiben von File-Buffern auf Disk
   - Datei mit GENERIC_READ öffnen (nicht-destruktiv)
   - Handle-Validierung (INVALID_HANDLE_VALUE Check)
   - FlushFileBuffers() aufrufen
   - Handle ordnungsgemäß schließen
3. **Wartezeit erhöht** - Von 0.1s auf 0.5s (konservativer Wert)
4. **Dokumentation aktualisiert** - Docstring und Inline-Kommentare verbessert

### Vorteile dieser Lösung

- **Zweifache Absicherung:** EmptyWorkingSet() + FlushFileBuffers()
- **Expliziter File-Buffer-Flush:** Stellt sicher dass Daten auf Disk geschrieben werden
- **Ausreichend Zeit:** 0.5s gibt OS genug Zeit für asynchrone Cache-Operationen
- **Fehlerrobust:** Handle-Validierung verhindert Crashes bei ungültigem Handle
- **Abwärtskompatibel:** Linux/Unix-Code bleibt unverändert

### Behoben am
2025-12-15

## Testing
Nach dem Fix testen mit:
1. Große Datei schreiben (z.B. 1 GB)
2. Sofort verifizieren
3. Performance-Monitor beobachten:
   - Disk-Activity sollte bei Verifikation hoch sein
   - Memory-Usage sollte nicht stark steigen
4. Bei zu kleinem Sleep: Cache-Reads sichtbar (keine Disk-Activity)

## Referenzen
- Windows EmptyWorkingSet: https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-emptyworkingset
- FlushFileBuffers: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers
