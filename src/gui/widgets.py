"""Custom Widgets für DiskTest GUI."""

from PySide6.QtWidgets import (
    QWidget, QLabel, QProgressBar, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFrame, QCheckBox, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QColor

from core.patterns import PatternType, PATTERN_SEQUENCE


class ErrorCounterWidget(QWidget):
    """
    Custom Widget für Fehler-Counter mit farblicher Hervorhebung.

    - Bei 0 Fehlern: Grüner Hintergrund
    - Bei Fehlern: Roter Hintergrund
    - Klickbar: Öffnet Detail-Dialog
    """

    clicked = Signal()  # Signal wenn Widget angeklickt wird

    def __init__(self, parent=None):
        super().__init__(parent)
        self._error_count = 0
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        """UI-Elemente erstellen."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.label = QLabel("Fehler: 0")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Font größer und fett
        font = self.label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.label.setFont(font)

        layout.addWidget(self.label)

        # Rahmen
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)

        # Cursor ändern wenn Fehler vorhanden
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Mindestgröße
        self.setMinimumHeight(40)

    def setFrameStyle(self, style):
        """Setzt den Frame-Style (für QFrame-Kompatibilität)."""
        self.setProperty("frameStyle", style)

    def setLineWidth(self, width):
        """Setzt die Linienbreite des Rahmens."""
        self.setProperty("lineWidth", width)

    def set_error_count(self, count: int):
        """Setzt die Anzahl der Fehler und aktualisiert die Anzeige."""
        self._error_count = count
        self.label.setText(f"Fehler: {count}")
        self._update_style()

        # Cursor ändern
        if count > 0:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def get_error_count(self) -> int:
        """Gibt die aktuelle Fehleranzahl zurück."""
        return self._error_count

    def _update_style(self):
        """Aktualisiert Hintergrundfarbe basierend auf Fehlerzahl."""
        if self._error_count == 0:
            # Grüner Hintergrund
            color = "#28a745"
            text_color = "white"
        else:
            # Roter Hintergrund
            color = "#dc3545"
            text_color = "white"

        self.setStyleSheet(f"""
            ErrorCounterWidget {{
                background-color: {color};
                border: 2px solid {color};
                border-radius: 5px;
            }}
            QLabel {{
                color: {text_color};
            }}
        """)

    def mousePressEvent(self, event):
        """Behandelt Mausklicks - emittiert clicked Signal wenn Fehler vorhanden."""
        if self._error_count > 0:
            self.clicked.emit()
        super().mousePressEvent(event)


class ProgressWidget(QGroupBox):
    """
    Widget für Fortschrittsanzeige mit Details.

    Zeigt:
    - Gesamtfortschrittsbalken mit Prozent
    - Geschätzte Restzeit
    - Aktuelles Muster, Phase, Datei
    - Geschwindigkeit
    - Fehler-Counter
    """

    def __init__(self, parent=None):
        super().__init__("Fortschritt", parent)
        self._setup_ui()

    def _setup_ui(self):
        """UI-Elemente erstellen."""
        layout = QVBoxLayout(self)

        # Gesamtfortschritt
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Gesamt:"))

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar, 1)

        layout.addLayout(progress_layout)

        # Datei-Fortschritt
        file_progress_layout = QHBoxLayout()
        file_progress_layout.addWidget(QLabel("Datei:"))

        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setMinimum(0)
        self.file_progress_bar.setMaximum(100)
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setTextVisible(True)
        self.file_progress_bar.setFormat("%p%")
        file_progress_layout.addWidget(self.file_progress_bar, 1)

        layout.addLayout(file_progress_layout)

        # Geschätzte Restzeit
        self.time_label = QLabel("Geschätzte Restzeit: --")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.time_label)

        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Detail-Informationen horizontal in zwei Zeilen
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setSpacing(8)

        # Erste Zeile: Muster und Phase
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(20)

        self.pattern_label = self._create_detail_item("Muster:", "--")
        row1_layout.addLayout(self.pattern_label)

        self.phase_label = self._create_detail_item("Phase:", "--")
        row1_layout.addLayout(self.phase_label)

        row1_layout.addStretch()
        details_layout.addLayout(row1_layout)

        # Zweite Zeile: Datei und Geschwindigkeit
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(20)

        self.file_label = self._create_detail_item("Datei:", "--")
        row2_layout.addLayout(self.file_label)

        self.speed_label = self._create_detail_item("Geschw.:", "--")
        row2_layout.addLayout(self.speed_label)

        row2_layout.addStretch()
        details_layout.addLayout(row2_layout)

        layout.addWidget(details_widget)

        # Fehler-Counter
        self.error_counter = ErrorCounterWidget()
        layout.addWidget(self.error_counter)

    def _create_detail_item(self, label_text: str, initial_value: str) -> QHBoxLayout:
        """Hilfsfunktion zum Erstellen eines Detail-Items."""
        item_layout = QHBoxLayout()

        label = QLabel(label_text)
        label.setMinimumWidth(80)
        item_layout.addWidget(label)

        value_label = QLabel(initial_value)
        item_layout.addWidget(value_label)

        # Speichere das Value-Label für späteren Zugriff
        if label_text == "Muster:":
            self.pattern_value = value_label
        elif label_text == "Phase:":
            self.phase_value = value_label
        elif label_text == "Datei:":
            self.file_value = value_label
        elif label_text == "Geschw.:":
            self.speed_value = value_label

        return item_layout

    def set_progress(self, percent: int):
        """Setzt den Gesamtfortschritt (0-100)."""
        self.progress_bar.setValue(percent)

    def set_file_progress(self, percent: int):
        """Setzt den Fortschritt der aktuellen Datei (0-100)."""
        self.file_progress_bar.setValue(percent)

    def set_time_remaining(self, time_str: str):
        """Setzt die geschätzte Restzeit."""
        self.time_label.setText(f"Geschätzte Restzeit: {time_str}")

    def set_pattern(self, pattern_str: str):
        """Setzt die Muster-Anzeige (z.B. '2/5 (0xFF)')."""
        self.pattern_value.setText(pattern_str)

    def set_phase(self, phase_str: str):
        """Setzt die Phase ('Schreiben' oder 'Verifizieren')."""
        self.phase_value.setText(phase_str)

    def set_file(self, file_str: str):
        """Setzt die Datei-Anzeige (z.B. '23/50 (disktest_023.dat)')."""
        self.file_value.setText(file_str)

    def set_speed(self, speed_str: str):
        """Setzt die Geschwindigkeit (z.B. '185.3 MB/s')."""
        self.speed_value.setText(speed_str)

    def set_error_count(self, count: int):
        """Setzt die Fehleranzahl."""
        self.error_counter.set_error_count(count)

    def reset(self):
        """Setzt alle Anzeigen zurück."""
        self.progress_bar.setValue(0)
        self.file_progress_bar.setValue(0)
        self.time_label.setText("Geschätzte Restzeit: --")
        self.pattern_value.setText("--")
        self.phase_value.setText("--")
        self.file_value.setText("--")
        self.speed_value.setText("--")
        self.error_counter.set_error_count(0)


class LogWidget(QGroupBox):
    """
    Widget für Log-Ausgabe mit Farbcodierung.

    Zeigt Log-Einträge mit:
    - Timestamp
    - Level (INFO, SUCCESS, WARNING, ERROR)
    - Nachricht
    - Farbcodierung nach Level
    - Auto-Scroll
    """

    # Farben für Log-Levels
    COLORS = {
        'INFO': '#000000',      # Schwarz
        'SUCCESS': '#28a745',   # Grün
        'WARNING': '#fd7e14',   # Orange
        'ERROR': '#dc3545',     # Rot
    }

    def __init__(self, parent=None):
        super().__init__("Log", parent)
        self._setup_ui()

    def _setup_ui(self):
        """UI-Elemente erstellen."""
        layout = QVBoxLayout(self)

        # Importiere hier um zirkuläre Imports zu vermeiden
        from PySide6.QtWidgets import QPlainTextEdit

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(1000)  # Limitiere auf 1000 Zeilen

        # Monospace Font für bessere Lesbarkeit
        font = self.log_text.font()
        font.setFamily("Consolas")
        font.setPointSize(9)
        self.log_text.setFont(font)

        layout.addWidget(self.log_text)

    def add_log(self, timestamp: str, level: str, message: str):
        """
        Fügt einen Log-Eintrag hinzu.

        Args:
            timestamp: Zeit im Format 'HH:MM:SS'
            level: Log-Level (INFO, SUCCESS, WARNING, ERROR)
            message: Log-Nachricht
        """
        color = self.COLORS.get(level, '#000000')

        # HTML für farbigen Text
        html = f'<span style="color: {color};">[{timestamp}] {level:8} {message}</span>'

        self.log_text.appendHtml(html)

        # Auto-Scroll zum Ende
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def clear(self):
        """Löscht alle Log-Einträge."""
        self.log_text.clear()


class PatternSelectionWidget(QGroupBox):
    """
    Widget für Auswahl der Testmuster.

    Zeigt Checkboxen für alle 5 Patterns:
    - 0x00 (Null)
    - 0xFF (Eins)
    - 0xAA (Alternierende Bits 1)
    - 0x55 (Alternierende Bits 2)
    - Random (Zufallsdaten)

    Signals:
        selection_changed: Emittiert wenn Auswahl geändert wird
    """

    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__("Testmuster", parent)
        self.checkboxes = {}
        self.completed_patterns = []  # Liste der abgeschlossenen Pattern-Values
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """UI-Elemente erstellen."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Checkboxen horizontal nebeneinander
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(15)

        # Checkbox für jedes Pattern
        for pattern_type in PATTERN_SEQUENCE:
            checkbox = QCheckBox(pattern_type.display_name)
            # Random default abgewählt, alle anderen ausgewählt
            checkbox.setChecked(pattern_type != PatternType.RANDOM)
            self.checkboxes[pattern_type] = checkbox
            checkbox_layout.addWidget(checkbox)

        checkbox_layout.addStretch()
        layout.addLayout(checkbox_layout)

        # Buttons für Alle auswählen/abwählen - rechts positioniert
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.select_all_button = QPushButton("Alle auswählen")
        self.select_all_button.setMaximumWidth(120)
        button_layout.addWidget(self.select_all_button)

        self.deselect_all_button = QPushButton("Alle abwählen")
        self.deselect_all_button.setMaximumWidth(120)
        button_layout.addWidget(self.deselect_all_button)

        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Verbindet interne Signals."""
        # Checkbox-Änderungen
        for checkbox in self.checkboxes.values():
            checkbox.stateChanged.connect(self._on_checkbox_changed)

        # Buttons
        self.select_all_button.clicked.connect(self._select_all)
        self.deselect_all_button.clicked.connect(self._deselect_all)

    def _on_checkbox_changed(self):
        """Wird aufgerufen wenn eine Checkbox geändert wird."""
        # Validierung: Mindestens 1 Pattern muss ausgewählt sein
        selected_count = sum(1 for cb in self.checkboxes.values() if cb.isChecked())

        if selected_count == 0:
            # Letzte Checkbox wieder aktivieren
            sender = self.sender()
            if isinstance(sender, QCheckBox):
                sender.setChecked(True)
                return

        # Styles nach Änderung aktualisieren (completed_patterns bleiben erhalten)
        self._update_checkbox_styles()
        self.selection_changed.emit()

    def _select_all(self):
        """Wählt alle Patterns aus."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all(self):
        """Wählt alle Patterns ab (außer dem letzten)."""
        # Alle außer dem ersten abwählen, damit mindestens 1 ausgewählt bleibt
        checkboxes_list = list(self.checkboxes.values())
        for i, checkbox in enumerate(checkboxes_list):
            checkbox.setChecked(i == 0)

    def get_selected_patterns(self):
        """
        Gibt die ausgewählten Patterns zurück.

        Returns:
            list[PatternType]: Liste der ausgewählten Patterns in fixer Reihenfolge
        """
        selected = []
        for pattern_type in PATTERN_SEQUENCE:
            if self.checkboxes[pattern_type].isChecked():
                selected.append(pattern_type)
        return selected

    def set_selected_patterns(self, patterns):
        """
        Setzt die ausgewählten Patterns.

        Args:
            patterns: list[PatternType] oder None (None = alle auswählen)
        """
        if patterns is None:
            patterns = PATTERN_SEQUENCE

        for pattern_type, checkbox in self.checkboxes.items():
            checkbox.setChecked(pattern_type in patterns)

        # Styles aktualisieren nach Änderung der Auswahl
        self._update_checkbox_styles()

    def set_completed_patterns(self, completed_pattern_values):
        """
        Setzt die Liste der abgeschlossenen Patterns und aktualisiert die UI.

        Args:
            completed_pattern_values: list[str] - Pattern-Values (z.B. ["00", "FF"])
        """
        self.completed_patterns = completed_pattern_values if completed_pattern_values else []
        self._update_checkbox_styles()

    def _update_checkbox_styles(self):
        """Aktualisiert die visuellen Styles der Checkboxen basierend auf completed_patterns"""
        for pattern_type, checkbox in self.checkboxes.items():
            if pattern_type.value in self.completed_patterns:
                # Pattern abgeschlossen - grüner Text und Tooltip
                checkbox.setStyleSheet("QCheckBox { color: green; font-weight: bold; }")
                checkbox.setToolTip(f"✓ Bereits getestet - Entfernen verwirft Fortschritt")
            else:
                # Pattern nicht abgeschlossen - normaler Style
                checkbox.setStyleSheet("")
                checkbox.setToolTip(f"{pattern_type.display_name} - Ausstehend")
