from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QTime, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QPen
import math

class CircularTimePicker(QDialog):
    timeSelected = pyqtSignal(QTime)

    def __init__(self, parent=None, initial_time=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar hora")
        self.setFixedSize(260, 320)

        self.selected_hour = 12
        self.selected_minute = 0
        if initial_time:
            self.selected_hour = initial_time.hour()
            self.selected_minute = initial_time.minute()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.label = QLabel(self.format_time())
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.ok_btn = QPushButton("OK", self)
        self.ok_btn.clicked.connect(self.accept)
        layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancelar", self)
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

        self.is_selecting_minutes = False

    def format_time(self):
        return f"{self.selected_hour:02d}:{self.selected_minute:02d}"

    def mousePressEvent(self, event):
        center = QPoint(self.width() // 2, self.width() // 2)
        dx = event.x() - center.x()
        dy = event.y() - center.y()
        angle = math.atan2(-dy, dx)
        angle_deg = (angle * 180 / math.pi) % 360

        if not self.is_selecting_minutes:
            hour = int((angle_deg + 90) // 30) % 12
            self.selected_hour = hour if hour != 0 else 12
            self.is_selecting_minutes = True
        else:
            # MINUTOS cada 10, pero con mayor tolerancia
            sector = int(((angle_deg + 90) % 360) // 60)
            minute = sector * 10
            self.selected_minute = minute
            self.is_selecting_minutes = False

        self.label.setText(self.format_time())
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPoint(self.width() // 2, self.width() // 2)
        radius = self.width() // 2 - 20

        # Draw circle
        pen = QPen(Qt.gray, 3)
        painter.setPen(pen)
        painter.drawEllipse(center, radius, radius)

        # Draw hour/minute markers
        if not self.is_selecting_minutes:
            for i in range(12):
                angle = (i * 30) - 90
                x = center.x() + int(radius * 0.85 * math.cos(math.radians(angle)))
                y = center.y() + int(radius * 0.85 * math.sin(math.radians(angle)))
                txt = f"{i+1}"
                painter.drawText(x - 10, y + 5, 20, 15, Qt.AlignCenter, txt)
        else:
            # SOLO CADA 10 MINUTOS
            for i in range(6):
                minute = i * 10
                angle = (minute * 6) - 90
                x = center.x() + int(radius * 0.85 * math.cos(math.radians(angle)))
                y = center.y() + int(radius * 0.85 * math.sin(math.radians(angle)))
                txt = f"{minute:02d}"
                painter.drawText(x - 10, y + 5, 20, 15, Qt.AlignCenter, txt)

        # Draw selected
        if not self.is_selecting_minutes:
            angle = ((self.selected_hour-1) * 30) - 90
        else:
            angle = (self.selected_minute * 6) - 90
        sel_x = center.x() + int(radius * 0.55 * math.cos(math.radians(angle)))
        sel_y = center.y() + int(radius * 0.55 * math.sin(math.radians(angle)))
        pen.setColor(Qt.red)
        pen.setWidth(4)
        painter.setPen(pen)
        painter.drawLine(center, QPoint(sel_x, sel_y))

    def get_time(self):
        return QTime(self.selected_hour, self.selected_minute)
