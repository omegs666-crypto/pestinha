"""Captura local do áudio que sai do PC (loopback) para alimentar o visualizador da ilha.

Só analisa o sinal: não grava nem guarda áudio em disco. A captura roda numa QThread
própria; a interface recebe apenas pequenos dicionários já calculados.
"""

import warnings

import numpy as np
from PySide6.QtCore import QThread, Signal

TAXA = 48_000
QUADRO = 2_048
BANDAS = 24
PISO_DB = -70.0
TETO_DB = -20.0


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


class CapturaLoopback(QThread):
    """Lê o áudio de saída do sistema (WASAPI loopback no Windows) e emite análises."""

    niveis = Signal(object)
    erro = Signal(str)

    def __init__(self, parent=None, taxa=TAXA, quadro=QUADRO, bandas=BANDAS):
        super().__init__(parent)
        self.taxa = taxa
        self.quadro = quadro
        self.bandas = bandas

    def run(self):
        try:
            import soundcard as sc
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                alto_falante = sc.default_speaker()
                microfone = sc.get_microphone(id=str(alto_falante.name), include_loopback=True)
                with microfone.recorder(samplerate=self.taxa, channels=2, blocksize=self.quadro) as gravador:
                    while not self.isInterruptionRequested():
                        quadro = gravador.record(numframes=self.quadro)
                        self.niveis.emit(analisar(quadro.mean(axis=1), self.taxa, self.bandas))
        except Exception as error:  # sem dispositivo de saída, driver ausente ou biblioteca faltando
            self.erro.emit(f"Áudio do sistema indisponível: {str(error)[:160] or type(error).__name__}")
