# autocomplete_helpers.py
from PyQt5.QtWidgets import QCompleter
from PyQt5.QtCore import QStringListModel, Qt, QTimer

class LiveDbCompleter:
    """
    Enlaza un QLineEdit con un QCompleter que consulta a BD mientras se escribe (debounce).
    Puedes proveer cualquier callable 'fetch_fn(texto)' que devuelva lista de (display, id).
    """
    def __init__(self, line_edit, fetch_fn, on_pick_id, delay_ms=180, min_chars=1):
        self.line_edit = line_edit
        self.fetch_fn = fetch_fn          # fn: str -> List[Tuple[str, Any]]
        self.on_pick_id = on_pick_id      # fn: (id, display) -> None
        self.min_chars = min_chars

        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)

        self._model = QStringListModel([])
        self._completer = QCompleter(self._model, line_edit)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.activated[str].connect(self._activated)
        line_edit.setCompleter(self._completer)

        self._index_by_text = {}  # "display" -> id

        line_edit.textEdited.connect(self._start_timer)

    def _start_timer(self, _):
        self._timer.start( self._timer.interval() or 180 )

    def _refresh(self):
        texto = self.line_edit.text().strip()
        if len(texto) < self.min_chars:
            self._model.setStringList([])
            self._index_by_text.clear()
            return
        rows = self.fetch_fn(texto) or []
        display_list = []
        self._index_by_text.clear()
        for disp, _id in rows:
            display_list.append(disp)
            self._index_by_text[disp] = _id
        self._model.setStringList(display_list)
        # si hay sugerencias, abrir popup
        if display_list:
            self._completer.complete()

    def _activated(self, display_text):
        _id = self._index_by_text.get(display_text)
        if _id is not None:
            self.on_pick_id(_id, display_text)
