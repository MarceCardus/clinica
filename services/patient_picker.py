from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLineEdit, QVBoxLayout, QCompleter
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from sqlalchemy import or_, func, text
import unicodedata

class PatientPicker(QWidget):
    def __init__(self, session, parent=None, placeholder="Buscar paciente (nombre y apellido)..."):
        super().__init__(parent)
        self._session = session
        self._current = None

        # input
        self.input = QLineEdit(self)
        self.input.setPlaceholderText(placeholder)

        # completer (no roba foco)
        self.model = QStandardItemModel(self)
        self.completer = QCompleter(self.model, self)
        self.completer.setCaseSensitivity(False)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated.connect(self._activated)   # click o Enter en la lista
        self.input.setCompleter(self.completer)

        # layout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.input)

        # eventos
        self.input.textEdited.connect(self._search)
        self.input.returnPressed.connect(self._confirm_enter)

        # detectar unaccent sin ensuciar la sesión
        self._has_unaccent = False
        try:
            self._session.execute(text("SELECT unaccent('a')")).scalar()
            self._has_unaccent = True
            self._session.rollback()
        except Exception:
            try: self._session.rollback()
            except Exception: pass
            self._has_unaccent = False

    # ---------------- helpers acentos ----------------
    @staticmethod
    def _strip_accents_py(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

    def _no_accent_sql(self, col):
        return func.translate(
            func.lower(col),
            "áàâäãéèêëíìîïóòôöõúùûüñçÁÀÂÄÃÉÈÊËÍÌÎÏÓÒÔÖÕÚÙÛÜÑÇ",
            "aaaaaeeeeiiiiooooouuuuncAAAAAEEEEIIIIOOOOOUUUUNC",
        )

    # ---------------- búsqueda ----------------
    def _search(self, text):
        q = (text or "").strip()
        self._current = None
        self.model.clear()

        if len(q) < 2:
            return

        from models.paciente import Paciente

        if self._has_unaccent:
            term = f"%{q}%"
            filtro = or_(
                func.unaccent(Paciente.nombre).ilike(func.unaccent(term)),
                func.unaccent(Paciente.apellido).ilike(func.unaccent(term)),
            )
        else:
            norm = self._strip_accents_py(q).lower()
            filtro = or_(
                self._no_accent_sql(Paciente.nombre).ilike(f"%{norm}%"),
                self._no_accent_sql(Paciente.apellido).ilike(f"%{norm}%"),
            )

        rows = (self._session.query(Paciente.idpaciente, Paciente.apellido, Paciente.nombre)
                .filter(filtro)
                .order_by(Paciente.apellido.asc(), Paciente.nombre.asc())
                .limit(20)
                .all())

        # llenar modelo (solo Apellido, Nombre)
        for pid, ap, no in rows:
            txt = f"{ap or ''}, {no or ''}".strip(", ")
            it = QStandardItem(txt)
            it.setData(int(pid), Qt.UserRole)
            self.model.appendRow(it)

        # no seleccionamos nada por defecto → podés seguir escribiendo

    # activado desde la lista
    def _activated(self, arg):
        """
        Puede venir como str (texto) o como QModelIndex según la señal.
        Seteamos _current de forma segura.
        """
        text = None
        idx = None

        try:
            # Si vino un índice
            from PyQt5.QtCore import QModelIndex
            if isinstance(arg, QModelIndex):
                idx = arg
                it = self.model.itemFromIndex(idx)
                if it is not None:
                    self._current = int(it.data(Qt.UserRole))
                    text = it.text()
            else:
                # Si vino como str
                text = str(arg) if arg is not None else ""
                # buscar exacto por texto
                for r in range(self.model.rowCount()):
                    it = self.model.item(r)
                    if it and it.text() == text:
                        self._current = int(it.data(Qt.UserRole))
                        break
        except Exception:
            # por cualquier cosa, no explotar
            pass

        if text:
            self.input.setText(text)

    # Enter en el QLineEdit
    def _confirm_enter(self):
        """
        Enter en el QLineEdit:
        - Si hay un ítem resaltado en el popup -> usarlo.
        - Si no, pero hay filas -> tomar la primera.
        - Si no hay filas -> no hacer nada.
        """
        popup = self.completer.popup()
        try:
            idx = popup.currentIndex() if popup is not None else None
        except Exception:
            idx = None

        it = None
        if idx is not None and idx.isValid():
            it = self.model.itemFromIndex(idx)

        if it is None and self.model.rowCount() > 0:
            it = self.model.item(0)

        if it is not None:
            pid = it.data(Qt.UserRole)
            if pid is not None:
                self._current = int(pid)
                self.input.setText(it.text())
    # API pública
    def current_id(self):
        return self._current

    def set_current(self, pid: int, display_text: str = None):
        self._current = int(pid) if pid else None
        if display_text:
            self.input.setText(display_text)
