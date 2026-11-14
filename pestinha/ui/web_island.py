"""Núcleo: a ilha em WebEngine, sem bordas, sempre no topo e centralizada no topo da tela.

A janela tem tamanho fixo (a maior área que a interface usa) e fica quase toda transparente.
Toda a animação (molas, expansão, orbe) roda em CSS/canvas dentro da página; a página informa
pela ponte o retângulo visível, e a janela aplica `setMask`: fora dele o clique passa para o
desktop. Assim nada redimensiona a cada quadro e o movimento fica liso.

Sem PySide6-WebEngine instalado, `criar_ilha` devolve a ilha nativa (`ui/ilha.py`).
"""

from pathlib import Path

from PySide6.QtCore import QRect, Qt, QUrl
from PySide6.QtGui import QColor, QRegion
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
JANELA = (1040, 620)            # área máxima usada pela interface expandida
REGIAO_INICIAL = (330, 0, 380, 52)


class WebIlha(QWidget):
    """Janela transparente que recorta o clique para a forma visível da interface."""

    def __init__(self, app, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Pestinha")
        self.ponte = Ponte(app, self)
        self.ponte.regiao.connect(self.aplicar_regiao)
        self.view = QWebEngineView(self)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        canal = QWebChannel(self.view.page())
        canal.registerObject("ponte", self.ponte)
        self.view.page().setWebChannel(canal)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.setUrl(QUrl.fromLocalFile(str(PAGINA)))
        self._posicionar()
        self.aplicar_regiao(*REGIAO_INICIAL)

    def _posicionar(self):
        tela = self.screen().geometry() if self.screen() else None
        largura, altura = JANELA
        if tela is None:
            self.setGeometry(0, 0, largura, altura)
            return
        self.setGeometry(tela.x() + (tela.width() - largura) // 2, tela.y(), largura, altura)

    def aplicar_regiao(self, x, y, largura, altura):
        """Só o retângulo visível recebe o mouse; o resto da janela é atravessável."""
        rect = QRect(int(x), int(y), int(largura), int(altura)).intersected(self.rect())
        self.setMask(QRegion(rect if not rect.isEmpty() else QRect(0, 0, 1, 1)))

    # ----- ciclo de vida -----
    def showEvent(self, event):
        self.ponte.iniciar()
        super().showEvent(event)

    def hideEvent(self, event):
        self.ponte.parar()
        super().hideEvent(event)

    def shutdown(self):
        """Para estado, narrador, áudio, Ollama e voz; chamado ao sair do app."""
        self.ponte.shutdown()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


def criar_ilha(app):
    """A ilha em WebEngine (padrão, perm `ilha_web`) quando disponível; senão a ilha nativa Qt."""
    return WebIlha(app) if WEB_OK and app.perms.get("ilha_web", True) else Ilha(app)
