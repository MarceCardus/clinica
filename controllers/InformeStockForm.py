from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QApplication
)
from controllers.informe_stock import StockController

TIPOS_INSUMO = ["TODOS", "MEDICAMENTO", "DESCARTABLE", "REACTIVO", "ANTIBIOTICO"]
CATEGORIAS_INSUMO = ["TODOS", "CONSUMO_INTERNO", "USO_PROCEDIMIENTO"]

class InformeStockForm(QWidget):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.controller = StockController(session)
        self.setWindowTitle("Informe de Stock de Insumos")
        self.setMinimumWidth(800)

        # Layout principal
        layout = QVBoxLayout(self)

        # Fila de filtros
        filtros_layout = QHBoxLayout()
        filtros_layout.addWidget(QLabel("Tipo:"))
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(TIPOS_INSUMO)
        filtros_layout.addWidget(self.combo_tipo)

        filtros_layout.addWidget(QLabel("Categoría:"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.addItems(CATEGORIAS_INSUMO)
        filtros_layout.addWidget(self.combo_categoria)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.cargar_tabla)
        filtros_layout.addWidget(self.btn_buscar)

        layout.addLayout(filtros_layout)

        # Tabla de resultados
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels([
            "ID", "Nombre", "Tipo", "Categoría", "Unidad", "Stock Actual"
        ])
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabla)

        # Cargar datos iniciales
        self.cargar_tabla()

    def cargar_tabla(self):
        tipo = self.combo_tipo.currentText()
        categoria = self.combo_categoria.currentText()

        resultados = self.controller.get_stock_insumos(
            tipo if tipo != "TODOS" else None,
            categoria if categoria != "TODOS" else None
        )

        self.tabla.setRowCount(len(resultados))
        for row, dato in enumerate(resultados):
            idinsumo, nombre, tipo, categoria, unidad, stock_actual = dato
            self.tabla.setItem(row, 0, QTableWidgetItem(str(idinsumo)))
            self.tabla.setItem(row, 1, QTableWidgetItem(str(nombre)))
            self.tabla.setItem(row, 2, QTableWidgetItem(str(tipo)))
            self.tabla.setItem(row, 3, QTableWidgetItem(str(categoria)))
            self.tabla.setItem(row, 4, QTableWidgetItem(str(unidad)))
            self.tabla.setItem(row, 5, QTableWidgetItem(str(stock_actual)))

        self.tabla.resizeColumnsToContents()

# ------- Si querés probarlo como ventana independiente -------
if __name__ == "__main__":
    import sys
    from utils.db import SessionLocal
    app = QApplication(sys.argv)
    session = SessionLocal()
    win = InformeStockForm(session)
    win.show()
    sys.exit(app.exec_())
