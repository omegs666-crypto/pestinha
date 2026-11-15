"""Ouvir: detecção de fala por energia, conferência do modelo Parakeet e o caminho sem modelo na ponte."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from pestinha.sense import ouvir  # noqa: E402

SILENCIO = np.zeros(ouvir.BLOCO, dtype=np.float32)
VOZ = (0.2 * np.sin(np.linspace(0, 200, ouvir.BLOCO))).astype(np.float32)


def test_recorte_espera_a_fala_e_termina_no_silencio():
    r = ouvir.Recorte()
    for _ in range(5):
        assert r.passo(SILENCIO) == "continua"          # ruído de fundo
    for _ in range(10):
        assert r.passo(VOZ) == "continua"               # 1 s falando
    assert r.falando
    fim = [r.passo(SILENCIO) for _ in range(15)]
    assert "fim" in fim                                 # 1,2 s de silêncio encerra
    assert len(r.fala()) >= 10 * ouvir.BLOCO


def test_recorte_desiste_se_ninguem_falar():
    r = ouvir.Recorte()
    resultados = [r.passo(SILENCIO) for _ in range(int(ouvir.ESPERA_FALA_S / 0.1) + 2)]
    assert resultados[-1] == "nada" and not r.falando


def test_recorte_tem_limite_de_tempo():
    r = ouvir.Recorte()
    for _ in range(4):
        r.passo(SILENCIO)
    passos = [r.passo(VOZ) for _ in range(int(ouvir.MAX_FALA_S / 0.1) + 10)]
    assert "fim" in passos


def test_modelo_pronto_exige_os_quatro_arquivos_com_tamanho_certo(tmp_path):
    assert not ouvir.pronto(tmp_path)
    for nome, tamanho, _ in ouvir.ARQUIVOS:
        with open(tmp_path / nome, "wb") as f:
            f.truncate(tamanho)
    assert ouvir.pronto(tmp_path)
    (tmp_path / "tokens.txt").write_bytes(b"x")
    assert not ouvir.pronto(tmp_path)


def test_sha256_confere_conteudo(tmp_path):
    arq = tmp_path / "a.bin"
    arq.write_bytes(b"abc")
    assert ouvir.sha256(arq) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_modelo_fica_fora_do_onedrive():
    assert "OneDrive" not in str(ouvir.pasta_modelo())


def test_transcrever_ignora_audio_curto():
    assert ouvir.transcrever(np.zeros(100, dtype=np.float32)) == ""


def test_ponte_sem_modelo_pede_download(monkeypatch):
    from pestinha.ui import web_bridge
    monkeypatch.setattr(ouvir, "pronto", lambda pasta=None: False)
    ponte = web_bridge.Ponte(SimpleNamespace(perms={}, paths=SimpleNamespace(memory=ROOT)))
    avisos = []
    ponte.voz_modelo.connect(avisos.append)
    ponte.ouvir()
    assert avisos == ["ausente"]
    estado = json.loads(ponte.estado_modelo_voz())
    assert estado == {"pronto": False, "tamanho_mb": ouvir.TAMANHO_MB}
    ponte.shutdown()
