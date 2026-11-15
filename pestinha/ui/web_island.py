"""Núcleo: a ilha em WebEngine, sem bordas, sempre no topo e centralizada no topo da tela.

A janela tem tamanho fixo (a maior área que a interface usa) e fica quase toda transparente.
Toda a animação (molas, expansão, orbe) roda em CSS/canvas dentro da página; a página informa
pela ponte o retângulo visível, e a janela aplica `setMask`: fora dele o clique passa para o
desktop. Assim nada redimensiona a cada quadro e o movimento fica liso.

Sem PySide6-WebEngine instalado, `criar_ilha` devolve a ilha nativa (`ui/ilha.py`).
"""

import json
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QUrl
from PySide6.QtGui import QColor, QGuiApplication, QRegion
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
MARGEM_VISIVEL = 120            # px da pílula que ficam na tela quando você a joga para a borda
ARQUIVO_POSICAO = "web_posicao.json"


def limitar_posicao(x, y, tela, largura, altura):
    """Mantém a janela com pelo menos MARGEM_VISIVEL px visíveis na horizontal e a barra no topo ou abaixo."""
    x = min(max(int(x), tela.left() - largura + MARGEM_VISIVEL), tela.right() - MARGEM_VISIVEL)
    y = min(max(int(y), tela.top()), tela.bottom() - altura // 4)
    return x, y


class WebIlha(QWidget):
    """Janela transparente que recorta o clique para a forma visível da interface."""

    def __init__(self, app, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Pestinha")
        self._app = app
        self.ponte = Ponte(app, self)
        self.ponte.regiao.connect(self.aplicar_regiao)
        self.ponte.movimento.connect(self.mover_por)
        self.ponte.soltou.connect(self.salvar_posicao)
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
        largura, altura = JANELA
        salva = self._ler_posicao()
        if salva:
            tela = (QGuiApplication.screenAt(QPoint(*salva)) or QGuiApplication.primaryScreen()).geometry()
            self.move(*limitar_posicao(*salva, tela, largura, altura))
            return
        tela = self.screen().geometry() if self.screen() else None
        if tela is None:
            self.setGeometry(0, 0, largura, altura)
            return
        self.setGeometry(tela.x() + (tela.width() - largura) // 2, tela.y(), largura, altura)

    # ----- arrastar: a pílula vai para onde você quiser, e a posição fica salva -----
    def mover_por(self, dx, dy):
        destino = QPoint(self.x() + dx, self.y() + dy)
        tela = (QGuiApplication.screenAt(destino) or self.screen()).geometry()
        self.move(*limitar_posicao(destino.x(), destino.y(), tela, self.width(), self.height()))

    def _arquivo_posicao(self):
        return Path(self._app.paths.memory) / ARQUIVO_POSICAO

    def _ler_posicao(self):
        try:
            dados = json.loads(self._arquivo_posicao().read_text(encoding="utf-8"))
            x, y = dados["x"], dados["y"]
            return (x, y) if type(x) is int and type(y) is int else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def salvar_posicao(self):
        try:
            self._arquivo_posicao().write_text(json.dumps({"x": self.x(), "y": self.y()}), encoding="utf-8")
        except OSError:
            pass

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

    def anunciar(self, texto, tom="calmo", origem="pet"):
        """Balão do pet no topo da ilha."""
        self.ponte.anunciar(texto, tom, origem)

    def shutdown(self):
        """Para estado, narrador, áudio, Ollama e voz; chamado ao sair do app."""
        self.ponte.shutdown()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


def criar_ilha(app):
    """A ilha em WebEngine (padrão, perm `ilha_web`) quando disponível; senão a ilha nativa Qt."""
    return WebIlha(app) if WEB_OK and app.perms.get("ilha_web", True) else Ilha(app)
