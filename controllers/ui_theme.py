# ui_theme.py
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import QLocale

PRIMARY = "#4F46E5"   # índigo
PRIMARY_D = "#4338CA"
ACCENT   = "#22C55E"   # verde ok
DANGER   = "#EF4444"
BG       = "#F8FAFC"   # slate-50
CARD     = "#FFFFFF"
BORDER   = "#E5E7EB"
TEXT     = "#0F172A"

QSS = f"""
/* base */
QWidget {{
  font-size: 18px;
  color: {TEXT};
}}
QDialog, QMainWindow, QWidget {{
  background: {BG};
}}
QGroupBox {{
  border: 1px solid {BORDER};
  border-radius: 10px;
  margin-top: 10px;
  padding: 8px;
  background: {CARD};
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  left: 12px; padding: 0 6px; color: {TEXT};
}}
/* inputs */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
  background: {CARD};
  border: 1px solid {BORDER};
  border-radius: 8px;
  padding: 6px 8px;
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
  border: 1px solid {PRIMARY};
}}
/* tabs */
QTabWidget::pane {{
  border: 1px solid {BORDER}; border-radius: 10px; background: {CARD};
}}
QTabBar::tab {{
  padding: 6px 12px; margin: 2px; border: 1px solid {BORDER};
  border-bottom: none; border-top-left-radius: 10px; border-top-right-radius: 10px;
  background: #F1F5F9;
}}
QTabBar::tab:selected {{
  background: {CARD}; border-color: {PRIMARY}; color: {TEXT};
}}
/* tabla */
QTableView {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
  gridline-color: {BORDER};
}}
QHeaderView::section {{
  background: #EEF2FF;  /* leve violeta */
  padding: 6px; border: none; font-weight: 600;
}}
QTableView::item:selected {{
  background: #E0E7FF;
}}
/* botones */
QPushButton {{
  border: 1px solid {BORDER}; background: {CARD}; padding: 6px 12px; border-radius: 10px;
}}
QPushButton#PrimaryButton {{
  background: {PRIMARY}; color: white; border: 1px solid {PRIMARY};
}}
QPushButton#PrimaryButton:hover {{ background: {PRIMARY_D}; }}
QPushButton#DangerButton {{
  background: {DANGER}; color: white; border: 1px solid {DANGER};
}}
/* icon buttons (acciones) */
QPushButton[class~="icon"] {{
  padding: 4px; min-width: 36px; min-height: 36px; border-radius: 8px;
}}
QPushButton[class~="icon"]:hover {{ background: #F3F4F6; }}
QPushButton[class~="icon"][class~="danger"] {{
  border-color: #FECACA;
}}
"""

def apply_theme(app: QApplication):
    # estilo consistente
    app.setStyle("Fusion")
    # locale global es-PY (miles . coma ,)
    QLocale.setDefault(QLocale(QLocale.Spanish, QLocale.Paraguay))
    # paleta leve
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.Base, QColor(CARD))
    pal.setColor(QPalette.AlternateBase, QColor("#F6F8FC"))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
