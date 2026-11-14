"""Dynamic Island do Pestinha: janela frameless, compacta e dashboard interativo."""

from collections import deque
import json
import math
import time

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRect, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSlider, QTabWidget, QVBoxLayout, QWidget,
)

from ..body.desenho_rosto import draw_face
from ..body.pet import overlay_flags, set_no_activate
from ..config import EMOTION_NAMES
from ..core.emotion import EYE_SHAPES
from .. import log as log_module
from .. import plataforma
from ..mind.chat_voice import MAX_VOICE_TEXT, ChatVoice
from ..mind.ollama_local import OLLAMA_HOST, OllamaLocal
from ..world.arrastavel import load_positions, posicao_acessivel, save_position
from . import tema

PEQUENO = (268, 46)
ESPIA = (304, 54)
GRANDE_W = 960
GRANDE_H = 392
DELAY_RECOLHER_MS = 900
LIMIAR_ARRASTE = 5
ANIM_MS = 240
HOVER_OPEN_MS = 320
AMOSTRAS_MAX = 120
MAX_PROMPT_CHARS = 4_000
MAX_CONTEXT_CHARS = 8_000
MAX_CHAT_BLOCKS = 800

METRICAS = {
    "Energia": ("energia", tema.CYAN),
    "Insatisfação": ("insatisfacao", tema.BLUE),
    "Estimulação": ("estimulacao", tema.GREEN),
    "Atividade neural": ("atividade", tema.CYAN),
}


def _card(parent=None, radius=18):
    """Cria um card de superfície escura com o hairline sutil do Coucou."""
    frame = QFrame(parent)
    frame.setObjectName("islandCard")
    frame.setStyleSheet(
        f"QFrame#islandCard {{ background: {tema.CARD.name()};"
        f" border: 1px solid rgba(255,255,255,0.035); border-radius: {radius}px; }}"
    )
    return frame


def _label(text="", size=10, color=None):
    """Label de texto do tema Coucou."""
    label = QLabel(text)
    color = color or tema.INK
    label.setFont(tema.fonte(size, QFont.Medium))
    label.setStyleSheet(f"color: {color.name()}; background: transparent;")
    return label


def _button(text, primary=False):
    """Botão cápsula consistente com os botões do Coucou."""
    button = QPushButton(text)
    button.setCursor(Qt.PointingHandCursor)
    button.setFont(tema.fonte(10, QFont.Medium))
    button.setStyleSheet(tema.qss_botao(primary))
    return button


def _ratio(value):
    """Converte dado possivelmente ausente/inválido em valor finito entre zero e um."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, min(1.0, number)) if math.isfinite(number) else 0.0


class MiniPet(QWidget):
    """Retrato reduzido do pet na cápsula compacta."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setFixedSize(32, 32)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(16, 16)
        painter.scale(0.27, 0.27)
        emotion = self.app.pet_state.emotion
        if not isinstance(emotion, str):
            emotion = "observando"
        draw_face(
            painter,
            dict(EYE_SHAPES.get(emotion, EYE_SHAPES["observando"])),
            emotion=emotion,
            aparencia=self.app.pet.aparencia,
            boca=self.app.pet_state.boca,
        )


class TrendChart(QWidget):
    """Gráfico compacto sem dependência extra; pinta amostras recebidas da UI."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(260, 176)
        self._values = []
        self._color = QColor(34, 211, 238)
        self._headline = ""

    def set_series(self, values, color, headline):
        try:
            samples = list(values)[-AMOSTRAS_MAX:]
        except (TypeError, ValueError):
            samples = []
        self._values = [_ratio(value) for value in samples]
        self._color = QColor(color)
        self._headline = headline
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(18, 32, -12, -22)
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        for row in range(4):
            y = rect.top() + rect.height() * row / 3
            p.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))

        p.setFont(tema.fonte(9, QFont.Medium))
        p.setPen(tema.INK)
        p.drawText(16, 20, self._headline)
        p.setPen(tema.DIM_3)
        p.setFont(tema.fonte(8))
        p.drawText(16, self.height() - 6, "ÚLTIMOS 60 SEGUNDOS")

        if len(self._values) < 2:
            p.setPen(tema.DIM_3)
            p.drawText(rect, Qt.AlignCenter, "Coletando atividade")
            p.end()
            return
        points = []
        for index, value in enumerate(self._values):
            x = rect.left() + rect.width() * index / (len(self._values) - 1)
            y = rect.bottom() - rect.height() * max(0.0, min(1.0, value))
            points.append(QPoint(int(x), int(y)))
        pen = QPen(self._color, 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        for first, second in zip(points, points[1:]):
            p.drawLine(first, second)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(points[-1], 3, 3)


class ChatInput(QPlainTextEdit):
    """Editor de prompt; Ctrl+Enter envia sem roubar Enter para quebras de linha."""

    submitted = Signal()
    focus_requested = Signal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.focus_requested.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
            self.submitted.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class Ilha(QWidget):
    """Pílula frameless no topo que expande para controles, KPIs, gráfico e log."""

    def __init__(self, app):
        super().__init__(None, overlay_flags() | Qt.WindowDoesNotAcceptFocus)
        self.app = app
        self._foco_chat = False
        self._alterando_flags_foco = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        self._aberta = False
        self._fixada = False
        self._manual = False
        self._grab = None
        self._arrastou = False
        self._anim = None
        self._recolher_ate = None
        self._delay_s = DELAY_RECOLHER_MS / 1000
        self._ultimo_sample = 0.0
        self._series = {
            metric_key: deque(maxlen=AMOSTRAS_MAX)
            for metric_key, _color in METRICAS.values()
        }
        self._eventos = deque(maxlen=80)
        self._chat_messages = []
        self._chat_busy = False
        self._chat_had_error = False
        self._chat_cancelled = False
        self._assistant_buffer = ""
        self._models_loaded = False
        self._voice_listening = False
        self._models_cache = []
        self._speaking_text = ""
        self._tts_llm_ok = True
        self._ollama = OllamaLocal(self)
        self._ollama.models_ready.connect(self._modelos_recebidos)
        self._ollama.token.connect(self._receber_token)
        self._ollama.chat_finished.connect(self._chat_concluido)
        self._ollama.error.connect(self._ollama_erro)
        self._ollama.response_limited.connect(self._resposta_limitada)
        self._speech = ChatVoice(self)
        self._speech.transcribed.connect(self._texto_reconhecido)
        self._speech.error.connect(self._fala_erro)
        self._speech.activity_changed.connect(self._estado_voz)
        self._ollama.speech_ready.connect(self._speech.play_wav)
        self._ollama.speech_failed.connect(self._voz_llm_falhou)

        self._timer_recolher = QTimer(self)
        self._timer_recolher.setSingleShot(True)
        self._timer_recolher.timeout.connect(self.recolher)
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._atualizar_dados)
        self._timer_hover = QTimer(self)
        self._timer_hover.setSingleShot(True)
        self._timer_hover.setInterval(HOVER_OPEN_MS)
        self._timer_hover.timeout.connect(self.abrir)
        self._timer_barra = QTimer(self)
        self._timer_barra.setInterval(60)
        self._timer_barra.timeout.connect(self._atualizar_barra)

        self._montar_ui()
        saved = load_positions(self.app.paths.panels).get("ilha")
        self._manual = saved is not None
        self.resize(*PEQUENO)
        if self._manual:
            self.move(*posicao_acessivel(saved, self._topo(PEQUENO), PEQUENO))
        else:
            self._posicionar_topo(PEQUENO)
        self._registrar_evento("Interface pronta")

    def _montar_ui(self):
        self.setStyleSheet("background: transparent;")
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(12, 7, 12, 8)
        self._root.setSpacing(9)

        # Compact island: clean capsule, pet + name/status/time.
        self._compact = QWidget(self)
        self._compact.setMouseTracking(True)
        self._compact.installEventFilter(self)
        compact_layout = QHBoxLayout(self._compact)
        compact_layout.setContentsMargins(5, 0, 5, 0)
        compact_layout.setSpacing(9)
        compact_layout.addWidget(MiniPet(self.app))
        self._compact_name = _label(self.app.nome, 11, tema.INK)
        self._compact_name.setAttribute(Qt.WA_TransparentForMouseEvents)
        compact_layout.addWidget(self._compact_name)
        compact_layout.addStretch(1)
        self._compact_status = _label("ATIVO", 8, tema.DIM_3)
        self._compact_status.setAttribute(Qt.WA_TransparentForMouseEvents)
        compact_layout.addWidget(self._compact_status)
        self._compact_clock = _label("", 10, tema.DIM)
        self._compact_clock.setAttribute(Qt.WA_TransparentForMouseEvents)
        compact_layout.addWidget(self._compact_clock)
        self._root.addWidget(self._compact)

        # Expanded dashboard: cards in a clear three-column grid.
        self._dashboard = QWidget(self)
        dashboard_layout = QVBoxLayout(self._dashboard)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(10)
        dashboard_layout.addLayout(self._build_header())

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 0; background: transparent; }}"
            f"QTabBar::tab {{ color: {tema.DIM_3.name()}; background: transparent;"
            " border: 0; border-radius: 10px; padding: 5px 12px; margin-right: 3px;"
            " font-family: 'Segoe UI'; font-size: 10px; }"
            f"QTabBar::tab:selected {{ color: {tema.INK.name()}; background: #1d1f23; }}"
            f"QTabBar::tab:hover {{ color: {tema.INK_2.name()}; }}"
        )
        self._overview_page = self._build_overview_page()
        self._chat_page = self._build_chat_page()
        self._tabs.addTab(self._overview_page, "Visão geral")
        self._tabs.addTab(self._chat_page, "Chat local")
        self._tabs.currentChanged.connect(self._aba_alterada)
        self._tabs.tabBar().installEventFilter(self)
        dashboard_layout.addWidget(self._tabs, 1)

        self._root.addWidget(self._dashboard, 1)
        self._dashboard.hide()

        self._countdown = QWidget(self)
        self._countdown.setFixedHeight(2)
        self._countdown.hide()
        self._root.addWidget(self._countdown)

    def _build_overview_page(self):
        page = QWidget()
        columns = QHBoxLayout(page)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(9)
        self._controls_card = self._build_controls()
        self._chart_card = self._build_chart_card()
        self._log_card = self._build_log_card()
        columns.addWidget(self._controls_card, 25)
        columns.addWidget(self._chart_card, 43)
        columns.addWidget(self._log_card, 32)
        return page

    def _build_header(self):
        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 3, 0)
        self._title = _label(f"{self.app.nome}  /  CONTROLE", 11, tema.INK)
        header.addWidget(self._title)
        header.addStretch(1)
        self._live = _label("LOCAL  ·  AO VIVO", 8, tema.DIM_3)
        header.addWidget(self._live)
        self._pin_button = _button("Fixar")
        self._pin_button.setCheckable(True)
        self._pin_button.setStyleSheet(tema.qss_botao())
        self._pin_button.toggled.connect(self._fixar)
        header.addWidget(self._pin_button)
        self._close_button = _button("Fechar")
        self._close_button.clicked.connect(self.recolher)
        header.addWidget(self._close_button)
        return header

    def _build_chat_page(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 11, 13, 12)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.addWidget(_label("OLLAMA LOCAL", 8, tema.DIM_3))
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(210)
        self._model_combo.setFont(tema.fonte(9))
        self._model_combo.setStyleSheet(self._combo_qss())
        self._model_combo.currentTextChanged.connect(self._modelo_selecionado)
        toolbar.addWidget(self._model_combo)
        self._refresh_models = _button("Atualizar")
        self._refresh_models.clicked.connect(self._carregar_modelos)
        toolbar.addWidget(self._refresh_models)
        toolbar.addStretch(1)
        self._ollama_status = _label("Modelos locais apenas", 8, tema.DIM_3)
        self._ollama_status.setToolTip(f"Servidor permitido nesta integração: {OLLAMA_HOST}")
        toolbar.addWidget(self._ollama_status)
        layout.addLayout(toolbar)

        self._chat_view = QPlainTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_view.setUndoRedoEnabled(False)
        self._chat_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._chat_view.document().setMaximumBlockCount(MAX_CHAT_BLOCKS)
        self._chat_view.setFont(tema.fonte(9, mono=True))
        self._chat_view.setPlaceholderText(
            "A conversa é enviada somente ao Ollama local nesta máquina."
        )
        self._chat_view.setStyleSheet(
            f"QPlainTextEdit {{ background: {tema.CARD_FLAT.name()}; color: {tema.INK_2.name()};"
            f" border: 1px solid rgba(255,255,255,0.035); border-radius: 12px;"
            " padding: 9px; selection-background-color: #282a30; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #4b4d53; border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        layout.addWidget(self._chat_view, 1)

        composer = QHBoxLayout()
        composer.setSpacing(8)
        self._context_button = _button("Analisar resultados")
        self._context_button.setToolTip(
            "Anexa métricas e os registros recentes do Pestinha ao prompt local."
        )
        self._context_button.clicked.connect(self._analisar_contexto)
        composer.addWidget(self._context_button)
        self._mic_button = _button("Falar")
        self._mic_button.setToolTip(
            "Transcreve em português com reconhecimento local do Windows; requer pacote pt-BR."
        )
        self._mic_button.setEnabled(plataforma.NOME_DO_SISTEMA == "Windows")
        self._mic_button.clicked.connect(self._alternar_microfone)
        composer.addWidget(self._mic_button)
        self._voice_reply_button = _button("Ler respostas: não")
        self._voice_reply_button.setCheckable(True)
        self._voice_reply_button.toggled.connect(self._alternar_resposta_falada)
        composer.addWidget(self._voice_reply_button)
        self._chat_input = ChatInput()
        self._chat_input.setFixedHeight(52)
        self._chat_input.setFont(tema.fonte(10))
        self._chat_input.setPlaceholderText("Pergunte ao modelo local… (Ctrl+Enter envia)")
        self._chat_input.setStyleSheet(
            f"QPlainTextEdit {{ background: {tema.CARD_FLAT.name()}; color: {tema.INK.name()};"
            " border: 1px solid rgba(255,255,255,0.10); border-radius: 12px;"
            " padding: 8px; selection-background-color: #282a30; }"
        )
        self._chat_input.submitted.connect(self._enviar_chat)
        self._chat_input.focus_requested.connect(self._solicitar_foco_chat)
        composer.addWidget(self._chat_input, 1)
        self._cancel_chat_button = _button("Parar")
        self._cancel_chat_button.setToolTip("Interrompe o stream do modelo local.")
        self._cancel_chat_button.clicked.connect(self._cancelar_chat)
        self._cancel_chat_button.hide()
        composer.addWidget(self._cancel_chat_button)
        self._send_button = _button("Enviar", primary=True)
        self._send_button.clicked.connect(lambda: self._enviar_chat())   # clicked passa `checked`; não é o prompt
        composer.addWidget(self._send_button)
        layout.addLayout(composer)
        return card

    def _aba_alterada(self, index):
        if self._tabs.tabText(index) == "Chat local":
            self._solicitar_foco_chat()
            self._carregar_modelos()

    def _solicitar_foco_chat(self):
        """Ativa foco nativo após intenção explícita de digitar no chat."""
        self._definir_foco_chat(True)
        QTimer.singleShot(0, self._chat_input.setFocus)

    def _definir_foco_chat(self, habilitar):
        """Alterna foco de teclado só enquanto a aba de conversa está ativa."""
        habilitar = bool(habilitar)
        if self._foco_chat == habilitar:
            return
        geometry = self.geometry()
        visible = self.isVisible()
        self._foco_chat = habilitar
        self._alterando_flags_foco = True
        try:
            self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, not habilitar)
            self.setGeometry(geometry)
            if visible:
                self.show()
        finally:
            self._alterando_flags_foco = False
        if visible:
            if habilitar:
                plataforma.com_foco_nativo(int(self.winId()))
                self.activateWindow()
            else:
                set_no_activate(self)

    def _set_ollama_status(self, text, color):
        self._ollama_status.setText(text)
        self._ollama_status.setStyleSheet(
            f"color: {color.name()}; background: transparent;"
        )

    def _carregar_modelos(self):
        self._set_ollama_status("Conectando ao serviço local…", tema.DIM)
        self._refresh_models.setEnabled(False)
        self._ollama.list_models_async()

    def _modelos_recebidos(self, names):
        self._models_loaded = True
        self._models_cache = list(names)
        self._tts_llm_ok = True
        saved = self.app.perms.get("ollama_chat_modelo", "")
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(names)
        if saved in names:
            self._model_combo.setCurrentText(saved)
        elif names:
            self._model_combo.setCurrentIndex(0)
        self._model_combo.blockSignals(False)
        self._model_combo.setEnabled(bool(names))
        self._send_button.setEnabled(bool(names) and not self._chat_busy)
        self._context_button.setEnabled(bool(names) and not self._chat_busy)
        self._refresh_models.setEnabled(True)
        if names:
            self._set_ollama_status(f"Conectado · {len(names)} modelos locais", tema.GREEN)
            self._modelo_selecionado(self._model_combo.currentText())
        else:
            self._set_ollama_status("Conectado · nenhum modelo instalado", tema.AMBER)

    def _modelo_selecionado(self, name):
        if name and name != self.app.perms.get("ollama_chat_modelo"):
            self.app.store.update({"ollama_chat_modelo": name})

    def _alternar_microfone(self):
        """Inicia ou cancela a captura local; a fala reconhecida envia o prompt."""
        if self._voice_listening:
            self._speech.cancel()
            self._set_ollama_status("Cancelando captura de voz…", tema.AMBER)
            return
        if self._chat_busy:
            self._set_ollama_status("Aguarde a resposta atual antes de falar.", tema.AMBER)
            return
        self._speech.listen(seconds=12)

    def _alternar_resposta_falada(self, enabled):
        """Ativa ou desativa a leitura local das respostas completas do assistente."""
        self._voice_reply_button.setText(
            "Ler respostas: sim" if enabled else "Ler respostas: não"
        )
        self._voice_reply_button.setProperty("ativo", enabled)
        self._voice_reply_button.style().unpolish(self._voice_reply_button)
        self._voice_reply_button.style().polish(self._voice_reply_button)

    def _estado_voz(self, state):
        self._voice_listening = state == "ouvindo"
        self._mic_button.setText("Parar de ouvir" if self._voice_listening else "Falar")
        if state == "ouvindo":
            self._set_ollama_status("Ouvindo pelo microfone local…", tema.CYAN)
        elif state == "falando":
            self._set_ollama_status("Falando resposta local…", tema.CYAN)
        elif (
            not self._chat_busy
            and self._model_combo.currentText()
            and self._ollama_status.text().startswith(
                ("Ouvindo", "Falando", "Cancelando captura")
            )
        ):
            self._set_ollama_status(
                f"Conectado · {self._model_combo.currentText()}", tema.GREEN
            )

    def _texto_reconhecido(self, text):
        """Coloca a transcrição no campo e envia a pergunta ao modelo selecionado."""
        text = str(text).strip()[:MAX_PROMPT_CHARS]
        if not text:
            return
        self._chat_input.setPlainText(text)
        self._registrar_evento("Entrada de voz transcrita localmente")
        self._enviar_chat(prompt=text, display_text=f"VOZ\n{text}")

    def _fala_erro(self, message):
        """Apresenta falhas de reconhecimento ou síntese sem derrubar o chat."""
        self._voice_listening = False
        self._mic_button.setText("Falar")
        self._set_ollama_status(message, tema.RED)
        self._append_chat_line("VOZ LOCAL", message)
        self._registrar_evento(message)

    def _modelo_voz(self):
        """Prefere um modelo com nome de TTS/voz; sem ele, usa o modelo do chat."""
        for name in self._models_cache:
            folded = name.casefold()
            if any(tag in folded for tag in (
                "tts", "kokoro", "piper", "f5-", "chattts", "speech",
            )):
                return name
        return self._model_combo.currentText().strip()

    def _falar_resposta(self, texto):
        """Fala com a voz do próprio LLM local; cai na voz do sistema se falhar."""
        model = self._modelo_voz() if self._tts_llm_ok else ""
        if not model:
            self._speech.speak(texto)
            return
        self._speaking_text = texto
        self._ollama.speak_async(model, texto)

    def _voz_llm_falhou(self, message):
        """Registra a indisponibilidade do TTS do LLM e usa a voz do sistema."""
        self._tts_llm_ok = False
        texto = self._speaking_text
        self._speaking_text = ""
        self._registrar_evento(
            f"Voz do LLM indisponível; usando voz do sistema ({message})"
        )
        if texto:
            self._speech.speak(texto)

    def _contexto_projeto(self):
        """Snapshot explicitamente solicitado pelo usuário, limitado e local."""
        data = self._snapshot()
        try:
            stage = int(getattr(self.app.protest, "stage", 0))
        except (TypeError, ValueError, OverflowError):
            stage = 0
        return {
            "pet": str(getattr(self.app, "nome", "Pestinha"))[:80],
            "emocao": str(getattr(self.app.pet_state, "emotion", "desconhecida"))[:80],
            "atividade": str(getattr(self.app, "activity", "desconhecida"))[:80],
            "energia": round(data["energia"], 3),
            "insatisfacao": round(data["insatisfacao"], 3),
            "estimulacao": round(data["estimulacao"], 3),
            "atividade_neural": round(data["atividade"], 3),
            "estagio_protesto": max(0, min(10_000, stage)),
            "logs_recentes": [str(line)[:500] for line in log_module.recent(12)],
        }

    def _analisar_contexto(self):
        context = json.dumps(self._contexto_projeto(), ensure_ascii=False)
        self._enviar_chat(
            "Analise os dados locais atuais deste projeto. Dê um diagnóstico breve, "
            "aponte anomalias relevantes e sugira uma próxima verificação.",
            context=context,
            display_text="Analise os resultados atuais. [métricas e logs locais anexados]",
        )

    def _enviar_chat(self, prompt=None, *, context=None, display_text=None):
        if self._chat_busy:
            return
        prompt = (self._chat_input.toPlainText() if prompt is None else prompt).strip()
        prompt = prompt[:MAX_PROMPT_CHARS]
        model = self._model_combo.currentText().strip()
        if not prompt or not model:
            if not model:
                self._set_ollama_status("Selecione um modelo local instalado.", tema.AMBER)
            return
        if context:
            context = str(context)[:MAX_CONTEXT_CHARS]
            prompt = f"{prompt}\n\nDados locais do projeto (JSON):\n{context}"
        visible_prompt = display_text or prompt
        self._chat_input.clear()
        self._chat_busy = True
        self._chat_had_error = False
        self._chat_cancelled = False
        self._send_button.setEnabled(False)
        self._context_button.setEnabled(False)
        self._cancel_chat_button.setEnabled(True)
        self._cancel_chat_button.show()
        self._send_button.setText("Gerando")
        self._append_chat_line("USUÁRIO", visible_prompt)
        self._chat_view.appendPlainText("\nASSISTENTE")
        cursor = self._chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._chat_view.setTextCursor(cursor)
        self._assistant_buffer = ""
        self._chat_messages.append({"role": "user", "content": prompt})
        history = [
            {
                "role": "system",
                "content": (
                    "Você é o assistente técnico deste dashboard. Responda em português, "
                    "com clareza e concisão. Os dados enviados pelo usuário são locais; "
                    "analise apenas o contexto fornecido e não invente observações."
                ),
            },
            *self._chat_messages[-20:],
        ]
        self._set_ollama_status(f"Gerando · {model}", tema.CYAN)
        self._ollama.chat_stream_async(model, history)

    def _append_chat_line(self, role, text):
        self._chat_view.appendPlainText(f"\n{role}\n{text}")
        bar = self._chat_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _receber_token(self, token):
        """Acumula fragmentos de saída com limite e atualiza o histórico da conversa."""
        restante = 16_000 - len(self._assistant_buffer)
        if restante <= 0:
            return
        token = str(token)[:restante]
        self._assistant_buffer += token
        cursor = self._chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(token)
        self._chat_view.setTextCursor(cursor)
        self._chat_view.ensureCursorVisible()

    def _chat_concluido(self):
        """Libera os controles e mantém no histórico apenas o contexto recente."""
        self._chat_busy = False
        self._cancel_chat_button.hide()
        self._send_button.setText("Enviar")
        if self._assistant_buffer:
            self._chat_messages.append(
                {"role": "assistant", "content": self._assistant_buffer[:16_000]}
            )
        self._chat_messages = self._chat_messages[-20:]
        self._send_button.setEnabled(bool(self._model_combo.currentText()))
        self._context_button.setEnabled(bool(self._model_combo.currentText()))
        if "desconectado" not in self._ollama_status.text().lower():
            self._set_ollama_status(
                f"Conectado · {self._model_combo.currentText()}", tema.GREEN
            )
        self._chat_view.appendPlainText("")
        if (
            self._assistant_buffer
            and self._voice_reply_button.isChecked()
            and not self._chat_had_error
            and not self._chat_cancelled
        ):
            self._falar_resposta(self._assistant_buffer[:MAX_VOICE_TEXT])

    def _ollama_erro(self, message):
        if self._chat_busy:
            self._chat_had_error = True
        self._set_ollama_status(message, tema.RED)
        self._refresh_models.setEnabled(True)
        if self._chat_busy:
            self._append_chat_line("SISTEMA", message)
        self._registrar_evento(message)

    def _resposta_limitada(self):
        self._append_chat_line(
            "SISTEMA", "Resposta limitada a 16.000 caracteres para proteger a memória."
        )
        self._set_ollama_status("Resposta limitada", tema.AMBER)
        self._registrar_evento("Resposta do modelo limitada")

    def _cancelar_chat(self):
        """Solicita cancelamento do stream sem bloquear a thread da interface."""
        if not self._chat_busy:
            return
        self._chat_cancelled = True
        self._cancel_chat_button.setEnabled(False)
        self._set_ollama_status("Cancelando resposta…", tema.AMBER)
        self._ollama.cancel_chat()

    def _build_controls(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(9)
        layout.addWidget(_label("CONTROLES", 8, tema.DIM_3))
        self._pause_button = _button("Pausar")
        self._pause_button.clicked.connect(self._alternar_pausa)
        layout.addWidget(self._pause_button)
        self._voice_button = _button("Voz: desligada")
        self._voice_button.clicked.connect(self._alternar_voz)
        layout.addWidget(self._voice_button)
        self._mischief_button = _button("Travessuras: desligadas")
        self._mischief_button.clicked.connect(self._alternar_travessuras)
        layout.addWidget(self._mischief_button)

        layout.addSpacing(3)
        layout.addWidget(_label("RECOLHER APÓS SAIR", 8, tema.DIM_3))
        delay_row = QHBoxLayout()
        self._delay_slider = QSlider(Qt.Horizontal)
        self._delay_slider.setRange(1, 10)
        self._delay_slider.setValue(round(self._delay_s))
        self._delay_slider.setStyleSheet(self._slider_qss())
        self._delay_slider.valueChanged.connect(self._mudar_delay)
        delay_row.addWidget(self._delay_slider, 1)
        self._delay_label = _label(f"{round(self._delay_s)} s", 9, tema.DIM)
        delay_row.addWidget(self._delay_label)
        layout.addLayout(delay_row)

        layout.addSpacing(3)
        layout.addWidget(_label("MÉTRICA DO GRÁFICO", 8, tema.DIM_3))
        self._metric = QComboBox()
        self._metric.addItems(METRICAS)
        self._metric.setFont(tema.fonte(9))
        self._metric.setStyleSheet(self._combo_qss())
        self._metric.currentTextChanged.connect(self._render_grafico)
        layout.addWidget(self._metric)

        layout.addSpacing(3)
        layout.addWidget(_label("ATALHOS DE PAINEL", 8, tema.DIM_3))
        self._open_neural = _button("Monitor neural")
        self._open_neural.clicked.connect(lambda: self._abrir_painel("neural"))
        layout.addWidget(self._open_neural)
        self._open_strike = _button("Painel de protesto")
        self._open_strike.clicked.connect(lambda: self._abrir_painel("greve"))
        layout.addWidget(self._open_strike)
        layout.addStretch(1)
        return card

    def _build_chart_card(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 13, 14, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.addWidget(_label("ATIVIDADE", 8, tema.DIM_3))
        header.addStretch(1)
        layout.addLayout(header)
        self._chart_value = _label("--", 22, tema.INK)
        layout.addWidget(self._chart_value)
        self._chart = TrendChart()
        layout.addWidget(self._chart, 1)
        return card

    def _build_log_card(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 13, 14, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.addWidget(_label("EVENTOS", 8, tema.DIM_3))
        header.addStretch(1)
        self._clear_log = _button("Limpar")
        self._clear_log.clicked.connect(self._limpar_eventos)
        header.addWidget(self._clear_log)
        layout.addLayout(header)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setUndoRedoEnabled(False)
        self._log_view.setFont(tema.fonte(9, mono=True))
        self._log_view.setStyleSheet(
            f"QPlainTextEdit {{ background: {tema.CARD_FLAT.name()}; color: {tema.DIM.name()};"
            f" border: 1px solid rgba(255,255,255,0.035); border-radius: 11px;"
            " padding: 8px; selection-background-color: #282a30; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #4b4d53; border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        layout.addWidget(self._log_view, 1)
        return card

    @staticmethod
    def _slider_qss():
        return (
            f"QSlider::groove:horizontal {{ height: 3px; background: #34363b; border-radius: 2px; }}"
            f"QSlider::sub-page:horizontal {{ background: {tema.CYAN.name()}; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; border-radius: 6px;"
            f" background: {tema.INK.name()}; }}"
        )

    @staticmethod
    def _combo_qss():
        return (
            f"QComboBox {{ color: {tema.DIM.name()}; background: {tema.CARD_FLAT.name()};"
            " border: 1px solid rgba(255,255,255,0.10); border-radius: 10px;"
            " padding: 4px 9px; }"
            f"QComboBox QAbstractItemView {{ color: {tema.INK.name()};"
            f" background: {tema.CARD.name()}; selection-background-color: #282a30; }}"
        )

    def _registrar_evento(self, text):
        stamp = time.strftime("%H:%M:%S")
        self._eventos.append(f"{stamp}  {text}")
        self._render_eventos()

    def _render_eventos(self):
        if not hasattr(self, "_log_view"):
            return
        lines = log_module.recent(40) + list(self._eventos)
        text = "\n".join(lines[-60:])
        if self._log_view.toPlainText() == text:
            return
        self._log_view.setPlainText(text)
        self._log_view.verticalScrollBar().setValue(
            self._log_view.verticalScrollBar().maximum()
        )

    def _limpar_eventos(self):
        self._eventos.clear()
        self._log_view.clear()

    def _alternar_pausa(self):
        self.app.toggle_pause()
        self._registrar_evento("Sessão pausada" if self.app.paused else "Sessão retomada")
        self._atualizar_dados()

    def _alternar_voz(self):
        ligada = not self.app.perms.get("voz", False)
        self.app.apply_perms({"voz": ligada})
        self._registrar_evento(f"Voz {'ativada' if ligada else 'desativada'}")
        self._atualizar_dados()

    def _alternar_travessuras(self):
        ligada = not self.app.perms.get("travessuras", False)
        self.app.apply_perms({"travessuras": ligada})
        self._registrar_evento(f"Travessuras {'ativadas' if ligada else 'desativadas'}")
        self._atualizar_dados()

    def _abrir_painel(self, key):
        self.app.floats.toggle(key)
        self._registrar_evento(f"Painel {key} alternado")
        self._atualizar_dados()

    def _mudar_delay(self, value):
        self._delay_s = float(value)
        self._delay_label.setText(f"{value} s")
        if self._recolher_ate is not None:
            self._agendar_recolher()

    def _snapshot(self):
        drives = getattr(self.app, "drives", None)
        state = getattr(self.app, "pet_state", None)
        tone = getattr(state, "tone", None)
        rates = getattr(tone, "r", {})
        if isinstance(rates, dict):
            rate_values = rates.values()
        elif isinstance(rates, (list, tuple)) and all(
            not isinstance(item, (list, tuple, dict)) for item in rates
        ):
            rate_values = rates
        elif getattr(rates, "ndim", None) == 1:
            try:
                rate_values = rates.tolist()
            except (AttributeError, TypeError, ValueError):
                rate_values = ()
        else:
            rate_values = ()
        return {
            "energia": _ratio(getattr(drives, "energy", 0.0)),
            "insatisfacao": _ratio(
                getattr(getattr(self.app, "protest", None), "grievance", 0.0)
            ),
            "estimulacao": _ratio(getattr(drives, "stimulation", 0.0)),
            "atividade": max((_ratio(value) for value in rate_values), default=0.0),
        }

    def _atualizar_dados(self):
        """Lê um snapshot pequeno do backend; sem I/O ou cálculo pesado na UI."""
        now = time.monotonic()
        if now - self._ultimo_sample >= 0.5:
            data = self._snapshot()
            for key, value in data.items():
                self._series[key].append(value)
            self._ultimo_sample = now

        emotion = getattr(getattr(self.app, "pet_state", None), "emotion", None)
        try:
            name = EMOTION_NAMES.get(emotion, str(emotion))
        except TypeError:
            name = "DESCONHECIDA"
        self._compact_name.setText(self.app.nome)
        self._compact_clock.setText(time.strftime("%H:%M"))
        if self.app.paused:
            status, color = "PAUSADO", tema.AMBER
        elif not self.app.perms.get("ativo", False):
            status, color = "INATIVO", tema.RED
        else:
            status, color = name.upper(), tema.DIM_3
        self._compact_status.setText(status)
        self._compact_status.setStyleSheet(
            f"color: {color.name()}; background: transparent;"
        )
        self._compact_status.setFont(tema.fonte(8, QFont.DemiBold))
        if self._aberta:
            self._pause_button.setText("Retomar" if self.app.paused else "Pausar")
            self._voice_button.setText(
                "Voz: ligada" if self.app.perms.get("voz") else "Voz: desligada"
            )
            self._mischief_button.setText(
                "Travessuras: ligadas" if self.app.perms.get("travessuras")
                else "Travessuras: desligadas"
            )
            self._render_grafico(self._metric.currentText())
            self._render_eventos()

    def _render_grafico(self, metric):
        key, color = METRICAS.get(metric, METRICAS["Energia"])
        values = list(self._series[key])
        current = values[-1] if values else 0.0
        self._chart_value.setText(f"{current:.0%}")
        self._chart_value.setStyleSheet(
            f"color: {color.name()}; background: transparent;"
        )
        self._chart_value.setFont(tema.fonte(22, QFont.DemiBold))
        self._chart.set_series(values, color, metric)

    def _topo(self, size):
        left, top, right, _bottom = self.app.bounds()
        return int(left + (right - left - size[0]) / 2), top

    def _posicionar_topo(self, size):
        if not self._manual:
            self.move(*self._topo(size))

    def _alvo(self, size):
        default = self._topo(size)
        if self._manual:
            x, y = posicao_acessivel((self.x(), self.y()), default, size)
            return QRect(x, y, size[0], size[1])
        return QRect(default[0], default[1], size[0], size[1])

    def _animar_para(self, size):
        if self._anim is not None:
            self._anim.stop()
        left, top, right, bottom = self.app.bounds()
        size = (min(size[0], max(PEQUENO[0], right - left - 16)),
                min(size[1], max(PEQUENO[1], bottom - top - 12)))
        target = self._alvo(size)
        if self.geometry() == target:
            self._anim = None
            self._animacao_concluida()
            return
        animation = QPropertyAnimation(self, b"geometry", self)
        animation.setDuration(ANIM_MS)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.setStartValue(self.geometry())
        animation.setEndValue(target)
        animation.finished.connect(self._animacao_concluida)
        self._anim = animation
        animation.start()

    def _animacao_concluida(self):
        self._anim = None
        if not self._aberta and self._foco_chat:
            self._definir_foco_chat(False)

    def abrir(self):
        if self._aberta:
            return
        self._timer_recolher.stop()
        self._aberta = True
        self._dashboard.show()
        self._animar_para((GRANDE_W, GRANDE_H))
        self._registrar_evento("Dashboard aberto")
        self._atualizar_dados()

    def recolher(self):
        if not self._aberta:
            return
        self._timer_recolher.stop()
        self._timer_barra.stop()
        self._recolher_ate = None
        self._countdown.hide()
        self._aberta = False
        self._dashboard.hide()
        self._animar_para(PEQUENO)

    def toggle(self):
        self.recolher() if self._aberta else self.abrir()

    def _fixar(self, pinned):
        self._fixada = pinned
        if not pinned and self._aberta:
            self._agendar_recolher()

    def _agendar_recolher(self):
        self._recolher_ate = time.monotonic() + self._delay_s
        self._timer_recolher.start(round(self._delay_s * 1000))
        self._countdown.show()
        self._timer_barra.start()

    def _atualizar_barra(self):
        if self._recolher_ate is None:
            self._timer_barra.stop()
            self._countdown.hide()
            return
        fraction = max(0.0, (self._recolher_ate - time.monotonic()) / self._delay_s)
        self._countdown.setStyleSheet(
            f"background: rgba(255,255,255,{int(90 * fraction)});"
            " border-radius: 1px;"
        )

    def eventFilter(self, watched, event):
        if (
            hasattr(self, "_tabs")
            and watched is self._tabs.tabBar()
            and event.type() == QEvent.MouseButtonRelease
            and event.button() == Qt.LeftButton
        ):
            index = watched.tabAt(event.position().toPoint())
            if index == self._tabs.indexOf(self._chat_page):
                self._solicitar_foco_chat()
            return super().eventFilter(watched, event)
        if watched is self._compact:
            if event.type() == QEvent.Enter:
                self._timer_recolher.stop()
                if not self._aberta:
                    self._animar_para(ESPIA)
                    self._timer_hover.start()
            elif event.type() == QEvent.Leave:
                if self.geometry().contains(QCursor.pos()):
                    return super().eventFilter(watched, event)
                self._timer_hover.stop()
                if self._aberta:
                    if not self._fixada:
                        self._agendar_recolher()
                else:
                    self._animar_para(PEQUENO)
            elif event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.mousePressEvent(event)
                return True
            elif event.type() == QEvent.MouseMove and self._grab is not None:
                self.mouseMoveEvent(event)
                return True
            elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if self._grab is not None and self._arrastou:
                    self.mouseReleaseEvent(event)
                else:
                    self._grab = None
                    self._arrastou = False
                    self.toggle()
                return True
        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        self._timer_recolher.stop()
        self._timer_barra.stop()
        self._recolher_ate = None
        self._countdown.hide()
        if not self._aberta:
            self._animar_para(ESPIA)
            self._timer_hover.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.geometry().contains(QCursor.pos()):
            super().leaveEvent(event)
            return
        self._timer_hover.stop()
        if self._aberta and not self._fixada:
            self._agendar_recolher()
        elif not self._aberta:
            self._animar_para(PEQUENO)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._grab = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._arrastou = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._grab is not None:
            target = event.globalPosition().toPoint() - self._grab
            if not self._arrastou and (target - self.pos()).manhattanLength() > LIMIAR_ARRASTE:
                self._arrastou = True
                self._manual = True
            if self._arrastou:
                if self._anim is not None:
                    self._anim.stop()
                    self._anim = None
                self.move(target)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._grab is not None:
            if self._arrastou:
                save_position(self.app.paths.panels, "ilha", self.x(), self.y())
            self._grab = None
            self._arrastou = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        radius = 16 if self._aberta else 23
        path.addRoundedRect(self.rect(), radius, radius)
        painter.fillPath(path, tema.BG)

    def showEvent(self, event):
        super().showEvent(event)
        if self._foco_chat:
            plataforma.com_foco_nativo(int(self.winId()))
        else:
            set_no_activate(self)
        self._timer.start()

    def hideEvent(self, event):
        if self._alterando_flags_foco:
            super().hideEvent(event)
            return
        if self._foco_chat:
            self._definir_foco_chat(False)
        self._timer.stop()
        self._timer_recolher.stop()
        self._timer_hover.stop()
        self._timer_barra.stop()
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        self._ollama.cancel_chat()
        self._speech.cancel()
        super().hideEvent(event)

    def anunciar(self, texto, tom="calmo", origem="pet"):
        """A ilha nativa não tem balões: a fala do pet fica só na voz (quando ligada)."""

    def shutdown(self):
        """Interrompe chamadas locais e aguarda workers por no máximo 750 ms."""
        self._ollama.shutdown()
        self._speech.shutdown()

    def closeEvent(self, event):
        """Fecha a ilha sem deixar uma geração local continuar em segundo plano."""
        self.shutdown()
        super().closeEvent(event)
