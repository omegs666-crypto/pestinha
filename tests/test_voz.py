"""Voz: o pet comenta a emoção em voz alta com frases de pets/<pet>/falas/, opt-in e sem travar."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha import config  # noqa: E402
from pestinha.mind.voz import Voz, _json_str, _ps_str  # noqa: E402


def voz(tmp_path, ligado=True, url=""):
    """Uma Voz com a pasta falas/ do pet em tmp_path."""
    pasta = tmp_path / "pets" / "bryan"
    (pasta / "falas").mkdir(parents=True)
    (pasta / "falas" / "bravo.txt").write_text("raiva!\nfurioso!\n", encoding="utf-8")
    perms = dict(config.DEFAULT_PERMISSIONS, voz=ligado, voz_url=url)
    from types import SimpleNamespace
    return Voz(perms, SimpleNamespace(proprio=pasta))


def test_desligado_nao_fala(tmp_path):
    v = voz(tmp_path, ligado=False)
    assert v.falar("bravo") is None


def test_fala_frase_do_arquivo(tmp_path, monkeypatch):
    v = voz(tmp_path)
    falas = []
    monkeypatch.setattr(v, "_falar_async", lambda t, m=None: falas.append(t))
    assert v.falar("bravo", now=100.0) in ("raiva!", "furioso!")
    assert len(falas) == 1


def test_cooldown_nao_repente(tmp_path, monkeypatch):
    v = voz(tmp_path)
    monkeypatch.setattr(v, "_falar_async", lambda t, m=None: None)
    assert v.falar("bravo", now=100.0) is not None
    assert v.falar("bravo", now=105.0) is None                  # ainda no cooldown
    assert v.falar("bravo", now=160.0) is not None              # já pode de novo


def test_sem_arquivo_usa_frase_da_emocao(tmp_path):
    v = voz(tmp_path)
    (tmp_path / "pets" / "bryan" / "falas" / "bravo.txt").unlink()
    assert v.falar("bravo") == "tô bravo!"


def test_fallback_padrao(tmp_path):
    v = voz(tmp_path)
    (tmp_path / "pets" / "bryan" / "falas" / "_padrao.txt").write_text("oi!\n", encoding="utf-8")
    (tmp_path / "pets" / "bryan" / "falas" / "curioso.txt").unlink(missing_ok=True)
    assert v._frase("curioso") == "oi!"


def test_escapes_de_texto():
    assert _json_str('oi "ele"') == '"oi \\"ele\\""'
    assert _ps_str("não 'é'") == "'não ''é'''"


def test_voz_url_invalida_nao_derruba(tmp_path):
    v = voz(tmp_path, url="http://127.0.0.1:9/nada")
    v._falar_async("teste")          # conexão recusada: exceção fica na thread, não derruba
    import time as _t
    for _ in range(60):
        if not v._falando:
            break
        _t.sleep(0.2)
    assert not v._falando
