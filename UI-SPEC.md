# DiskTest - UI-Spezifikation

## Fenster-Eigenschaften

| Eigenschaft | Wert |
|-------------|------|
| Titel | DiskTest |
| Mindestgröße | 800 × 600 px |
| Startgröße | 900 × 700 px |
| Größe änderbar | Ja |
| Icon | Festplatten-Symbol |

---

## Layout-Übersicht

```
┌─────────────────────────────────────────────────────────────────────┐
│ DiskTest                                                       [─][□][×] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ Konfiguration ───────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │  Zielpfad:    [D:\                                ] [Browse]  │  │
│  │                                                               │  │
│  │  Testgröße:   [================|----] 50 GB   ☑ Ganzes Lfw.  │  │
│  │                                                               │  │
│  │  Dateigröße:  [1    ] GB        Freier Speicher: 120 GB       │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Steuerung ───────────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │  [ ▶ Start ]  [ ⏸ Pause ]  [ ⏹ Stop ]    [🗑 Dateien löschen] │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Fortschritt ─────────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │  Gesamt:      [████████████░░░░░░░░░░░░░░░░░░]  42%           │  │
│  │               Geschätzte Restzeit: 2h 15m                     │  │
│  │                                                               │  │
│  │  ─────────────────────────────────────────────────────────    │  │
│  │                                                               │  │
│  │  Muster:      2/5 (0xFF)                                      │  │
│  │  Phase:       Verifizieren                                    │  │
│  │  Datei:       23/50 (disktest_023.dat)                        │  │
│  │  Geschw.:     185.3 MB/s                                      │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  Fehler: 0                                              │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Log ─────────────────────────────────────────────────────────┐  │
│  │ [14:30:22] INFO    Test gestartet - Ziel: D:\                 │  │
│  │ [14:30:22] INFO    Konfiguration: 50 Dateien à 1 GB           │  │
│  │ [14:35:44] SUCCESS disktest_001.dat - 0x00 - Schreiben OK     │  │
│  │ [14:40:12] SUCCESS disktest_001.dat - 0x00 - Verifizierung OK │  │
│  │ [14:45:33] SUCCESS disktest_002.dat - 0x00 - Schreiben OK     │  │
│  │ [14:50:55] SUCCESS disktest_002.dat - 0x00 - Verifizierung OK │  │
│  │ ...                                                       ▼   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Statusleiste: Bereit | Session: disktest_session.json             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Bereich: Konfiguration

### Zielpfad
- **Widget:** QLineEdit + QPushButton ("Browse")
- **Verhalten:**
  - Direkteingabe möglich
  - Browse öffnet QFileDialog (Ordnerauswahl)
  - Validierung: Pfad muss existieren und beschreibbar sein
- **Deaktiviert wenn:** Test läuft

### Testgröße
- **Widget:** QSlider + QSpinBox + QCheckBox
- **Slider:** 1 GB bis freier Speicher
- **SpinBox:** Direkte Eingabe in GB
- **Checkbox:** "Ganzes Laufwerk" (setzt Slider auf Maximum)
- **Verhalten:**
  - Slider und SpinBox sind synchronisiert
  - Checkbox überschreibt manuelle Eingabe
- **Deaktiviert wenn:** Test läuft

### Dateigröße
- **Widget:** QSpinBox
- **Bereich:** 100 MB - 10 GB (Schrittweite: 100 MB)
- **Default:** 1 GB
- **Deaktiviert wenn:** Test läuft

### Freier Speicher
- **Widget:** QLabel
- **Verhalten:** Aktualisiert sich bei Pfadänderung
- **Format:** "Freier Speicher: XXX GB"

---

## Bereich: Steuerung

### Start-Button
- **Widget:** QPushButton
- **Icon:** ▶ (Play)
- **Text:** "Start"
- **Verhalten:**
  - Startet den Test
  - Wird zu "Fortsetzen" wenn pausiert
- **Deaktiviert wenn:** Test läuft, kein Pfad, ungültige Konfiguration

### Pause-Button
- **Widget:** QPushButton
- **Icon:** ⏸ (Pause)
- **Text:** "Pause"
- **Verhalten:**
  - Pausiert den laufenden Test
  - Wird zu "Fortsetzen" nach Pause
- **Deaktiviert wenn:** Test nicht läuft

### Stop-Button
- **Widget:** QPushButton
- **Icon:** ⏹ (Stop)
- **Text:** "Stop"
- **Verhalten:**
  - Bricht Test ab (nach Bestätigung)
  - Session wird gelöscht
- **Deaktiviert wenn:** Test nicht läuft

### Dateien löschen Button
- **Widget:** QPushButton
- **Icon:** 🗑 (Mülleimer)
- **Text:** "Dateien löschen"
- **Verhalten:**
  - Bestätigungs-Dialog
  - Löscht alle disktest_*.dat Dateien im Zielpfad
- **Deaktiviert wenn:** Test läuft, keine Testdateien vorhanden

---

## Bereich: Fortschritt

### Gesamtfortschritt
- **Widget:** QProgressBar + QLabel
- **Fortschrittsbalken:** 0-100%
- **Label darunter:** "Geschätzte Restzeit: Xh Xm"

### Detail-Anzeigen
| Feld | Widget | Format |
|------|--------|--------|
| Muster | QLabel | "2/5 (0xFF)" |
| Phase | QLabel | "Schreiben" oder "Verifizieren" |
| Datei | QLabel | "23/50 (disktest_023.dat)" |
| Geschwindigkeit | QLabel | "185.3 MB/s" |

### Fehler-Counter
- **Widget:** Custom Widget (auffällig gestaltet)
- **Normal:** Grüner Hintergrund, "Fehler: 0"
- **Bei Fehlern:** Roter Hintergrund, "Fehler: X"
- **Klickbar:** Öffnet Detail-Dialog mit Fehlerliste

---

## Bereich: Log

### Log-Ausgabe
- **Widget:** QTextEdit (readonly) oder QPlainTextEdit
- **Verhalten:**
  - Auto-Scroll zu neuesten Einträgen
  - Farbcodierung nach Log-Level
  - Scrollbar für manuelle Navigation

### Farbcodierung
| Level | Farbe |
|-------|-------|
| INFO | Schwarz/Standard |
| SUCCESS | Grün (#28a745) |
| WARNING | Orange (#fd7e14) |
| ERROR | Rot (#dc3545) |

### Format
```
[HH:MM:SS] LEVEL   Message
```

---

## Statusleiste

- **Widget:** QStatusBar
- **Inhalt:**
  - Linker Bereich: Aktueller Status ("Bereit", "Test läuft...", "Pausiert", etc.)
  - Rechter Bereich: Session-Datei Info (falls vorhanden)

---

## Dialoge

### Session-Wiederherstellung Dialog
```
┌─ Vorherige Session gefunden ─────────────────────────┐
│                                                      │
│  ℹ Eine vorherige Test-Session wurde gefunden.       │
│                                                      │
│  Zielpfad:    D:\                                    │
│  Fortschritt: 42%                                    │
│  Muster:      2/5 (0xFF)                             │
│  Fehler:      0                                      │
│                                                      │
│  Möchten Sie den Test fortsetzen?                    │
│                                                      │
│  [Fortsetzen]  [Neuer Test]  [Abbrechen]             │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Dateien löschen Dialog
```
┌─ Testdateien löschen ────────────────────────────────┐
│                                                      │
│  ⚠ Möchten Sie alle Testdateien löschen?            │
│                                                      │
│  Pfad:   D:\                                         │
│  Anzahl: 50 Dateien                                  │
│  Größe:  50 GB                                       │
│                                                      │
│  [Löschen]  [Abbrechen]                              │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Stop-Bestätigung Dialog
```
┌─ Test abbrechen ─────────────────────────────────────┐
│                                                      │
│  ⚠ Möchten Sie den Test wirklich abbrechen?         │
│                                                      │
│  Der aktuelle Fortschritt geht verloren.             │
│  Die erstellten Testdateien bleiben erhalten.        │
│                                                      │
│  [Abbrechen]  [Test beenden]                         │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Fehler-Detail Dialog
```
┌─ Fehler-Details ─────────────────────────────────────┐
│                                                      │
│  Fehler während des Tests: 2                         │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │ 1. disktest_023.dat                            │  │
│  │    Muster: 0xFF                                │  │
│  │    Phase: Verifizierung                        │  │
│  │    Details: Daten stimmen nicht überein        │  │
│  │                                                │  │
│  │ 2. disktest_041.dat                            │  │
│  │    Muster: 0xAA                                │  │
│  │    Phase: Schreiben                            │  │
│  │    Details: Schreibfehler - Zugriff verweigert │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  [Schließen]                                         │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Zustände der UI

### Zustand: Bereit (Idle)
| Element | Status |
|---------|--------|
| Konfiguration | Aktiviert |
| Start | Aktiviert |
| Pause | Deaktiviert |
| Stop | Deaktiviert |
| Dateien löschen | Aktiviert (wenn Dateien existieren) |

### Zustand: Test läuft
| Element | Status |
|---------|--------|
| Konfiguration | Deaktiviert |
| Start | Deaktiviert |
| Pause | Aktiviert |
| Stop | Aktiviert |
| Dateien löschen | Deaktiviert |

### Zustand: Pausiert
| Element | Status |
|---------|--------|
| Konfiguration | Deaktiviert |
| Start (→ "Fortsetzen") | Aktiviert |
| Pause | Deaktiviert |
| Stop | Aktiviert |
| Dateien löschen | Deaktiviert |

### Zustand: Abgeschlossen
| Element | Status |
|---------|--------|
| Konfiguration | Aktiviert |
| Start | Aktiviert |
| Pause | Deaktiviert |
| Stop | Deaktiviert |
| Dateien löschen | Aktiviert |

---

## Responsive Verhalten

- **Log-Bereich:** Nimmt verfügbaren vertikalen Platz ein
- **Fortschrittsbalken:** Dehnt sich horizontal
- **Minimum-Größe:** Unter 800×600 nicht verkleinerbar
- **Layout:** QVBoxLayout mit QGroupBoxen

---

## Tastenkürzel

| Kürzel | Aktion |
|--------|--------|
| Ctrl+S | Start/Fortsetzen |
| Ctrl+P | Pause |
| Escape | Stop (mit Bestätigung) |
| Ctrl+L | Log leeren |
| Ctrl+O | Pfad auswählen (Browse) |
