"""OUVIR - reconhecimento da sua voz no PC, do jeito do Coucou: Parakeet (NVIDIA) via sherpa-onnx.

- O modelo (~670 MB) só é baixado quando você clica em "Baixar" na ilha. Vem do Hugging Face numa
  revisão fixa, é conferido por SHA-256 e fica em %LOCALAPPDATA%\\Pestinha\\Models (fora do OneDrive).
- Depois disso tudo roda offline. O áudio do microfone fica só na memória: nada é gravado em disco.
- A gravação para sozinha depois de 1,2 s de silêncio (ou 12 s no máximo).
"""

import hashlib
import os
import sys
import threading
import warnings
from pathlib import Path

import numpy as np
import requests
from PySide6.QtCore import QThread, Signal

TAXA = 16_000
BLOCO = 1_600                       # 0,1 s
SILENCIO_FIM_S = 1.2
MAX_FALA_S = 12.0
ESPERA_FALA_S = 6.0                 # sem começar a falar nisso, desiste
LIMIAR_MIN = 0.012

REVISAO = "2bda32ec70b097a55adaa07d9a7173915b43cc78"
BASE = f"https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/resolve/{REVISAO}/"
ARQUIVOS = (
    ("encoder.int8.onnx", 652_184_281, "acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247"),
    ("decoder.int8.onnx", 11_845_275, "179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e"),
    ("joiner.int8.onnx", 6_355_277, "3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3"),
    ("tokens.txt", 93_939, "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d"),
)
TAMANHO_MB = sum(t for _, t, _ in ARQUIVOS) // 1_000_000


def pasta_modelo():
    """Onde o Parakeet fica: fora da pasta do projeto (que pode estar no OneDrive)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "Pestinha" / "Models" / "parakeet-tdt-0.6b-v3-int8"


def pronto(pasta=None):
    """Os quatro arquivos existem com o tamanho certo (o SHA-256 é conferido no download)."""
    pasta = pasta or pasta_modelo()
    return all((pasta / nome).is_file() and (pasta / nome).stat().st_size == tamanho for nome, tamanho, _ in ARQUIVOS)


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ---------------- detecção de fala (pura, testável) ----------------

def rms(bloco):
    x = np.asarray(bloco, dtype=np.float32)
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


class Recorte:
    """Decide, bloco a bloco, quando a fala começou e terminou (energia com limiar pelo ruído de fundo)."""

    def __init__(self, taxa=TAXA, bloco=BLOCO):
        self.dt = bloco / taxa
        self.ruido = None
        self.falando = False
        self.silencio = 0.0
        self.tempo = 0.0
        self.amostras = []

    def limiar(self):
        return max(LIMIAR_MIN, (self.ruido or 0.0) * 3.0)

    def passo(self, bloco):
        """Recebe 0,1 s de áudio; devolve 'continua', 'fim' (fala completa) ou 'nada' (ninguém falou)."""
        nivel = rms(bloco)
        self.tempo += self.dt
        if not self.falando:
            self.ruido = nivel if self.ruido is None else 0.9 * self.ruido + 0.1 * nivel
            if self.tempo > 0.3 and nivel > self.limiar():
                self.falando = True
                self.amostras.append(np.asarray(bloco, dtype=np.float32))
            elif self.tempo >= ESPERA_FALA_S:
                return "nada"
            return "continua"
        self.amostras.append(np.asarray(bloco, dtype=np.float32))
        self.silencio = self.silencio + self.dt if nivel <= self.limiar() else 0.0
        if self.silencio >= SILENCIO_FIM_S or self.tempo >= MAX_FALA_S + 0.3:
            return "fim"
        return "continua"

    def fala(self):
        return np.concatenate(self.amostras) if self.amostras else np.zeros(0, dtype=np.float32)


# ---------------- reconhecedor ----------------

_reconhecedor = None
_trava = threading.Lock()


def reconhecedor(pasta=None):
    """Carrega o Parakeet uma vez (alguns segundos) e reaproveita."""
    global _reconhecedor
    with _trava:
        if _reconhecedor is None:
            import sherpa_onnx
            pasta = pasta or pasta_modelo()
            _reconhecedor = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(pasta / "encoder.int8.onnx"), decoder=str(pasta / "decoder.int8.onnx"),
                joiner=str(pasta / "joiner.int8.onnx"), tokens=str(pasta / "tokens.txt"),
                num_threads=max(1, min(4, (os.cpu_count() or 2) // 2)), model_type="nemo_transducer",
                sample_rate=TAXA, feature_dim=80,
            )
        return _reconhecedor


def transcrever(amostras):
    """Texto do que foi dito (16 kHz mono, float32)."""
    if len(amostras) < TAXA // 4:
        return ""
    rec = reconhecedor()
    stream = rec.create_stream()
    stream.accept_waveform(TAXA, np.asarray(amostras, dtype=np.float32))
    rec.decode_stream(stream)
    return stream.result.text.strip()


# ---------------- threads (Qt) ----------------

class Ouvinte(QThread):
    """Grava do microfone até você parar de falar e transcreve; o áudio nunca vai para o disco."""

    estado = Signal(str)            # "ouvindo", "transcrevendo", "pronto"
    transcrito = Signal(str)
    erro = Signal(str)

    def run(self):
        try:
            import soundcard as sc
            recorte = Recorte()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                mic = sc.default_microphone()
                with mic.recorder(samplerate=TAXA, channels=1, blocksize=BLOCO) as gravador:
                    self.estado.emit("ouvindo")
                    while not self.isInterruptionRequested():
                        resultado = recorte.passo(gravador.record(numframes=BLOCO)[:, 0])
                        if resultado != "continua":
                            break
            # Parar no meio da fala ainda transcreve o que foi capturado;
            # parar antes de falar nada cancela em silêncio.
            if not recorte.falando:
                if not self.isInterruptionRequested():
                    self.erro.emit("Não ouvi nada. Fale perto do microfone e tente de novo.")
                return
            self.estado.emit("transcrevendo")
            texto = transcrever(recorte.fala())
            if texto:
                self.transcrito.emit(texto)
            else:
                self.erro.emit("Não entendi o que foi dito. Tente de novo.")
        except Exception as error:      # microfone ausente, driver, modelo corrompido
            self.erro.emit(f"Não consegui ouvir: {str(error)[:160] or type(error).__name__}")
        finally:
            self.estado.emit("pronto")


class Baixador(QThread):
    """Baixa o Parakeet com progresso, conferindo o SHA-256 de cada arquivo antes de usar."""

    progresso = Signal(int)         # 0..100
    concluido = Signal()
    erro = Signal(str)

    def __init__(self, parent=None, pasta=None):
        super().__init__(parent)
        self.pasta = pasta or pasta_modelo()

    def run(self):
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            total = sum(t for _, t, _ in ARQUIVOS)
            feito = 0
            sessao = requests.Session()
            sessao.trust_env = False
            for nome, tamanho, esperado in ARQUIVOS:
                destino = self.pasta / nome
                if destino.is_file() and destino.stat().st_size == tamanho and sha256(destino) == esperado:
                    feito += tamanho
                    continue
                parcial = destino.with_name(nome + ".part")
                with sessao.get(BASE + nome, stream=True, timeout=(10, 60)) as resposta:
                    resposta.raise_for_status()
                    with open(parcial, "wb") as f:
                        for bloco in resposta.iter_content(1 << 20):
                            if self.isInterruptionRequested():
                                return
                            f.write(bloco)
                            feito += len(bloco)
                            self.progresso.emit(min(99, int(feito * 100 / total)))
                if sha256(parcial) != esperado:
                    parcial.unlink(missing_ok=True)
                    raise RuntimeError(f"{nome} chegou corrompido (SHA-256 diferente). Tente de novo.")
                os.replace(parcial, destino)
            self.progresso.emit(100)
            self.concluido.emit()
        except Exception as error:
            self.erro.emit(f"Download do modelo de voz falhou: {str(error)[:200]}")
