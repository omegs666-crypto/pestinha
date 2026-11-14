"""Captura local do áudio que sai do PC (loopback) para alimentar o visualizador da ilha.

Só analisa o sinal: não grava nem guarda áudio em disco. A captura roda numa QThread
própria; a interface recebe apenas pequenos dicionários já calculados.
Se a saída de som mudar (fone, HDMI) ou o dispositivo falhar, a thread reconecta sozinha,
com espera crescente entre tentativas.
"""

import time
import warnings

import numpy as np
from PySide6.QtCore import QThread, Signal

TAXA = 48_000
QUADRO = 2_048
BANDAS = 24
PISO_DB = -70.0
TETO_DB = -20.0
SUBIDA, QUEDA = 0.55, 0.12          # o espectro sobe rápido e cai devagar (não treme)
QUEDA_PICO = 0.02                   # por quadro, o marcador de pico desce devagar
LIMIAR_SILENCIO = 0.002
SILENCIO_S = 1.5
ESPERA_MIN_S, ESPERA_MAX_S = 1.0, 10.0
CHECA_SAIDA_S = 2.0                 # de quanto em quanto tempo confere se a saída de som trocou


def analisar(mono, taxa=TAXA, bandas=BANDAS):
    """Converte um quadro mono em bandas de espectro (0–1), nível RMS e pico.

    Entradas inválidas (vazias, não finitas, dimensão errada) devolvem zeros: a ilha
    mostra um visualizador parado em vez de quebrar.
    """
    zero = {"bandas": [0.0] * bandas, "rms": 0.0, "pico": 0.0}
    try:
        x = np.asarray(mono, dtype=np.float32)
    except (TypeError, ValueError):
        return zero
    if x.ndim != 1 or x.size < 64 or not np.isfinite(x).all():
        return zero
    rms = float(np.sqrt(np.mean(x * x)))
    espectro = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freq = np.fft.rfftfreq(x.size, 1.0 / taxa)
    bordas = np.geomspace(40.0, min(16_000.0, taxa / 2), bandas + 1)
    indice = np.clip(np.digitize(freq, bordas), 0, bandas + 1)
    soma = np.bincount(indice, weights=espectro, minlength=bandas + 2)[1:bandas + 1]
    contagem = np.bincount(indice, minlength=bandas + 2)[1:bandas + 1]
    media = soma / np.maximum(contagem, 1)
    db = 20.0 * np.log10(media + 1e-9)
    niveis = np.clip((db - PISO_DB) / (TETO_DB - PISO_DB), 0.0, 1.0)
    return {
        "bandas": [round(float(v), 3) for v in niveis],
        "rms": round(min(rms, 1.0), 4),
        "pico": round(min(float(np.max(np.abs(x))), 1.0), 4),
    }


class Suavizador:
    """Dá inércia ao espectro: sobe rápido, cai devagar, segura o pico e detecta silêncio."""

    def __init__(self, bandas=BANDAS):
        self.bandas = [0.0] * bandas
        self.picos = [0.0] * bandas
        self._silencio_desde = None

    def aplicar(self, dados, agora):
        alvo = dados.get("bandas") or []
        if len(alvo) != len(self.bandas):
            return dados
        for i, v in enumerate(alvo):
            self.bandas[i] += (v - self.bandas[i]) * (SUBIDA if v > self.bandas[i] else QUEDA)
            self.picos[i] = max(self.bandas[i], self.picos[i] - QUEDA_PICO)
        if dados.get("rms", 0.0) < LIMIAR_SILENCIO:
            self._silencio_desde = agora if self._silencio_desde is None else self._silencio_desde
        else:
            self._silencio_desde = None
        silencio = self._silencio_desde is not None and agora - self._silencio_desde >= SILENCIO_S
        return {
            "bandas": [round(v, 3) for v in self.bandas],
            "picos": [round(v, 3) for v in self.picos],
            "rms": dados.get("rms", 0.0),
            "pico": dados.get("pico", 0.0),
            "silencio": silencio,
        }


class CapturaLoopback(QThread):
    """Lê o áudio de saída do sistema (WASAPI loopback no Windows) e emite análises suavizadas."""

    niveis = Signal(object)
    conectado = Signal()
    erro = Signal(str)

    def __init__(self, parent=None, taxa=TAXA, quadro=QUADRO, bandas=BANDAS):
        super().__init__(parent)
        self.taxa = taxa
        self.quadro = quadro
        self.bandas = bandas
        self._suavizador = Suavizador(bandas)

    def run(self):
        espera = ESPERA_MIN_S
        while not self.isInterruptionRequested():
            try:
                self._capturar()
                espera = ESPERA_MIN_S
            except Exception as error:  # sem dispositivo de saída, driver ausente ou biblioteca faltando
                self.erro.emit(f"Áudio do sistema indisponível: {str(error)[:160] or type(error).__name__}")
                espera = min(espera * 2, ESPERA_MAX_S)
            self._dormir(espera)

    def _capturar(self):
        """Captura enquanto a saída de som for a mesma; quando ela muda, volta e reconecta."""
        import soundcard as sc
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            nome = str(sc.default_speaker().name)
            microfone = sc.get_microphone(id=nome, include_loopback=True)
            with microfone.recorder(samplerate=self.taxa, channels=2, blocksize=self.quadro) as gravador:
                self.conectado.emit()
                ultimo_check = time.monotonic()
                while not self.isInterruptionRequested():
                    quadro = gravador.record(numframes=self.quadro)
                    agora = time.monotonic()
                    self.niveis.emit(self._suavizador.aplicar(
                        analisar(quadro.mean(axis=1), self.taxa, self.bandas), agora))
                    if agora - ultimo_check >= CHECA_SAIDA_S:
                        ultimo_check = agora
                        if str(sc.default_speaker().name) != nome:
                            return

    def _dormir(self, segundos):
        """Espera em pedaços curtos, para o fechamento não ficar preso na espera."""
        fim = time.monotonic() + segundos
        while not self.isInterruptionRequested() and time.monotonic() < fim:
            time.sleep(0.1)
