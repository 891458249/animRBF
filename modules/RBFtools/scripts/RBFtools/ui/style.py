# -*- coding: utf-8 -*-
"""
QSS stylesheet — Maya 2024+ flat dark theme integration.

Designed to look native inside Maya's modernised UI while adding
polish that the default widgets lack.  Colour palette is sampled from
Maya 2024's ``styleSheet()`` base colours:

    bg-dark   #2b2b2b     main background
    bg-mid    #383838     panel / header background
    bg-light  #444444     hovered / active elements
    accent    #5285a6     selection / focus
    text      #cccccc     primary text
    text-dim  #888888     disabled / secondary text
    border    #555555     separator / border lines
    driver    #2e3d50     driver column tint (deep blue)
    driven    #2e4a3a     driven column tint (deep green)
"""

from __future__ import absolute_import

# -- Colour tokens (centralised for easy theme tweaking) --
_C = {
    "bg_dark":   "#2b2b2b",
    "bg_mid":    "#383838",
    "bg_light":  "#444444",
    "accent":    "#5285a6",
    "accent_h":  "#6198bb",    # accent hover
    "text":      "#cccccc",
    "text_dim":  "#888888",
    "border":    "#555555",
    "driver":    "#2e3d50",
    "driven":    "#2e4a3a",
    "danger":    "#a65252",
    "danger_h":  "#bb6868",
}

# Expose raw colour values for the delegate (no QSS parsing needed)
COLOR_DRIVER_BG = _C["driver"]
COLOR_DRIVEN_BG = _C["driven"]

STYLESHEET = """
/* ==================================================================
   Global
   ================================================================== */

QMainWindow, QWidget {{
    background-color: {bg_dark};
    color: {text};
    font-size: 12px;
}}

/* ==================================================================
   Scroll area (frameless, seamless)
   ================================================================== */

QScrollArea {{
    border: none;
    background: transparent;
}}

/* ==================================================================
   QScrollBar — thin, flat
   ================================================================== */

QScrollBar:vertical {{
    background: {bg_dark};
    width: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {bg_light};
    min-height: 30px;
    border-radius: 4px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {accent};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {bg_dark};
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {bg_light};
    min-width: 30px;
    border-radius: 4px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {accent};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ==================================================================
   QPushButton
   ================================================================== */

QPushButton {{
    background-color: {bg_light};
    color: {text};
    border: 1px solid {border};
    border-radius: 3px;
    min-height: 24px;
    padding: 2px 10px;
}}
QPushButton:hover {{
    background-color: {accent};
    border-color: {accent_h};
}}
QPushButton:pressed {{
    background-color: {accent_h};
}}
QPushButton:disabled {{
    color: {text_dim};
    background-color: {bg_mid};
}}

/* Delete-style buttons (optional class) */
QPushButton[cssClass="danger"] {{
    background-color: {danger};
}}
QPushButton[cssClass="danger"]:hover {{
    background-color: {danger_h};
}}

/* ==================================================================
   QComboBox
   ================================================================== */

QComboBox {{
    background-color: {bg_mid};
    border: 1px solid {border};
    border-radius: 3px;
    padding: 3px 6px;
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: {accent};
}}
QComboBox QAbstractItemView {{
    background-color: {bg_mid};
    selection-background-color: {accent};
    border: 1px solid {border};
}}

/* ==================================================================
   QCheckBox
   ================================================================== */

QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {border};
    border-radius: 2px;
    background: {bg_mid};
}}
QCheckBox::indicator:checked {{
    background: {accent};
    border-color: {accent};
}}

/* ==================================================================
   QSpinBox / QDoubleSpinBox
   ================================================================== */

QSpinBox, QDoubleSpinBox {{
    background-color: {bg_mid};
    border: 1px solid {border};
    border-radius: 3px;
    padding: 2px 4px;
    min-height: 22px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {accent};
}}

/* ==================================================================
   QLineEdit (read-only fields)
   ================================================================== */

QLineEdit {{
    background-color: {bg_mid};
    border: 1px solid {border};
    border-radius: 3px;
    padding: 3px 6px;
    min-height: 22px;
}}
QLineEdit:read-only {{
    background-color: {bg_dark};
    color: {text_dim};
}}

/* ==================================================================
   QListWidget (attribute lists)
   ================================================================== */

QListWidget {{
    background-color: {bg_dark};
    border: 1px solid {border};
    border-radius: 3px;
    alternate-background-color: {bg_mid};
}}
QListWidget::item:selected {{
    background-color: {accent};
}}

/* ==================================================================
   QTableView (pose table) — base styling only.
   Column-specific colouring handled by PoseDelegate.
   ================================================================== */

QTableView {{
    background-color: {bg_dark};
    alternate-background-color: {bg_mid};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: 3px;
    selection-background-color: {accent};
}}
QTableView QHeaderView::section {{
    background-color: {bg_mid};
    color: {text};
    padding: 4px 6px;
    border: none;
    border-right: 1px solid {border};
    border-bottom: 1px solid {border};
    font-weight: bold;
}}

/* ==================================================================
   QToolButton (collapsible section toggles)
   ================================================================== */

QToolButton {{
    border: none;
    color: {text};
    font-weight: bold;
    padding: 4px 2px;
}}
QToolButton:hover {{
    color: {accent_h};
}}

/* ==================================================================
   QProgressBar (status bar)
   ================================================================== */

QProgressBar {{
    background-color: {bg_mid};
    border: 1px solid {border};
    border-radius: 3px;
    text-align: center;
    color: {text};
    height: 16px;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 2px;
}}

/* ==================================================================
   QSplitter handle
   ================================================================== */

QSplitter::handle {{
    background-color: {border};
}}
QSplitter::handle:vertical {{
    height: 3px;
}}
QSplitter::handle:horizontal {{
    width: 3px;
}}

/* ==================================================================
   Separator / divider lines
   ================================================================== */

QFrame[frameShape="4"] {{
    color: {border};
    max-height: 1px;
}}
QFrame[frameShape="5"] {{
    color: {border};
    max-width: 1px;
}}

/* ==================================================================
   QMenu (gear popup, filter context)
   ================================================================== */

QMenu {{
    background-color: {bg_mid};
    border: 1px solid {border};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 5px 25px 5px 20px;
}}
QMenu::item:selected {{
    background-color: {accent};
}}
QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 4px 8px;
}}
""".format(**_C)
