"""
Stylesheet-System für DiskTest GUI

Unterstützt automatische Erkennung von Windows Dark Mode
und passt die Farben entsprechend an.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor


def is_dark_mode() -> bool:
    """
    Erkennt ob Windows im Dark Mode läuft.

    Returns:
        True wenn Dark Mode aktiv ist
    """
    # Prüfe Windows-Palette
    palette = QApplication.palette()
    window_color = palette.color(QPalette.ColorRole.Window)

    # Dark Mode wenn Hintergrund dunkel ist (Helligkeit < 128)
    return window_color.lightness() < 128


class AppStyles:
    """
    Zentrale Stylesheet-Verwaltung für die Anwendung.

    Stellt Stylesheets für Light/Dark Mode bereit.
    """

    @staticmethod
    def get_main_stylesheet() -> str:
        """
        Gibt das Haupt-Stylesheet für die Anwendung zurück.

        Passt sich automatisch an Light/Dark Mode an.

        Returns:
            CSS-String für QApplication.setStyleSheet()
        """
        if is_dark_mode():
            return AppStyles._get_dark_stylesheet()
        else:
            return AppStyles._get_light_stylesheet()

    @staticmethod
    def _get_dark_stylesheet() -> str:
        """Stylesheet für Dark Mode"""
        return """
        /* Haupt-Fenster */
        QMainWindow {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }

        /* GroupBox */
        QGroupBox {
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 5px;
            margin-top: 12px;
            padding-top: 10px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #e0e0e0;
        }

        /* Labels */
        QLabel {
            color: #e0e0e0;
        }

        /* LineEdit / TextEdit */
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #3c3f41;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 5px;
            selection-background-color: #0d47a1;
        }

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid #0d47a1;
        }

        QLineEdit:disabled, QTextEdit:disabled {
            background-color: #2b2b2b;
            color: #808080;
        }

        /* Buttons */
        QPushButton {
            background-color: #3c3f41;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 5px 15px;
            min-height: 20px;
        }

        QPushButton:hover {
            background-color: #4c5052;
            border: 1px solid #0d47a1;
        }

        QPushButton:pressed {
            background-color: #2b2b2b;
        }

        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #606060;
            border: 1px solid #3c3f41;
        }

        QPushButton:default {
            border: 2px solid #0d47a1;
        }

        /* SpinBox / DoubleSpinBox */
        QSpinBox, QDoubleSpinBox {
            background-color: #3c3f41;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 3px;
        }

        QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color: #2b2b2b;
            color: #808080;
        }

        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            background-color: #3c3f41;
            border: 1px solid #555555;
        }

        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
            background-color: #4c5052;
        }

        /* Slider */
        QSlider::groove:horizontal {
            border: 1px solid #555555;
            height: 8px;
            background: #3c3f41;
            margin: 2px 0;
            border-radius: 4px;
        }

        QSlider::handle:horizontal {
            background: #0d47a1;
            border: 1px solid #0d47a1;
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }

        QSlider::handle:horizontal:hover {
            background: #1565c0;
        }

        QSlider:disabled {
            opacity: 0.5;
        }

        /* ProgressBar */
        QProgressBar {
            border: 1px solid #555555;
            border-radius: 5px;
            text-align: center;
            background-color: #3c3f41;
            color: #e0e0e0;
        }

        QProgressBar::chunk {
            background-color: #0d47a1;
            border-radius: 4px;
        }

        /* CheckBox */
        QCheckBox {
            color: #e0e0e0;
            spacing: 5px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #555555;
            border-radius: 3px;
            background-color: #3c3f41;
        }

        QCheckBox::indicator:hover {
            border: 1px solid #0d47a1;
        }

        QCheckBox::indicator:checked {
            background-color: #0d47a1;
            border: 1px solid #0d47a1;
            image: url(none);
        }

        QCheckBox::indicator:disabled {
            background-color: #2b2b2b;
            border: 1px solid #3c3f41;
        }

        /* ComboBox */
        QComboBox {
            background-color: #3c3f41;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 5px;
        }

        QComboBox:hover {
            border: 1px solid #0d47a1;
        }

        QComboBox::drop-down {
            border: none;
            width: 20px;
        }

        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #b0b0b0;
            margin-right: 5px;
        }

        QComboBox QAbstractItemView {
            background-color: #3c3f41;
            color: #e0e0e0;
            border: 1px solid #555555;
            selection-background-color: #0d47a1;
            selection-color: #ffffff;
        }

        /* StatusBar */
        QStatusBar {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border-top: 1px solid #555555;
        }

        /* MenuBar */
        QMenuBar {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border-bottom: 1px solid #555555;
        }

        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }

        QMenuBar::item:selected {
            background-color: #3c3f41;
        }

        QMenu {
            background-color: #3c3f41;
            color: #e0e0e0;
            border: 1px solid #555555;
        }

        QMenu::item {
            padding: 5px 25px 5px 20px;
        }

        QMenu::item:selected {
            background-color: #0d47a1;
        }

        /* ScrollBar */
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 12px;
            margin: 0px;
        }

        QScrollBar::handle:vertical {
            background-color: #555555;
            min-height: 20px;
            border-radius: 6px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #666666;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        QScrollBar:horizontal {
            background-color: #2b2b2b;
            height: 12px;
            margin: 0px;
        }

        QScrollBar::handle:horizontal {
            background-color: #555555;
            min-width: 20px;
            border-radius: 6px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #666666;
        }

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        /* TabWidget */
        QTabWidget::pane {
            border: 1px solid #555555;
            background-color: #2b2b2b;
        }

        QTabBar::tab {
            background-color: #3c3f41;
            color: #e0e0e0;
            border: 1px solid #555555;
            padding: 5px 10px;
        }

        QTabBar::tab:selected {
            background-color: #0d47a1;
            border-bottom: none;
        }

        QTabBar::tab:hover {
            background-color: #4c5052;
        }

        /* Dialog */
        QDialog {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }

        /* Custom Widget-spezifische Styles */
        .error-widget {
            background-color: #3c1f1f;
            border-left: 4px solid #d32f2f;
        }

        .success-widget {
            background-color: #1f3c1f;
            border-left: 4px solid #388e3c;
        }

        .warning-widget {
            background-color: #3c3c1f;
            border-left: 4px solid #f57c00;
        }

        .info-widget {
            background-color: #1f2f3c;
            border-left: 4px solid #0288d1;
        }
        """

    @staticmethod
    def _get_light_stylesheet() -> str:
        """Stylesheet für Light Mode"""
        return """
        /* Haupt-Fenster */
        QMainWindow {
            background-color: #f5f5f5;
            color: #000000;
        }

        /* GroupBox */
        QGroupBox {
            color: #000000;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 12px;
            padding-top: 10px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #000000;
        }

        /* Labels */
        QLabel {
            color: #000000;
        }

        /* LineEdit / TextEdit */
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
            selection-background-color: #0078d4;
        }

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid #0078d4;
        }

        QLineEdit:disabled, QTextEdit:disabled {
            background-color: #f0f0f0;
            color: #808080;
        }

        /* Buttons */
        QPushButton {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px 15px;
            min-height: 20px;
        }

        QPushButton:hover {
            background-color: #e8e8e8;
            border: 1px solid #0078d4;
        }

        QPushButton:pressed {
            background-color: #d0d0d0;
        }

        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #a0a0a0;
            border: 1px solid #e0e0e0;
        }

        QPushButton:default {
            border: 2px solid #0078d4;
        }

        /* SpinBox / DoubleSpinBox */
        QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 3px;
        }

        QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color: #f0f0f0;
            color: #808080;
        }

        /* Slider */
        QSlider::groove:horizontal {
            border: 1px solid #cccccc;
            height: 8px;
            background: #ffffff;
            margin: 2px 0;
            border-radius: 4px;
        }

        QSlider::handle:horizontal {
            background: #0078d4;
            border: 1px solid #0078d4;
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }

        QSlider::handle:horizontal:hover {
            background: #1084d8;
        }

        /* ProgressBar */
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 5px;
            text-align: center;
            background-color: #ffffff;
            color: #000000;
        }

        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 4px;
        }

        /* CheckBox */
        QCheckBox {
            color: #000000;
            spacing: 5px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #cccccc;
            border-radius: 3px;
            background-color: #ffffff;
        }

        QCheckBox::indicator:hover {
            border: 1px solid #0078d4;
        }

        QCheckBox::indicator:checked {
            background-color: #0078d4;
            border: 1px solid #0078d4;
        }

        /* ComboBox */
        QComboBox {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 5px;
        }

        QComboBox:hover {
            border: 1px solid #0078d4;
        }

        QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
            selection-background-color: #0078d4;
            selection-color: #ffffff;
        }

        /* StatusBar */
        QStatusBar {
            background-color: #f5f5f5;
            color: #000000;
            border-top: 1px solid #cccccc;
        }

        /* MenuBar */
        QMenuBar {
            background-color: #f5f5f5;
            color: #000000;
            border-bottom: 1px solid #cccccc;
        }

        QMenuBar::item:selected {
            background-color: #e8e8e8;
        }

        QMenu {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
        }

        QMenu::item:selected {
            background-color: #0078d4;
            color: #ffffff;
        }

        /* ScrollBar */
        QScrollBar:vertical {
            background-color: #f5f5f5;
            width: 12px;
        }

        QScrollBar::handle:vertical {
            background-color: #cccccc;
            min-height: 20px;
            border-radius: 6px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #b0b0b0;
        }

        QScrollBar:horizontal {
            background-color: #f5f5f5;
            height: 12px;
        }

        QScrollBar::handle:horizontal {
            background-color: #cccccc;
            min-width: 20px;
            border-radius: 6px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #b0b0b0;
        }

        /* Dialog */
        QDialog {
            background-color: #f5f5f5;
            color: #000000;
        }

        /* Custom Widget-spezifische Styles */
        .error-widget {
            background-color: #ffebee;
            border-left: 4px solid #dc3545;
        }

        .success-widget {
            background-color: #e8f5e9;
            border-left: 4px solid #28a745;
        }

        .warning-widget {
            background-color: #fff3e0;
            border-left: 4px solid #ffc107;
        }

        .info-widget {
            background-color: #e3f2fd;
            border-left: 4px solid #0078d4;
        }
        """

    @staticmethod
    def get_dialog_detail_style(is_dark: bool = None) -> str:
        """
        Gibt Stylesheet für Detail-Widgets in Dialogen zurück.

        Args:
            is_dark: Optional, ob Dark Mode verwendet werden soll.
                     Wenn None, wird automatisch erkannt.

        Returns:
            CSS-String für Detail-Widget-Hintergrund
        """
        if is_dark is None:
            is_dark = is_dark_mode()

        if is_dark:
            return """
                background-color: #3c3f41;
                border-radius: 5px;
                padding: 15px;
            """
        else:
            return """
                background-color: #f0f0f0;
                border-radius: 5px;
                padding: 15px;
            """

    @staticmethod
    def get_error_style(is_dark: bool = None) -> str:
        """Gibt Stylesheet für Fehler-Widgets zurück."""
        if is_dark is None:
            is_dark = is_dark_mode()

        if is_dark:
            return """
                background-color: #3c1f1f;
                border-left: 4px solid #d32f2f;
                border-radius: 3px;
                padding: 10px;
            """
        else:
            return """
                background-color: #ffebee;
                border-left: 4px solid #dc3545;
                border-radius: 3px;
                padding: 10px;
            """
