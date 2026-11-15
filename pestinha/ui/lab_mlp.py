"""
LAB MLP - painel didático e interativo da rede feedforward (6 -> 4 -> 4 -> 2).

Você mexe nas entradas e nos alvos; a rede responde na hora (forward) e os neurônios
acendem com as ativações reais. O botão Treinar roda backpropagation em segundo plano,
com progresso ao vivo: os pesos, a saída e a curva de perda se atualizam enquanto a rede aprende.
Pausar guarda o ponto alcançado; Reiniciar volta aos pesos iniciais.
"""

import math
import threading

import numpy as np
from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, QThreadPool, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from ..core.mlp import NeuralNetwork
from ..world.arrastavel import FloatingWidget
from . import tema

ENTRADAS = ("x1", "x2", "x3", "x4", "x5", "x6")
SAIDAS = ("y1", "y2")
X_PADRAO = (0.2, 0.8, 0.5, 0.1, 0.9, 0.3)
Y_PADRAO = (0.9, 0.1)
NOMES_PESOS = ("W1", "W2", "W3", "b1", "b2", "b3")
FORMAS = {"W1": (6, 4), "W2": (4, 4), "W3": (4, 2), "b1": (4,), "b2": (4,), "b3": (2,)}
EPOCAS_LOTE = 500
TAXA = 0.5
PASSO_PROGRESSO = 5          # a cada quantas épocas a interface recebe o estado
MAX_PERDAS = 5000


def _pesos_validos(pesos):
    """Dict com os seis parâmetros nas formas certas e sem valores não finitos."""
    try:
        return all(
            isinstance(pesos.get(n), np.ndarray) and pesos[n].shape == FORMAS[n] and np.isfinite(pesos[n]).all()
            for n in NOMES_PESOS
        )
    except (AttributeError, TypeError):
        return False


def _copia_pesos(rede):
    return {n: getattr(rede, n).copy() for n in NOMES_PESOS}


def _limitada(valor):
    """Ativação para o desenho: número finito entre 0 e 1."""
    try:
        valor = float(valor)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, min(1.0, valor)) if np.isfinite(valor) else 0.0


class _TreinoSignals(QObject):
    """Sinais do worker; chegam à thread da interface em fila."""

    progresso = Signal(object)
    concluido = Signal(object)
    falhou = Signal(str)
    liberado = Signal(object)


class _TreinoTask(QRunnable):
    """Treina uma cópia isolada da rede com as entradas e alvos escolhidos, emitindo o estado a cada passo."""

    def __init__(self, pesos, X, Y, epocas, taxa, cancelamento):
        super().__init__()
        self.pesos = pesos
        self.X, self.Y = X, Y
        self.epocas = epocas
        self.taxa = taxa
        self.cancelamento = cancelamento
        self.signals = _TreinoSignals()
        self.thread_ident = None

    def run(self):
        self.thread_ident = threading.get_ident()
        try:
            rede = NeuralNetwork()
            for nome in NOMES_PESOS:
                setattr(rede, nome, self.pesos[nome].copy())
            pendentes = []
            epoca = 0
            while epoca < self.epocas and not self.cancelamento.is_set():
                epoca += 1
                pendentes.append(rede.mse(self.Y, rede.forward(self.X)))
                rede.backward(self.X, self.Y, self.taxa)
                if epoca % PASSO_PROGRESSO == 0:
                    self.signals.progresso.emit({"pesos": _copia_pesos(rede), "perdas": pendentes, "epoca": epoca})
                    pendentes = []
            self.signals.concluido.emit({
                "pesos": _copia_pesos(rede), "perdas": pendentes, "epoca": epoca,
                "cancelado": self.cancelamento.is_set(),
            })
        except Exception as error:
            self.signals.falhou.emit(str(error)[:240])
        finally:
            self.signals.liberado.emit(self)

    def cancelar(self):
        """Para o loop de épocas no próximo passo; o ponto alcançado é mantido."""
        self.cancelamento.set()


class RedeWidget(QWidget):
    """Desenha a rede 6-4-4-2: neurônios acesos pela ativação real e conexões pela cor do peso."""

    def __init__(self):
        super().__init__()
        self.rede = None
        self.ativ = None          # [entrada, oculta1, oculta2, saída] do último forward
        self.alvo = np.zeros(2)
        self.setMinimumSize(360, 230)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def atualizar(self, rede, ativ, alvo):
        self.rede, self.ativ, self.alvo = rede, ativ, alvo
        self.update()

    def _posicoes(self):
        w, h = self.width(), self.height()
        camadas = [6, 4, 4, 2]
        esq, dir_ = 30, 128                      # à direita cabe o rótulo das saídas (y1, alvo)
        xs = [esq + (w - esq - dir_) * i / (len(camadas) - 1) for i in range(len(camadas))]
        margem = 30
        return [[(x, margem + (h - 2 * margem) * (i + 0.5) / n) for i in range(n)] for x, n in zip(xs, camadas)]

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tema.fundo_arredondado(p, self.width(), self.height(), raio=12, cor=tema.CARTAO)
        pos = self._posicoes()
        p.setFont(tema.fonte(8))
        p.setPen(tema.FRACO)
        p.drawText(12, 16, "pesos: verde +  ·  vermelho −  ·  anel = alvo")
        if self.rede is None or not _pesos_validos({n: getattr(self.rede, n) for n in NOMES_PESOS}):
            p.setPen(tema.FRACO)
            p.drawText(self.rect(), Qt.AlignCenter, "Pesos inválidos: clique em Reiniciar")
            p.end()
            return
        pesos = [self.rede.W1, self.rede.W2, self.rede.W3]
        for cam, W in enumerate(pesos):
            wmax = max(1e-6, float(np.abs(W).max()))
            for i, (x0, y0) in enumerate(pos[cam]):
                for j, (x1, y1) in enumerate(pos[cam + 1]):
                    w = float(W[i, j])
                    forca = abs(w) / wmax
                    cor = QColor(tema.VERDE) if w > 0 else QColor(tema.VERMELHO)
                    cor.setAlpha(int(30 + 200 * forca))
                    p.setPen(QPen(cor, 0.6 + 1.6 * forca))
                    p.drawLine(int(x0), int(y0), int(x1), int(y1))
        ativ = self.ativ or [np.zeros(6), np.zeros(4), np.zeros(4), np.zeros(2)]
        for ci, camada in enumerate(pos):
            for j, (x, y) in enumerate(camada):
                a = _limitada(ativ[ci][j])
                fill = QColor(tema.CYAN if ci < 3 else tema.AMBER)
                fill.setAlpha(int(40 + 215 * a))
                p.setBrush(fill)
                p.setPen(QPen(tema.INK, 1))
                p.drawEllipse(int(x - 9), int(y - 9), 18, 18)
        p.setBrush(Qt.NoBrush)
        for j, (x, y) in enumerate(pos[-1]):
            p.setPen(QPen(tema.AMBER, 1.5, Qt.DashLine))
            p.drawEllipse(int(x - 15), int(y - 15), 30, 30)
        p.setFont(tema.fonte(8))
        p.setPen(tema.FRACO)
        for j, (x, y) in enumerate(pos[0]):
            p.drawText(int(x - 27), int(y + 4), ENTRADAS[j])
        for j, (x, y) in enumerate(pos[-1]):
            saida = float(ativ[3][j]) if np.isfinite(ativ[3][j]) else 0.0
            p.drawText(int(x + 20), int(y + 4), f"{SAIDAS[j]} {saida:.2f}  (alvo {self.alvo[j]:.2f})")
        p.end()


class CurvaPerda(QWidget):
    """Curva da perda em escala logarítmica, com animação suave, ponto pulsando durante o treino e leitura ao passar o mouse.

    Anima só enquanto há algo se movendo ou treinando, e só com o painel visível: fora disso o timer para."""

    QUADRO_MS = 33                      # ~30 quadros por segundo, enquanto anima
    SUAVIZA = 0.22                      # fração do caminho até o valor novo a cada quadro

    def __init__(self):
        super().__init__()
        self.perdas = []
        self._alvo = []                 # log10 da perda (valores reais)
        self._mostra = []               # log10 exibido (interpolado até o alvo)
        self._pulsar = False
        self._fase = 0.0
        self._mouse_x = None
        self.setMinimumHeight(110)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._timer = QTimer(self)
        self._timer.setInterval(self.QUADRO_MS)
        self._timer.timeout.connect(self._quadro)

    def definir(self, perdas):
        self.perdas = [float(v) for v in perdas[-600:] if np.isfinite(v)]
        self._alvo = [math.log10(max(v, 1e-12)) for v in self.perdas]
        if len(self._mostra) > len(self._alvo):
            self._mostra = self._mostra[:len(self._alvo)]
        while len(self._mostra) < len(self._alvo):          # ponto novo nasce do último exibido e cresce até o alvo
            self._mostra.append(self._mostra[-1] if self._mostra else self._alvo[len(self._mostra)])
        self._ligar()
        self.update()

    def pulsar(self, ativo):
        """Liga o pulso do último ponto enquanto o treino roda."""
        self._pulsar = bool(ativo)
        self._ligar()

    def _ligar(self):
        movendo = any(abs(a - m) > 1e-4 for a, m in zip(self._alvo, self._mostra))
        if self.isVisible() and (self._pulsar or movendo):
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def _quadro(self):
        self._fase += self.QUADRO_MS / 1000.0
        mexeu = False
        for i, alvo in enumerate(self._alvo):
            diff = alvo - self._mostra[i]
            if abs(diff) > 1e-4:
                self._mostra[i] += diff * self.SUAVIZA
                mexeu = True
            else:
                self._mostra[i] = alvo
        if not mexeu and not self._pulsar:
            self._timer.stop()
        self.update()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._ligar()

    def leaveEvent(self, event):
        self._mouse_x = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_x = event.position().x()
        self.update()

    def _area(self):
        """Retângulo do gráfico, descontando eixos e rótulos."""
        return QRectF(44, 20, self.width() - 56, self.height() - 42)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        tema.cartao(p, QRectF(0, 0, w, h), raio=10)
        area = self._area()
        p.setFont(tema.fonte(8))
        if len(self._mostra) < 2:
            p.setPen(tema.FRACO)
            p.drawText(self.rect(), Qt.AlignCenter, "Treine para ver a perda cair")
            p.end()
            return
        lo = min(self._mostra) - 0.05
        hi = max(self._mostra) + 0.05
        span = max(1e-6, hi - lo)
        n = len(self._mostra)

        def xy(i, v):
            return (area.left() + area.width() * i / (n - 1),
                    area.bottom() - (v - lo) / span * area.height())

        # grade horizontal com valores em escala real (potências de 10)
        for decada in range(math.floor(lo), math.ceil(hi) + 1):      # marcas em potências de 10
            if not lo <= decada <= hi:
                continue
            _, y = xy(0, decada)
            p.setPen(QPen(QColor(255, 255, 255, 16), 1))
            p.drawLine(int(area.left()), int(y), int(area.right()), int(y))
            p.setPen(tema.FRACO)
            p.drawText(QRectF(0, y - 7, 40, 14), Qt.AlignRight | Qt.AlignVCenter, f"1e{decada}")
        p.drawText(QRectF(area.left(), h - 16, area.width(), 14), Qt.AlignLeft, "épocas")
        p.drawText(QRectF(area.left(), h - 16, area.width(), 14), Qt.AlignRight, str(len(self.perdas)))

        # área preenchida com degradê e a linha
        pts = [xy(i, v) for i, v in enumerate(self._mostra)]
        caminho = QPainterPath(QPointF(pts[0][0], area.bottom()))
        for x, y in pts:
            caminho.lineTo(x, y)
        caminho.lineTo(pts[-1][0], area.bottom())
        caminho.closeSubpath()
        degrade = QLinearGradient(0, area.top(), 0, area.bottom())
        degrade.setColorAt(0, QColor(tema.VERDE.red(), tema.VERDE.green(), tema.VERDE.blue(), 90))
        degrade.setColorAt(1, QColor(tema.VERDE.red(), tema.VERDE.green(), tema.VERDE.blue(), 0))
        p.fillPath(caminho, QBrush(degrade))
        p.setPen(QPen(tema.VERDE, 1.8))
        p.setBrush(Qt.NoBrush)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

        # ponto final, com brilho pulsando durante o treino
        ux, uy = pts[-1]
        if self._pulsar:
            raio = 6 + 3 * (0.5 + 0.5 * math.sin(self._fase * 6))
            halo = QColor(tema.VERDE)
            halo.setAlpha(70)
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(ux, uy), raio, raio)
        p.setBrush(tema.VERDE)
        p.setPen(QPen(tema.INK, 1))
        p.drawEllipse(QPointF(ux, uy), 3.5, 3.5)

        # leitura ao passar o mouse
        if self._mouse_x is not None and area.left() <= self._mouse_x <= area.right():
            i = round((self._mouse_x - area.left()) / area.width() * (n - 1))
            i = max(0, min(n - 1, i))
            x, y = pts[i]
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            p.drawLine(int(x), int(area.top()), int(x), int(area.bottom()))
            p.setBrush(tema.VERDE)
            p.setPen(QPen(tema.INK, 1))
            p.drawEllipse(QPointF(x, y), 3.5, 3.5)
            texto = f"época {i + 1} · perda {self.perdas[i]:.6f}"
            p.setPen(tema.TEXTO)
            largura = 190
            tx = min(max(x - largura / 2, area.left()), area.right() - largura)
            p.drawText(QRectF(tx, 2, largura, 16), Qt.AlignCenter, texto)
        else:
            p.setPen(tema.TEXTO)
            p.drawText(QRectF(area.left(), 2, area.width(), 16), Qt.AlignRight, f"perda {self.perdas[-1]:.6f}")
        p.end()


class LabMLP(FloatingWidget):
    """Painel 'Laboratório MLP': entradas e alvos ao vivo, treino com progresso, pausa e reinício."""

    def __init__(self, app, pos):
        super().__init__(app, "mlp", "Laboratório MLP", (480, 660), (420, 580), pos)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.rede = NeuralNetwork()
        self.perdas = []
        self.saida = np.zeros(2)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._treino_task = None
        corpo = QVBoxLayout(self)
        corpo.setContentsMargins(14, 14, 24, 14)
        corpo.setSpacing(8)
        self.desenho = RedeWidget()
        corpo.addWidget(self.desenho, 1)
        grade = QGridLayout()
        grade.setHorizontalSpacing(8)
        grade.setVerticalSpacing(4)
        self.sl_entrada, self.sl_alvo, self.lbl_valor = [], [], []
        nomes = list(ENTRADAS) + list(SAIDAS)
        valores = [v for v in X_PADRAO] + [v for v in Y_PADRAO]
        for linha, (nome, valor) in enumerate(zip(nomes, valores)):
            rotulo = QLabel(f"entrada {nome}" if nome in ENTRADAS else f"alvo {nome}")
            rotulo.setStyleSheet(f"color: {tema.FRACO.name()}; font-size: 10px;")
            rotulo.setFixedWidth(84)
            sl = QSlider(Qt.Horizontal)
            sl.setMinimumWidth(120)
            sl.setRange(0, 100)
            sl.setValue(round(valor * 100))
            sl.setStyleSheet(self._estilo_slider())
            num = QLabel(f"{valor:.2f}")
            num.setStyleSheet(f"color: {tema.TEXTO.name()}; font-size: 10px;")
            num.setFixedWidth(34)
            sl.valueChanged.connect(lambda _v, i=linha: self._valor_mudou(i))
            grade.addWidget(rotulo, linha, 0)
            grade.addWidget(sl, linha, 1)
            grade.addWidget(num, linha, 2)
            (self.sl_entrada if linha < 6 else self.sl_alvo).append(sl)
            self.lbl_valor.append(num)
        corpo.addLayout(grade)
        botoes = QHBoxLayout()
        self.btn_treinar = QPushButton(f"Treinar {EPOCAS_LOTE} épocas")
        self.btn_treinar.setStyleSheet(tema.qss_pill())
        self.btn_treinar.clicked.connect(self.treinar)
        self.btn_reiniciar = QPushButton("Reiniciar pesos")
        self.btn_reiniciar.setStyleSheet(tema.qss_pill())
        self.btn_reiniciar.clicked.connect(self.reiniciar)
        botoes.addWidget(self.btn_treinar)
        botoes.addWidget(self.btn_reiniciar)
        corpo.addLayout(botoes)
        self.curva = CurvaPerda()
        corpo.addWidget(self.curva)
        self.saida_lbl = QLabel()
        self.saida_lbl.setStyleSheet(f"color: {tema.TEXTO.name()}; background: transparent; font-size: 11px;")
        corpo.addWidget(self.saida_lbl)
        self.rotulo = QLabel("Mexa nas entradas: a rede responde na hora.")
        self.rotulo.setStyleSheet(f"color: {tema.FRACO.name()}; font-size: 10px;")
        corpo.addWidget(self.rotulo)
        self._prever()

    @staticmethod
    def _estilo_slider():
        return (
            "QSlider::groove:horizontal { height: 3px; background: #34363b; border-radius: 2px; }"
            f"QSlider::sub-page:horizontal {{ background: {tema.CYAN.name()}; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; border-radius: 6px; background: {tema.INK.name()}; }}"
        )

    def _valores_entrada(self):
        return np.array([s.value() / 100.0 for s in self.sl_entrada])

    def _valores_alvo(self):
        return np.array([s.value() / 100.0 for s in self.sl_alvo])

    def _valor_mudou(self, linha):
        self.lbl_valor[linha].setText(f"{(self.sl_entrada + self.sl_alvo)[linha].value() / 100:.2f}")
        self._prever()

    def _prever(self):
        """Forward com as entradas atuais: atualiza ativações, saída e o desenho."""
        x = self._valores_entrada()
        try:
            saida = self.rede.forward(x)
        except (ValueError, FloatingPointError):
            self.desenho.atualizar(None, None, self._valores_alvo())
            self.saida_lbl.setText("Pesos inválidos: clique em Reiniciar pesos.")
            return
        cache = self.rede._cache
        self.saida = np.array(saida, dtype=float)
        ativ = [x.copy(), cache[2][0].copy(), cache[4][0].copy(), self.saida.copy()]
        alvo = self._valores_alvo()
        self.desenho.atualizar(self.rede, ativ, alvo)
        self.saida_lbl.setText(
            f"saída y1 {saida[0]:.3f} · y2 {saida[1]:.3f}  |  erro (MSE) {NeuralNetwork.mse(alvo, saida):.5f}"
        )

    def treinar(self):
        """Inicia o treino com as entradas e alvos atuais; com treino rodando, pausa."""
        if self._treino_task is not None:
            self.cancelar_treino()
            return
        X = self._valores_entrada().reshape(1, 6)
        Y = self._valores_alvo().reshape(1, 2)
        task = _TreinoTask(_copia_pesos(self.rede), X, Y, EPOCAS_LOTE, TAXA, threading.Event())
        task.signals.progresso.connect(self._progresso)
        task.signals.concluido.connect(self._treino_concluido)
        task.signals.falhou.connect(self._treino_falhou)
        task.signals.liberado.connect(self._treino_liberado)
        self._treino_task = task
        self.btn_treinar.setText("Pausar")
        self.curva.pulsar(True)
        self.btn_reiniciar.setEnabled(False)
        self.rotulo.setText("Treinando em segundo plano…")
        self._pool.start(task)

    def _aplicar(self, pesos):
        """Copia os pesos do worker para a rede da interface (depois de validar as formas)."""
        if not _pesos_validos(pesos):
            return False
        for nome in NOMES_PESOS:
            setattr(self.rede, nome, pesos[nome].copy())
        return True

    def _progresso(self, dados):
        if not self._aplicar(dados["pesos"]):
            return
        self.perdas = (self.perdas + dados["perdas"])[-MAX_PERDAS:]
        self.curva.definir(self.perdas)
        self.rotulo.setText(f"treinando: época {dados['epoca']}/{EPOCAS_LOTE} · perda {self.perdas[-1]:.6f}")
        self._prever()

    def _treino_concluido(self, dados):
        if not self._aplicar(dados["pesos"]):
            self._treino_falhou("pesos inválidos ao final do treino")
            return
        self.perdas = (self.perdas + dados["perdas"])[-MAX_PERDAS:]
        self.curva.definir(self.perdas)
        estado = "pausado" if dados["cancelado"] else "concluído"
        perda = f"{self.perdas[-1]:.6f}" if self.perdas else "—"
        self.rotulo.setText(f"treino {estado} em {dados['epoca']} épocas · perda {perda}")
        self._prever()

    def _treino_falhou(self, message):
        self.rotulo.setText(f"Treino interrompido: {message}")

    def _treino_liberado(self, _task):
        self._treino_task = None
        self.curva.pulsar(False)
        self.btn_treinar.setText(f"Treinar {EPOCAS_LOTE} épocas")
        self.btn_reiniciar.setEnabled(True)

    def reiniciar(self):
        """Volta aos pesos iniciais e apaga a curva; só quando não há treino rodando."""
        if self._treino_task is not None:
            return
        self.rede = NeuralNetwork()
        self.perdas = []
        self.curva.definir([])
        self.rotulo.setText("Pesos reiniciados.")
        self._prever()

    def cancelar_treino(self):
        """Pede ao worker para parar entre épocas sem bloquear a interface."""
        if self._treino_task is not None:
            self._treino_task.cancelar()

    def hideEvent(self, event):
        self.cancelar_treino()
        super().hideEvent(event)

    def shutdown(self):
        """Para treino pendente e aguarda o worker por um intervalo limitado."""
        self.cancelar_treino()
        self._pool.clear()
        self._pool.waitForDone(750)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
