"""ENVELOPE DA FALA - a amplitude de um WAV ao longo do tempo, para a vibração do chat acompanhar a voz.

Lê um WAV PCM (8 ou 16 bits, qualquer número de canais), mistura os canais e devolve o volume médio de
cada janela curta, normalizado entre 0 e 1. Só lê os bytes que já estão na memória: nada é gravado."""

import io
import wave

import numpy as np

JANELAS_POR_S = 24          # uma amostra de volume a cada ~42 ms: suficiente para a onda parecer viva
MAX_BYTES = 32 * 1024 * 1024


def envelope_wav(dados, janelas_por_s=JANELAS_POR_S):
    """{"duracao": segundos, "valores": [0..1, ...]} ou None se não for um WAV PCM legível."""
    if not isinstance(dados, (bytes, bytearray)) or not 44 <= len(dados) <= MAX_BYTES:
        return None
    try:
        with wave.open(io.BytesIO(bytes(dados)), "rb") as arq:
            largura, canais, taxa, total = arq.getsampwidth(), arq.getnchannels(), arq.getframerate(), arq.getnframes()
            bruto = arq.readframes(total)
    except (wave.Error, EOFError, ValueError):
        return None
    if largura not in (1, 2) or canais < 1 or taxa <= 0 or total == 0:
        return None
    if largura == 1:
        amostras = (np.frombuffer(bruto, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        amostras = np.frombuffer(bruto, dtype="<i2").astype(np.float32) / 32768.0
    amostras = amostras[: len(amostras) - len(amostras) % canais].reshape(-1, canais).mean(axis=1)
    janela = max(1, int(taxa / janelas_por_s))
    quadros = len(amostras) // janela
    if quadros == 0:
        return None
    rms = np.sqrt((amostras[: quadros * janela].reshape(quadros, janela) ** 2).mean(axis=1))
    pico = float(rms.max())
    valores = (rms / pico if pico > 1e-6 else rms * 0.0).round(3).tolist()
    return {"duracao": round(total / taxa, 3), "valores": valores}
