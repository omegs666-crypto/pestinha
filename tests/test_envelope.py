"""Envelope da fala: volume ao longo do tempo a partir de um WAV em memória."""
import io
import wave

import numpy as np

from pestinha.sense.envelope import envelope_wav


def _wav(amostras, taxa=8000, canais=1, largura=2):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as arq:
        arq.setnchannels(canais)
        arq.setsampwidth(largura)
        arq.setframerate(taxa)
        if largura == 2:
            arq.writeframes(np.asarray(amostras, dtype="<i2").tobytes())
        else:
            arq.writeframes(np.asarray(amostras, dtype=np.uint8).tobytes())
    return buf.getvalue()


def test_envelope_acompanha_a_forma_do_volume():
    silencio = np.zeros(4000, dtype=np.int16)
    alto = (np.sin(np.arange(4000) * 0.5) * 20000).astype(np.int16)
    env = envelope_wav(_wav(np.concatenate([silencio, alto, silencio])))
    assert env is not None
    assert env["duracao"] == 1.5
    valores = env["valores"]
    assert max(valores) == 1.0
    meio = valores[len(valores) // 3: 2 * len(valores) // 3]
    assert min(valores[:5]) < 0.05 and max(meio) > 0.9


def test_envelope_mistura_canais_e_aceita_8_bits():
    est = np.array([8000, -8000] * 2000, dtype=np.int16)
    estereo = np.repeat(est, 1).reshape(-1)
    assert envelope_wav(_wav(estereo, canais=2)) is not None
    oito = np.full(4000, 200, dtype=np.uint8)
    assert envelope_wav(_wav(oito, largura=1)) is not None


def test_envelope_rejeita_o_que_nao_e_wav():
    assert envelope_wav(b"isto nao e wav" * 10) is None
    assert envelope_wav("texto") is None
    assert envelope_wav(_wav(np.zeros(0, dtype=np.int16))) is None


def test_silencio_total_devolve_zeros():
    env = envelope_wav(_wav(np.zeros(4000, dtype=np.int16)))
    assert env is not None and set(env["valores"]) == {0.0}
