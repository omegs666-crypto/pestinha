"""
LAB MLP - painel didático da rede feedforward (6 -> 4 -> 4 -> 2).

Mostra os neurônios e as conexões, e um botão "Treinar" que roda épocas de
backpropagation em dados fictícios e desenha a perda caindo embaixo.
Fica no mesmo sistema de painéis flutuantes do monitor neural e do protesto.
"""

import numpy as np
import threading

from PySide6.QtCore import QObject, QRectF, QRunnable, QThreadPool, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QWidget

from ..core.mlp import NeuralNetwork
from ..world.arrastavel import FloatingWidget
from . import tema

BG = tema.BG
TEXT = tema.TEXTO
GOOD = tema.VERDE
MUTED = tema.FRACO

X_DEMO = np.array([[0.2, 0.8, 0.5, 0.1, 0.9, 0.3]])
Y_DEMO = np.array([[0.9, 0.1]])


class _TreinoSignals(QObject):
    """Sinais para devolver resultado do worker à thread Qt."""

    concluido = Signal(object)
    falhou = Signal(str)
    liberado = Signal(object)


class _TreinoTask(QRunnable):
    """Treina uma cópia isolada da MLP sem acessar widgets fora da thread Qt."""

    def __init__(self, pesos, cancelamento):
        super().__init__()
        self.pesos = pesos
        self.cancelamento = cancelamento
        self.signals = _TreinoSignals()
        self.thread_ident = None

    def run(self):
        self.thread_ident = threading.get_ident()
        try:
            rede = NeuralNetwork()
            for nome, value in self.pesos.items():
                setattr(rede, nome, value.copy())
            perdas = rede.train(
                X_DEMO, Y_DEMO, epocas=500, taxa=0.5,
                cancel_event=self.cancelamento,
            )
            a1 = rede.relu(X_DEMO @ rede.W1 + rede.b1)
            a2 = rede.relu(a1 @ rede.W2 + rede.b2)
            saida = rede.forward(X_DEMO)
            resultado = {
                "pesos": {nome: getattr(rede, nome).copy()
                          for nome in ("W1", "W2", "W3", "b1", "b2", "b3")},
                "perdas": perdas,
                "ativacoes": [X_DEMO[0].copy(), a1[0], a2[0], saida[0]],
            }
            self.signals.concluido.emit(resultado)
        except Exception as error:
            self.signals.falhou.emit(str(error)[:240])
        finally:
            self.signals.liberado.emit(self)

    def cancelar(self):
        """Sinaliza ao loop de épocas para parar no próximo limite seguro."""
        self.cancelamento.set()


class RedeWidget(QWidget):
    """Desenha a MLP 6-4-4-2: neurônios como círculos e conexões com peso na cor (verde +, vermelho −)."""
    def __init__(self, rede):
        """Guarda a rede e define o tamanho do desenho."""
        super().__init__()
        self.rede = rede
        self.setMinimumSize(340, 230)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _posicoes(self):
        """Coordenadas de cada neurônio: entrada (6), ocultas (4, 4), saída (2)."""
        w, h = self.width(), self.height()
        camadas = [6, 4, 4, 2]
        xs = [w * (i + 1) / (len(camadas) + 1) for i in range(len(camadas))]
        return [[(x, h * (i + 1) / (n + 1)) for i in range(n)] for x, n in zip(xs, camadas)]

    def paintEvent(self, _ev):
        """Desenha conexões (cor pelo peso) e neurônios (preenchido pela ativação do último forward)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tema.fundo_arredondado(p, self.width(), self.height(), raio=12, cor=tema.CARTAO)
        pos = self._posicoes()
        pesos = [
            getattr(self.rede, "W1", None),
            getattr(self.rede, "W2", None),
            getattr(self.rede, "W3", None),
        ]
        expected = ((6, 4), (4, 4), (4, 2))
        if any(
            not isinstance(weight, np.ndarray)
            or weight.shape != shape
            or not np.isfinite(weight).all()
            for weight, shape in zip(pesos, expected)
        ):
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignCenter, "Pesos da rede inválidos")
            p.end()
            return
        for cam, W in enumerate(pesos):
            wmax = max(1e-6, float(np.abs(W).max()))
            for i, (x0, y0) in enumerate(pos[cam]):
                for j, (x1, y1) in enumerate(pos[cam + 1]):
                    w_ = float(W[i, j])
                    cor = GOOD if w_ > 0 else QColor("#e0474c")
                    cor.setAlpha(int(40 + 180 * abs(w_) / wmax))
                    p.setPen(QPen(cor, 1))
                    p.drawLine(int(x0), int(y0), int(x1), int(y1))
        ativ = getattr(self.rede, "_ativ", None)
        expected_activations = (6, 4, 4, 2)
        valid_activations = (
            isinstance(ativ, (list, tuple))
            and len(ativ) == len(expected_activations)
            and all(
                isinstance(layer, np.ndarray)
                and layer.shape == (size,)
                and np.isfinite(layer).all()
                for layer, size in zip(ativ, expected_activations)
            )
        )
        for ci, camada in enumerate(pos):
            for j, (x, y) in enumerate(camada):
                a = _bounded_activation(ativ[ci][j]) if valid_activations else 0.0
                fill = QColor("#1c3b28"); fill.setAlpha(int(60 + 180 * a))
                p.setBrush(fill)
                p.setPen(QPen(GOOD, 1.5))
                p.drawEllipse(int(x - 9), int(y - 9), 18, 18)
        p.end()


def _bounded_activation(value):
    """Garante alfa visual finito para uma ativação numérica."""
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, min(1.0, value)) if np.isfinite(value) else 0.0


class LabMLP(FloatingWidget):
    """Painel 'Laboratório MLP': desenho da rede + botão Treinar + gráfico de perda."""
    def __init__(self, app, pos):
        """Cria a rede didática, o desenho e os controles de treino."""
        super().__init__(app, "mlp", "Laboratório MLP", (380, 420), (300, 300), pos)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.rede = NeuralNetwork()
        self.perdas = []
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._treino_task = None
        corpo = QVBoxLayout(self)
        corpo.setContentsMargins(10, 10, 10, 10)
        corpo.setSpacing(8)
        self.desenho = RedeWidget(self.rede)
        corpo.addWidget(self.desenho)
        self.rotulo = QLabel("Clique Treinar para ver a perda cair")
        self.rotulo.setStyleSheet(f"color: {tema.FRACO.name()}; font-size: 10px;")
        corpo.addWidget(self.rotulo)
        self.btn_treinar = QPushButton("Treinar 500 épocas")
        self.btn_treinar.setStyleSheet(tema.qss_pill())
        self.btn_treinar.clicked.connect(self.treinar)
        corpo.addWidget(self.btn_treinar)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)

    def treinar(self):
        """Executa o treino em worker e aplica o resultado somente na thread Qt."""
        if self._treino_task is not None:
            return
        pesos = {nome: getattr(self.rede, nome).copy()
                 for nome in ("W1", "W2", "W3", "b1", "b2", "b3")}
        task = _TreinoTask(pesos, threading.Event())
        task.signals.concluido.connect(self._treino_concluido)
        task.signals.falhou.connect(self._treino_falhou)
        task.signals.liberado.connect(self._treino_liberado)
        self._treino_task = task
        self.btn_treinar.setEnabled(False)
        self.rotulo.setText("Treinando em segundo plano…")
        self._pool.start(task)

    def _treino_concluido(self, resultado):
        """Copia pesos e ativações do worker para a UI após validar as dimensões."""
        shapes = {
            "W1": (6, 4), "W2": (4, 4), "W3": (4, 2),
            "b1": (4,), "b2": (4,), "b3": (2,),
        }
        pesos = resultado.get("pesos", {})
        for nome, shape in shapes.items():
            try:
                value = np.asarray(pesos.get(nome), dtype=float)
            except (TypeError, ValueError, OverflowError):
                self._treino_falhou(f"Parâmetro inválido: {nome}.")
                return
            if value.shape != shape or not np.isfinite(value).all():
                self._treino_falhou(f"Dimensão inválida no parâmetro {nome}.")
                return
        perdas = resultado.get("perdas", [])
        if not isinstance(perdas, list) or not perdas:
            self.rotulo.setText("Treino cancelado.")
            return
        ativacoes = resultado.get("ativacoes")
        expected_activations = ((6,), (4,), (4,), (2,))
        if not isinstance(ativacoes, list) or len(ativacoes) != len(expected_activations):
            self._treino_falhou("Ativações da rede inválidas.")
            return
        clean_activations = []
        for value, shape in zip(ativacoes, expected_activations):
            try:
                array = np.asarray(value, dtype=float)
            except (TypeError, ValueError, OverflowError):
                self._treino_falhou("Ativações da rede não numéricas.")
                return
            if array.shape != shape or not np.isfinite(array).all():
                self._treino_falhou("Dimensão inválida nas ativações da rede.")
                return
            clean_activations.append(array.copy())
        clean_losses = []
        for value in perdas:
            try:
                loss = float(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if np.isfinite(loss):
                clean_losses.append(loss)
        if not clean_losses:
            self.rotulo.setText("Treino cancelado.")
            return
        for nome in shapes:
            setattr(self.rede, nome, np.asarray(pesos[nome], dtype=float).copy())
        self.perdas.extend(clean_losses)
        self.perdas = self.perdas[-5000:]
        self.rede._ativ = clean_activations
        self.rotulo.setText(f"perda: {self.perdas[-1]:.6f}")
        self.desenho.update()
        self.update()

    def _treino_falhou(self, message):
        self.rotulo.setText(f"Treino indisponível: {message}")

    def _treino_liberado(self, _task):
        self._treino_task = None
        self.btn_treinar.setEnabled(True)

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start(500)

    def hideEvent(self, event):
        self._timer.stop()
        self.cancelar_treino()
        super().hideEvent(event)

    def cancelar_treino(self):
        """Pede ao worker para parar entre épocas sem bloquear a interface."""
        if self._treino_task is not None:
            self._treino_task.cancelar()

    def shutdown(self):
        """Para treino pendente e aguarda worker por um intervalo limitado."""
        self.cancelar_treino()
        self._pool.clear()
        self._pool.waitForDone(750)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def paintEvent(self, ev):
        """Desenha o painel e, embaixo, a curva de perda do treino."""
        super().paintEvent(ev)
        pts = []
        for value in self.perdas[-300:]:
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if np.isfinite(number):
                pts.append(number)
        if len(pts) < 2:
            return
        p = QPainter(self)
        w, h = self.width(), self.height()
        base = h - 60
        tema.cartao(p, QRectF(8, base - 58, w - 16, 58), raio=8)
        p.setPen(QPen(MUTED, 1))
        p.drawText(10, base - 4, "perda")
        mmax, mmin = max(pts), min(pts)
        span = max(1e-9, mmax - mmin)
        p.setPen(QPen(GOOD, 1.5))
        for i in range(1, len(pts)):
            x0 = 10 + (i - 1) * (w - 20) / max(1, len(pts) - 1)
            x1 = 10 + i * (w - 20) / max(1, len(pts) - 1)
            y0 = base - (pts[i - 1] - mmin) / span * 50
            y1 = base - (pts[i] - mmin) / span * 50
            p.drawLine(int(x0), int(y0), int(x1), int(y1))
        p.end()
