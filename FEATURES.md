# DiskTest - Feature-Spezifikation

## Übersicht

| Feature | Priorität | Status |
|---------|-----------|--------|
| Testdateien erstellen & verifizieren | Must-Have | Geplant |
| Mehrere Testmuster | Must-Have | Geplant |
| Fortschrittsanzeige | Must-Have | Geplant |
| Pause/Resume | Must-Have | Geplant |
| Session-Wiederherstellung | Must-Have | Geplant |
| Error-Logging | Must-Have | Geplant |
| Geschwindigkeitsanzeige | Nice-to-Have | Geplant |
| Manuelle Datei-Löschung | Must-Have | Geplant |

---

## Feature 1: Testdateien erstellen & verifizieren

### Beschreibung
Das Kernfeature - Schreiben von Testdateien mit bekannten Bitmustern und anschließende Verifikation durch Zurücklesen.

### Ablauf
1. User wählt Zielpfad
2. User gibt Testgröße an (oder "ganzes Laufwerk")
3. Programm berechnet Anzahl der Testdateien
4. Für jedes Muster:
   - Alle Dateien mit Muster schreiben
   - Alle Dateien verifizieren (zurücklesen und vergleichen)

### Technische Details

**Datei-Erstellung:**
```python
# Chunk-basiertes Schreiben
CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB

def write_file(filepath, pattern_generator, file_size):
    chunks_total = file_size // CHUNK_SIZE
    with open(filepath, 'wb') as f:
        for i in range(chunks_total):
            chunk = pattern_generator.generate_chunk(CHUNK_SIZE)
            f.write(chunk)
            # Progress update
```

**Verifikation:**
```python
def verify_file(filepath, pattern_generator, file_size):
    pattern_generator.reset()  # Wichtig für Random!
    chunks_total = file_size // CHUNK_SIZE
    with open(filepath, 'rb') as f:
        for i in range(chunks_total):
            expected = pattern_generator.generate_chunk(CHUNK_SIZE)
            actual = f.read(CHUNK_SIZE)
            if expected != actual:
                return False, f"Chunk {i} fehlerhaft"
    return True, None
```

### Akzeptanzkriterien
- [ ] Testdateien werden korrekt erstellt
- [ ] Dateigröße ist konfigurierbar (Default: 1 GB)
- [ ] Verifikation erkennt fehlerhafte Daten zuverlässig
- [ ] Bei Verifikationsfehler wird die betroffene Datei geloggt

---

## Feature 2: Testmuster

### Beschreibung
Fünf verschiedene Bitmuster für umfassende Tests, analog zu `badblocks`.

### Muster

| ID | Name | Hex-Wert | Binär | Zweck |
|----|------|----------|-------|-------|
| 1 | Zero | 0x00 | 00000000 | Alle Bits auf 0 |
| 2 | One | 0xFF | 11111111 | Alle Bits auf 1 |
| 3 | Alt-AA | 0xAA | 10101010 | Alternierende Bits |
| 4 | Alt-55 | 0x55 | 01010101 | Alternierende Bits (invertiert) |
| 5 | Random | - | - | Zufallsdaten |

### Reihenfolge
Die Muster werden in der oben genannten Reihenfolge durchlaufen.

### Random-Muster Details
- Seed wird beim Test-Start generiert
- Seed wird in Session gespeichert
- Bei Verifikation: Generator mit gleichem Seed neu initialisieren
- Damit 100% reproduzierbar

### Akzeptanzkriterien
- [ ] Alle 5 Muster werden durchlaufen
- [ ] Reihenfolge ist fix: 0x00 → 0xFF → 0xAA → 0x55 → Random
- [ ] Random-Muster ist bei Verifikation reproduzierbar
- [ ] Aktuelles Muster wird in GUI angezeigt

---

## Feature 3: Fortschrittsanzeige

### Beschreibung
Detaillierte Fortschrittsanzeige für User-Feedback.

### Anzuzeigende Informationen

**Gesamtfortschritt:**
- Prozentuale Anzeige (0-100%)
- Fortschrittsbalken
- Geschätzte Restzeit

**Aktueller Durchlauf:**
- Aktuelles Muster (z.B. "Muster 2/5: 0xFF")
- Aktuelle Phase (Schreiben/Verifizieren)
- Aktuelle Datei (z.B. "Datei 23/50")
- Aktuelle Geschwindigkeit (MB/s)

### Berechnung Gesamtfortschritt
```python
# Pro Muster: Schreiben + Verifizieren = 2 Phasen
# 5 Muster × 2 Phasen = 10 Phasen gesamt

total_phases = 10
current_phase = (pattern_index * 2) + (1 if verifying else 0)
phase_progress = current_file / total_files

overall_progress = (current_phase + phase_progress) / total_phases * 100
```

### Akzeptanzkriterien
- [ ] Gesamtfortschritt wird korrekt berechnet
- [ ] Fortschrittsbalken aktualisiert sich flüssig
- [ ] Geschätzte Restzeit ist einigermaßen genau
- [ ] Geschwindigkeit wird in MB/s angezeigt

---

## Feature 4: Pause/Resume

### Beschreibung
Test kann jederzeit pausiert und später fortgesetzt werden.

### Verhalten bei Pause
1. Aktuellen Chunk fertig schreiben/lesen
2. Session-State speichern
3. UI zeigt "Pausiert" an
4. "Pause"-Button wird zu "Fortsetzen"

### Session-State (wird gespeichert)
- Zielpfad
- Konfiguration (Dateigröße, Gesamtgröße)
- Aktuelles Muster (Index 0-4)
- Aktuelle Datei (Index)
- Aktuelle Phase (write/verify)
- Aktueller Chunk (Position in Datei)
- Random-Seed
- Bisherige Fehler
- Bisherige Laufzeit

### Verhalten bei Resume
1. Session-Datei laden
2. Zustand wiederherstellen
3. Exakt an Pause-Position fortfahren

### Akzeptanzkriterien
- [ ] Pause stoppt nach aktuellem Chunk
- [ ] Session wird zuverlässig gespeichert
- [ ] Resume setzt exakt an Pause-Position fort
- [ ] Random-Muster funktioniert auch nach Resume korrekt

---

## Feature 5: Session-Wiederherstellung beim Start

### Beschreibung
Beim Programmstart erkennen, ob eine vorherige Session existiert.

### Ablauf
```
Programmstart
    │
    ├── Prüfe: Existiert disktest_session.json?
    │
    ├── Ja ──► Dialog anzeigen:
    │          "Eine vorherige Test-Session wurde gefunden.
    │           Ziel: D:\
    │           Fortschritt: 45%
    │           Möchten Sie fortsetzen?"
    │           [Fortsetzen] [Neuer Test] [Abbrechen]
    │
    └── Nein ► Normaler Start
```

### Dialog-Optionen
- **Fortsetzen:** Session laden und Test fortsetzen
- **Neuer Test:** Session-Datei löschen, normal starten
- **Abbrechen:** Dialog schließen, nichts tun

### Akzeptanzkriterien
- [ ] Session wird beim Start erkannt
- [ ] Dialog zeigt relevante Infos (Pfad, Fortschritt)
- [ ] "Fortsetzen" funktioniert korrekt
- [ ] "Neuer Test" löscht alte Session

---

## Feature 6: Error-Logging

### Beschreibung
Ausführliches Logging aller Aktivitäten und Fehler.

### Log-Datei
- **Speicherort:** Programmverzeichnis
- **Name:** `disktest_YYYYMMDD_HHMMSS.log`
- **Format:** Timestamp + Level + Message

### Log-Levels

| Level | Verwendung |
|-------|------------|
| INFO | Normale Aktivitäten (Start, Konfiguration) |
| SUCCESS | Erfolgreiche Operationen (Datei geschrieben, verifiziert) |
| WARNING | Nicht-kritische Probleme |
| ERROR | Fehler (Verifikation fehlgeschlagen, Schreibfehler) |

### Beispiel-Log
```
[2024-12-07 14:30:22] INFO    ════════════════════════════════════════
[2024-12-07 14:30:22] INFO    DiskTest gestartet
[2024-12-07 14:30:22] INFO    ════════════════════════════════════════
[2024-12-07 14:30:22] INFO    Ziel: D:\
[2024-12-07 14:30:22] INFO    Dateigröße: 1 GB
[2024-12-07 14:30:22] INFO    Anzahl Dateien: 50
[2024-12-07 14:30:22] INFO    Gesamtgröße: 50 GB
[2024-12-07 14:30:22] INFO    ────────────────────────────────────────
[2024-12-07 14:30:22] INFO    Starte Muster 1/5: 0x00
[2024-12-07 14:30:22] INFO    Phase: Schreiben
[2024-12-07 14:35:44] SUCCESS disktest_001.dat - Schreiben abgeschlossen (180 MB/s)
[2024-12-07 14:41:02] SUCCESS disktest_002.dat - Schreiben abgeschlossen (175 MB/s)
...
[2024-12-07 15:30:00] INFO    Phase: Verifizieren
[2024-12-07 15:35:22] SUCCESS disktest_001.dat - Verifizierung OK
[2024-12-07 15:40:44] ERROR   disktest_023.dat - Verifizierung FEHLGESCHLAGEN
[2024-12-07 15:40:44] ERROR   Details: Chunk 156 - Daten stimmen nicht überein
...
[2024-12-07 20:00:00] INFO    ════════════════════════════════════════
[2024-12-07 20:00:00] INFO    Test abgeschlossen
[2024-12-07 20:00:00] INFO    Dauer: 5h 29m 38s
[2024-12-07 20:00:00] INFO    Fehler: 1
[2024-12-07 20:00:00] INFO    ════════════════════════════════════════
```

### GUI-Log-Ausgabe
- Scrollbares Textfeld
- Farbcodierung nach Level (Rot für ERROR, Grün für SUCCESS, etc.)
- Auto-Scroll zu neuesten Einträgen
- Optional: Filter nach Level

### Akzeptanzkriterien
- [ ] Log-Datei wird erstellt
- [ ] Alle Operationen werden geloggt
- [ ] Timestamps sind korrekt
- [ ] Erfolgreiche UND fehlerhafte Operationen werden geloggt
- [ ] Log wird in GUI angezeigt

---

## Feature 7: Geschwindigkeitsanzeige

### Beschreibung
Anzeige der aktuellen Schreib-/Lesegeschwindigkeit.

### Berechnung
```python
# Gleitender Durchschnitt über letzte N Chunks
SPEED_WINDOW = 10  # Chunks

def calculate_speed(chunk_times: list[float]) -> float:
    recent = chunk_times[-SPEED_WINDOW:]
    avg_time = sum(recent) / len(recent)
    return CHUNK_SIZE / avg_time / (1024 * 1024)  # MB/s
```

### Anzeige
- Aktuelle Geschwindigkeit: "185.3 MB/s"
- Durchschnittliche Geschwindigkeit (optional)

### Akzeptanzkriterien
- [ ] Geschwindigkeit wird berechnet und angezeigt
- [ ] Anzeige ist stabil (nicht zu viel Flackern)
- [ ] Einheit ist MB/s

---

## Feature 8: Manuelle Datei-Löschung

### Beschreibung
Testdateien werden NICHT automatisch gelöscht. User muss sie manuell löschen.

### GUI-Element
- Button "Testdateien löschen" (nur aktiv wenn Test abgeschlossen/gestoppt)
- Bestätigungs-Dialog vor Löschung

### Ablauf
```
User klickt "Testdateien löschen"
    │
    ▼
Dialog: "Möchten Sie alle Testdateien löschen?
         Pfad: D:\
         Anzahl: 50 Dateien
         Größe: 50 GB"
         [Löschen] [Abbrechen]
    │
    ├── Löschen ──► Dateien löschen, Status anzeigen
    │
    └── Abbrechen ► Nichts tun
```

### Akzeptanzkriterien
- [ ] Testdateien bleiben nach Test erhalten
- [ ] Button zum Löschen ist vorhanden
- [ ] Bestätigungs-Dialog wird angezeigt
- [ ] Löschung funktioniert und wird bestätigt

---

## Konfigurationsoptionen

### Vom User einstellbar

| Option | Default | Bereich | Beschreibung |
|--------|---------|---------|--------------|
| Zielpfad | - | Gültiger Pfad | Wo Testdateien erstellt werden |
| Testgröße | Ganzes Laufwerk | 1 GB - Freier Speicher | Wie viel getestet wird |
| Dateigröße | 1 GB | 100 MB - 10 GB | Größe einer Testdatei |

### Fest konfiguriert (nicht änderbar)

| Option | Wert | Grund |
|--------|------|-------|
| Chunk-Größe | 16 MB | Gute Balance Performance/Memory |
| Testmuster | 5 (fix) | Analog zu badblocks |
| Muster-Reihenfolge | 00,FF,AA,55,RND | Standard |
