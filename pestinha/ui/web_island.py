"""Ilha dinâmica em WebEngine: janela sem bordas, sempre no topo e centralizada no topo da tela.

A aparência vem de `ui/web/` (estilo Coucou + Moxen traduzidos); o backend fica em `ui/web_bridge.py`.
Sem PySide6-WebEngine instalado, `criar_ilha` devolve a ilha nativa (`ui/ilha.py`) como fallback.
"""

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .ilha import Ilha
from .web_bridge import Ponte

try:
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEB_OK = True
except ImportError:
    WEB_OK = False

PAGINA = Path(__file__).resolve().parent / "web" / "index.html"
COMPACTA = (300, 40)
EXPANDIDA = (980, 520)
ANIMACAO_MS = 260


class WebIlha(QWidget):
    """Pílula no topo da tela; expande e recolhe com animação de geometria."""

    def __init__(self, app, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Pestinha")
        self._aberta = False
        self._anim = None
        self.ponte = Ponte(app, self)
        self.ponte.expansao.connect(self.expandir)
        self.view = QWebEngineView(self)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        canal = QWebChannel(self.view.page())
        canal.registerObject("ponte", self.ponte)
        self.view.page().setWebChannel(canal)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.setUrl(QUrl.fromLocalFile(str(PAGINA)))
        self._posicionar(COMPACTA)

    # ----- geometria -----
    def _alvo(self, tamanho):
        tela = self.screen().geometry() if self.screen() else None
        if tela is None:
            return 0, 0, tamanho[0], tamanho[1]
        largura, altura = tamanho
        return tela.x() + (tela.width() - largura) // 2, tela.y(), largura, altura

    def _posicionar(self, tamanho):
        self.setGeometry(*self._alvo(tamanho))

    def expandir(self, aberta):
        """Anima a janela até o tamanho aberto ou compacto (ignora pedidos repetidos)."""
        aberta = bool(aberta)
        if aberta == self._aberta:
            return
        self._aberta = aberta
        destino = self._alvo(EXPANDIDA if aberta else COMPACTA)
        if self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(ANIMACAO_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(QRect(*destino))
        self._anim.start()

    # ----- ciclo de vida -----
    def showEvent(self, event):
        self.ponte.iniciar()
        super().showEvent(event)

    def hideEvent(self, event):
        self.ponte.parar()
        super().hideEvent(event)

    def shutdown(self):
        """Para estado, áudio, Ollama e voz; chamado ao sair do app."""
        if self._anim is not None:
            self._anim.stop()
        self.ponte.shutdown()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


def criar_ilha(app):
    """A ilha em WebEngine (padrão, perm `ilha_web`) quando disponível; senão a ilha nativa Qt."""
    return WebIlha(app) if WEB_OK and app.perms.get("ilha_web", True) else Ilha(app)
