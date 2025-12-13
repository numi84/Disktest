---
name: Pattern-Auswahl bei laufenden Sessions änderbar machen
about: Feature-Verbesserung für dynamische Testmuster-Anpassung während Pause/Resume
title: 'Pattern-Auswahl bei laufenden Sessions änderbar machen'
labels: enhancement, session-management
assignees: ''
---

## Problem / Feature Request

Die Auswahl der Testmuster (0x00, 0xFF, 0xAA, 0x55, RANDOM) soll auch bei pausierten Sessions jederzeit änderbar sein. Nutzer sollen Muster hinzufügen oder entfernen können, ohne den Test von vorne starten zu müssen.

## Aktueller Stand

**Was bereits funktioniert:**
- ✅ Pattern Widget ist bei Resume NICHT deaktiviert (im Gegensatz zu Zielpfad/Dateigröße)
- ✅ `test_controller.py:936-962` erlaubt Pattern-Änderungen beim Resume
- ✅ Engine unterstützt dynamische Pattern-Auswahl über `config.selected_patterns`
- ✅ Änderungen werden geloggt: "Testmuster angepasst: X Muster ausgewählt"

**Kritische Probleme:**

### 1. Progress-Berechnung fehlerhaft
**Datei:** `src/core/session.py` (Zeilen 71-95)
- `total_phases = 10` ist hardcoded (5 Patterns × 2 Phasen)
- Bei 3 ausgewählten Patterns sollte es 6 sein
- Führt zu falschen Prozentangaben in der UI

### 2. Pattern-Index-Mapping bricht
**Beispiel-Szenario:**
- Session läuft bei Pattern-Index 2 (0xAA)
- User entfernt Pattern 1 (0xFF) beim Resume
- `current_pattern_index = 2` zeigt jetzt auf falsches Pattern
- Kann zu übersprungenen oder doppelt getesteten Patterns führen

### 3. Keine Validierung bei Pattern-Änderungen
- ❌ User kann Patterns entfernen, die bereits getestet wurden (Datenverlust)
- ❌ Keine Warnung bei Hinzufügen neuer Patterns (Test unvollständig)
- ❌ Keine Rückfrage ob vorhandener Progress verworfen werden soll

### 4. UI gibt keine Hinweise
- ❌ Pattern Widget sieht gleich aus wie bei neuem Test
- ❌ User weiß nicht, dass Änderungen möglich/erlaubt sind
- ❌ Keine visuelle Kennzeichnung welche Patterns bereits getestet wurden

## Gewünschtes Verhalten

### Funktionale Anforderungen

1. **Pattern hinzufügen/entfernen immer möglich**
   - Bei pausiertem Test: Änderungen sofort möglich
   - Bei laufendem Test: Pattern-Widget deaktiviert (nur bei Pause änderbar)

2. **Intelligente Validierung**
   - ⚠️ Warnung wenn bereits getestete Patterns entfernt werden
   - ℹ️ Info wenn neue Patterns hinzugefügt werden
   - Dialog: "Progress für Pattern X wird verworfen. Fortfahren?"

3. **Korrekte Progress-Berechnung**
   - `total_phases` basierend auf `len(selected_patterns) * 2`
   - Pattern-Index-Mapping auf Pattern-Name umstellen (statt numerischer Index)

4. **UI-Verbesserungen**
   - ✓ Visuelle Kennzeichnung getesteter Patterns (z.B. grünes Häkchen-Icon)
   - 📝 Tooltip: "Bereits getestet - Entfernen verwirft Progress"
   - 🔒 Enable/Disable abhängig von Test-Status (Running vs Paused)

### Technische Änderungen

#### Session-Datenstruktur erweitern

```python
# Aktuell (session.py):
current_pattern_index: int = 0  # ❌ Bricht bei Pattern-Änderungen
selected_patterns: List[str] = field(default_factory=list)

# Vorschlag:
current_pattern_name: str = "00"  # ✅ Robust gegen Reihenfolge-Änderungen
selected_patterns: List[str] = field(default_factory=list)
completed_patterns: List[str] = field(default_factory=list)  # ✅ Für UI-Kennzeichnung
```

#### Betroffene Dateien

- **`src/core/session.py`** (Zeilen 71-95)
  - Progress-Berechnung dynamisch machen
  - `current_pattern_name` statt `current_pattern_index`
  - `completed_patterns` Liste hinzufügen

- **`src/gui/widgets.py`** (Zeilen 341-459)
  - Pattern Widget UI erweitern
  - Visuelle Kennzeichnung getesteter Patterns
  - Tooltips für Status-Info

- **`src/core/test_controller.py`** (Zeilen 936-962)
  - Validierung bei Resume
  - Warn-Dialoge für Pattern-Änderungen
  - Enable/Disable Logik für laufende Tests

- **`src/core/test_engine.py`** (Zeilen 227-238)
  - Pattern-Mapping von Index auf Name umstellen
  - Skip-Logik für bereits getestete Patterns

## Beispiel-Szenario

### Szenario 1: Pattern entfernen
```
Initial: [0x00, 0xFF, 0xAA, 0x55, RANDOM]
Progress: 0xFF getestet (write + verify)
User removes: 0xFF

Dialog:
┌─────────────────────────────────────────┐
│ Pattern 0xFF wurde bereits getestet.    │
│ Durch Entfernen wird der Progress für   │
│ dieses Muster verworfen.                │
│                                         │
│ Fortfahren?     [Ja] [Nein]             │
└─────────────────────────────────────────┘

Nach Bestätigung:
- completed_patterns: [] (0xFF entfernt)
- selected_patterns: ["00", "AA", "55", "RANDOM"]
- current_pattern_name: "AA" (nächstes ungetestetes)
```

### Szenario 2: Pattern hinzufügen
```
Initial: [0x00, 0xAA]
Progress: 0x00 getestet
User adds: 0xFF, 0x55

Info:
┌─────────────────────────────────────────┐
│ 2 neue Muster hinzugefügt:              │
│ - 0xFF                                  │
│ - 0x55                                  │
│                                         │
│ Diese werden nach 0xAA getestet.        │
│                             [OK]        │
└─────────────────────────────────────────┘

Nach OK:
- selected_patterns: ["00", "FF", "AA", "55"]
- completed_patterns: ["00"]
- current_pattern_name: "AA"
```

## Akzeptanzkriterien

- [ ] Pattern-Widget ist bei pausiertem Test editierbar
- [ ] Pattern-Widget ist bei laufendem Test deaktiviert
- [ ] Progress-Berechnung berücksichtigt dynamische Pattern-Anzahl
- [ ] Warnung beim Entfernen getesteter Patterns
- [ ] Info-Dialog beim Hinzufügen neuer Patterns
- [ ] Visuelle Kennzeichnung getesteter Patterns (Icon/Farbe)
- [ ] Tooltips zeigen Status (getestet/ausstehend)
- [ ] Session speichert `completed_patterns`
- [ ] Pattern-Mapping verwendet Namen statt Index
- [ ] Keine falschen/übersprungenen Tests bei Pattern-Änderungen

## Priorität

**Medium-High** - Feature ist teilweise implementiert, hat aber kritische Bugs die zu Datenverlust oder falschen Testergebnissen führen können.

## Zusätzliche Hinweise

- Code in `test_controller.py:936-962` ist bereits vorbereitet für Pattern-Updates
- Hauptproblem ist die Session-State-Verwaltung, nicht die UI-Anbindung
- Migration existierender Sessions nötig (`current_pattern_index` → `current_pattern_name`)
