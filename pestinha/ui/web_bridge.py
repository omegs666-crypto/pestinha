"""Ponte entre a ilha em HTML (QWebChannel) e o backend Python.

A página só pode pedir ações de uma lista fixa; não há execução de código vindo da web.
Persistência: apenas os nomes LAYOUT/DIAGRAMA, como JSON validado, em memory/.
Chamadas de rede (Ollama) e áudio rodam em workers; a ponte só troca sinais leves.
"""

import json
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .. import log as log_module
from ..config import EMOTION_NAMES
from ..mind.chat_voice import ChatVoice
from ..mind.ollama_local import OllamaLocal
from ..sense.audio import CapturaLoopback

PERSISTIVEIS = {"layout", "diagrama"}
LIMITE_PERSISTENCIA = 200_000
ESTADO_MS = 500
PAINEIS = {"neural", "greve", "mlp"}


def _percentual(valor):
    """Número do backend como percentual 0–100; qualquer valor ruim vira 0."""
    try:
        return round(min(1.0, max(0.0, float(valor))) * 100)
    except (TypeError, ValueError):
        return 0


class Ponte(QObject):
    """Objeto registrado no QWebChannel como `ponte`."""

    estado = Signal(str)
    expansao = Signal(bool)
    niveis = Signal(str)
    audio_estado = Signal(str)
    modelos = Signal(str)
    token = Signal(str)
    chat_fim = Signal()
    erro = Signal(str)
    transcrito = Signal(str)
    voz_estado = Signal(str)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.offline = False
        self._ultimo_texto = ""
        self._ollama = OllamaLocal(self)
        self._voz = ChatVoice(self)
        self._captura = None
        self._timer = QTimer(self)
        self._timer.setInterval(ESTADO_MS)
        self._timer.timeout.connect(self._emitir_estado)
        self._ollama.models_ready.connect(lambda nomes: self.modelos.emit(json.dumps(list(nomes))))
        self._ollama.token.connect(self.token)
        self._ollama.chat_finished.connect(self.chat_fim)
        self._ollama.error.connect(self.erro)
        self._ollama.response_limited.connect(lambda: self.erro("Resposta longa demais: o texto foi limitado."))
        self._ollama.speech_ready.connect(self._voz.play_wav)
        self._ollama.speech_failed.connect(self._voz_do_sistema)
        self._voz.transcribed.connect(self.transcrito)
        self._voz.error.connect(self.erro)
        self._voz.activity_changed.connect(self.voz_estado)

    # ----- ciclo de vida -----
    def iniciar(self):
        self._timer.start()
        self._emitir_estado()

    def parar(self):
        self._timer.stop()

    def shutdown(self):
        """Encerra workers de rede, voz e áudio ao fechar a ilha."""
        self.parar()
        self.audio(False)
        self._ollama.shutdown()
        self._voz.shutdown()

    # ----- estado do backend (somente leitura) -----
    def snapshot(self):
        drives = getattr(self.app, "drives", None)
        estado = getattr(self.app, "pet_state", None)
        emocao = getattr(estado, "emotion", None)
        taxas = getattr(getattr(estado, "tone", None), "r", {})
        valores = taxas.values() if isinstance(taxas, dict) else (taxas if isinstance(taxas, (list, tuple)) else [])
        atividade = max((_percentual(v) for v in valores if isinstance(v, (int, float))), default=0)
        return {
            "pet": str(getattr(self.app, "nome", "Pestinha"))[:60],
            "emocao": str(EMOTION_NAMES.get(emocao, emocao))[:40],
            "energia": _percentual(getattr(drives, "energy", 0.0)),
            "estimulacao": _percentual(getattr(drives, "stimulation", 0.0)),
            "insatisfacao": _percentual(getattr(getattr(self.app, "protest", None), "grievance", 0.0)),
            "atividade": atividade,
            "pausado": bool(getattr(self.app, "paused", False)),
            "voz": bool(self.app.perms.get("voz")),
            "travessuras": bool(self.app.perms.get("travessuras")),
            "offline": self.offline,
            "logs": [str(linha)[:300] for linha in log_module.recent(40)],
        }

    def _emitir_estado(self):
        try:
            self.estado.emit(json.dumps(self.snapshot(), ensure_ascii=False))
        except Exception as error:  # dado corrompido no backend não derruba a ilha
            log_module.log(f"[ilha-web] estado indisponível: {error}")

    @Slot(result=str)
    def obter_estado(self):
        return json.dumps(self.snapshot(), ensure_ascii=False)

    # ----- ações permitidas -----
    @Slot(str, bool)
    def acao(self, nome, valor):
        """Executa uma ação da lista permitida; nomes desconhecidos são ignorados."""
        if nome == "pausa":
            self.app.toggle_pause()
        elif nome == "concentracion" and bool(self.app.paused) != bool(valor):
            self.app.toggle_pause()
        elif nome == "voz":
            self.app.apply_perms({"voz": not self.app.perms.get("voz")})
        elif nome == "travessuras":
            self.app.apply_perms({"travessuras": not self.app.perms.get("travessuras")})
        elif nome == "avion":
            self.offline = bool(valor)
            if self.offline:
                self._ollama.cancel_chat()
        self._emitir_estado()

    @Slot(bool)
    def expandir(self, aberto):
        """A página pede para abrir/recolher a ilha; a janela anima a própria geometria."""
        self.expansao.emit(bool(aberto))

    @Slot(str)
    def painel(self, chave):
        if chave in PAINEIS:
            self.app.floats.toggle(chave)

    # ----- persistência (layout da Parrilla e diagrama do Eslabón) -----
    def _arquivo(self, nome):
        return Path(self.app.paths.memory) / f"web_{nome}.json"

    @Slot(str, str)
    def salvar(self, nome, dados):
        if nome not in PERSISTIVEIS or not isinstance(dados, str) or len(dados) > LIMITE_PERSISTENCIA:
            return
        try:
            json.loads(dados)
            self._arquivo(nome).write_text(dados, encoding="utf-8")
        except (ValueError, OSError) as error:
            log_module.log(f"[ilha-web] não salvou {nome}: {error}")

    @Slot(str, result=str)
    def carregar(self, nome):
        if nome not in PERSISTIVEIS:
            return ""
        try:
            texto = self._arquivo(nome).read_text(encoding="utf-8")
            json.loads(texto)
            return texto
        except (OSError, ValueError):
            return ""

    # ----- chat local (Ollama) -----
    @Slot()
    def listar_modelos(self):
        self._ollama.list_models_async()

    @Slot(str, str)
    def enviar_chat(self, modelo, mensagens):
        if self.offline:
            self.erro.emit("Modo avião ativo: o chat local está desligado.")
            self.chat_fim.emit()
            return
        try:
            lista = json.loads(mensagens)
        except ValueError:
            self.erro.emit("Mensagem inválida.")
            self.chat_fim.emit()
            return
        self._ollama.chat_stream_async(modelo, lista if isinstance(lista, list) else [])

    @Slot()
    def cancelar_chat(self):
        self._ollama.cancel_chat()

    @Slot(str, str)
    def falar_resposta(self, modelo, texto):
        """Voz do próprio LLM (/v1/audio/speech); sem ela, cai na voz do sistema."""
        self._ultimo_texto = str(texto)[:2_000]
        if modelo:
            self._ollama.speak_async(modelo, self._ultimo_texto)
        else:
            self._voz.speak(self._ultimo_texto)

    def _voz_do_sistema(self, _mensagem):
        """Falha da voz do LLM: fala o último texto com a voz do sistema, sem travar o chat."""
        self.erro.emit("Voz do modelo indisponível; usando a voz do sistema.")
        if self._ultimo_texto:
            self._voz.speak(self._ultimo_texto)

    # ----- voz de entrada -----
    @Slot()
    def ouvir(self):
        self._voz.listen(seconds=12)

    # ----- áudio do sistema (loopback) -----
    @Slot(bool)
    def audio(self, ligado):
        if ligado and self._captura is None:
            self._captura = CapturaLoopback(self)
            self._captura.niveis.connect(lambda dados: self.niveis.emit(json.dumps(dados)))
            self._captura.erro.connect(self._audio_erro)
            self._captura.finished.connect(lambda: self.audio_estado.emit("parado"))
            self._captura.start()
            self.audio_estado.emit("ativo")
        elif not ligado and self._captura is not None:
            captura, self._captura = self._captura, None
            captura.requestInterruption()
            captura.wait(1500)
            self.audio_estado.emit("parado")

    def _audio_erro(self, mensagem):
        self.audio_estado.emit(mensagem)
        self._captura = None
