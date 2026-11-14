"""Segundo cérebro (Obsidian): diário e aprendizado em Markdown, só dentro de Pestinha/<pet>/ do vault."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.mind.segundo_cerebro import SegundoCerebro  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

CASTIGO = {"fugas": 2.0, "rancor": 0.4, "receio": 0.1}
DRIVES = {"energia": 0.8, "estimulo": 0.3, "contato": 0.5}


def cerebro(tmp_path, ligado=True):
    """Um SegundoCerebro com permissão ligada e pasta em tmp_path."""
    perms = dict(config.DEFAULT_PERMISSIONS,
                 segundo_celebro=ligado, segundo_celebro_pasta=str(tmp_path / "vault"))
    return SegundoCerebro(perms, "bryan", "Bryan")


def test_desligado_nao_escreve_nada(tmp_path):
    c = cerebro(tmp_path, ligado=False)
    c.registrar("cutucada")
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")
    assert not (tmp_path / "vault").exists()


def test_sem_pasta_escolhida_nao_escreve(tmp_path):
    perms = dict(config.DEFAULT_PERMISSIONS, segundo_celebro=True)
    c = SegundoCerebro(perms, "bryan", "Bryan")
    c.registrar("cutucada")
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")
    assert c._base() is None


def test_evento_vai_para_o_diario_do_dia(tmp_path):
    c = cerebro(tmp_path)
    c.registrar("cutucada")
    c.registrar("entrou no cantinho do castigo")
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")
    diario = tmp_path / "vault" / "Pestinha" / "bryan" / "diario"
    arquivos = list(diario.glob("*.md"))
    assert len(arquivos) == 1
    texto = arquivos[0].read_text(encoding="utf-8")
    assert "Diário de Bryan" in texto
    assert "cutucada" in texto and "entrou no cantinho do castigo" in texto
    assert "- **" in texto                                   # cada evento tem hora


def test_aprendizado_e_perfil_em_markdown(tmp_path):
    c = cerebro(tmp_path)
    learned = [("CARESS", "PLAYFUL", 0.02), ("DISMISS", "GLOOM", -0.01)]
    c.salvar(learned, {"PLACA": 0.4}, CASTIGO, DRIVES, "bravo")
    base = tmp_path / "vault" / "Pestinha" / "bryan"
    aprendizado = (base / "aprendizado.md").read_text(encoding="utf-8")
    assert "O que Bryan aprendeu" in aprendizado
    assert "CARESS → PLAYFUL" in aprendizado and "+0.020" in aprendizado
    assert "`PLACA`: 0.40" in aprendizado
    assert "fugas que deram certo: **2**" in aprendizado
    assert "energia: 0.80" in aprendizado
    perfil = (base / "perfil.md").read_text(encoding="utf-8")
    assert "# Bryan" in perfil and "**bravo**" in perfil


def test_aprendizado_so_reescreve_quando_muda(tmp_path):
    c = cerebro(tmp_path)
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")
    alvo = tmp_path / "vault" / "Pestinha" / "bryan" / "aprendizado.md"
    primeiro = alvo.stat().st_mtime_ns
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")                # mesmo conteúdo: não regrava
    assert alvo.stat().st_mtime_ns == primeiro


def test_eventos_desligados_sao_descartados_no_salvar(tmp_path):
    perms = dict(config.DEFAULT_PERMISSIONS, segundo_celebro_pasta=str(tmp_path / "vault"))
    c = SegundoCerebro(perms, "bryan", "Bryan")
    c.registrar("cutucada")                                   # desligado: nem entra no buffer
    assert not c._eventos
    c.perms["segundo_celebro"] = False
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")
    assert not (tmp_path / "vault").exists()


def test_pasta_sem_permissao_nao_derruba(tmp_path, monkeypatch):
    import pestinha.mind.segundo_cerebro as sc
    c = cerebro(tmp_path)
    monkeypatch.setattr(sc, "pasta_gravavel", lambda _p: False)
    c.registrar("cutucada")
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")                # não levanta exceção
    assert not (tmp_path / "vault" / "Pestinha").exists()


def test_pet_id_invalido_nao_escreve_fora(tmp_path):
    perms = dict(config.DEFAULT_PERMISSIONS, segundo_celebro=True,
                 segundo_celebro_pasta=str(tmp_path / "vault"))
    c = SegundoCerebro(perms, "../fora", "Bryan")
    c.registrar("cutucada")
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")
    assert not (tmp_path / "vault").exists()
    assert not (tmp_path / "fora").exists()


def test_diario_nunca_leva_nome_de_programa(tmp_path):
    c = cerebro(tmp_path)
    c.registrar("cutucada")
    c.salvar([], {}, CASTIGO, DRIVES, "feliz")
    texto = next((tmp_path / "vault" / "Pestinha" / "bryan" / "diario").glob("*.md")).read_text(encoding="utf-8")
    for palavra in ("code.exe", "chrome.exe", "explorer.exe"):
        assert palavra not in texto


def test_permissao_tipo_errado_cai_no_padrao(tmp_path):
    from pestinha.store import write_json
    paths = Paths(root=tmp_path)
    paths.memory.mkdir(parents=True)
    write_json(paths.permissions, {"segundo_celebro": "sim", "segundo_celebro_pasta": 42})
    perms = config.load_permissions(paths)
    assert perms["segundo_celebro"] is config.DEFAULT_PERMISSIONS["segundo_celebro"]
    assert perms["segundo_celebro_pasta"] == ""


def test_grupo_segundo_celebro_na_tela(tmp_path):
    QApplication.instance() or QApplication([])
    from pestinha.ui.ui import SettingsDialog
    paths = Paths(root=tmp_path)
    perms = dict(config.DEFAULT_PERMISSIONS, segundo_celebro=True)
    dialog = SettingsDialog(perms, paths, first_run=False)
    assert "segundo_celebro" in dialog.boxes
    assert dialog.vault_button.isEnabled()
    dialog.close()


def test_escolher_pasta_grava_permissao(tmp_path, monkeypatch):
    from pestinha.ui.ui import SettingsDialog
    QApplication.instance() or QApplication([])
    paths = Paths(root=tmp_path)
    dialog = SettingsDialog(dict(config.DEFAULT_PERMISSIONS, segundo_celebro=True), paths, first_run=False)
    mudancas = []
    dialog.changed.connect(mudancas.append)
    pasta = tmp_path / "vault"
    monkeypatch.setattr("pestinha.ui.ui.QFileDialog.getExistingDirectory", lambda *a, **k: str(pasta))
    dialog._escolher_vault()
    assert mudancas == [{"segundo_celebro_pasta": str(pasta)}]
    assert str(pasta) in dialog.vault_label.text()
    dialog.close()


# ---------------- dentro do app ----------------

@pytest.fixture
def pet_app(tmp_path):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, segundo_celebro=True,
                      segundo_celebro_pasta=str(tmp_path / "vault")))
    app = PestinhaApp(store, paths)
    yield app, tmp_path
    app.floats.hidden_by_tray = True
    for w in list(app.floats.windows.values()):
        w.close()
    app.tray.icon.hide()


def test_app_cria_e_salva_o_segundo_cerebro(pet_app):
    app, tmp_path = pet_app
    app.save()
    base = tmp_path / "vault" / "Pestinha" / "bryan"
    assert (base / "aprendizado.md").exists()
    assert (base / "perfil.md").exists()


def test_cutucada_vai_para_o_diario(pet_app):
    app, tmp_path = pet_app
    app.on_poke()
    app.save()
    diario = tmp_path / "vault" / "Pestinha" / "bryan" / "diario"
    texto = next(diario.glob("*.md")).read_text(encoding="utf-8")
    assert "cutucada" in texto


def test_pausado_nao_registra_interacao(pet_app):
    app, tmp_path = pet_app
    app.toggle_pause()
    app.on_poke()
    app.save()
    diario = tmp_path / "vault" / "Pestinha" / "bryan" / "diario"
    if diario.exists():
        texto = "".join(p.read_text(encoding="utf-8") for p in diario.glob("*.md"))
        assert "cutucada" not in texto


def test_desligar_permissao_para_de_escrever(pet_app):
    app, tmp_path = pet_app
    app.save()
    app.apply_perms({"segundo_celebro": False})
    app.on_poke()
    app.save()
    diario = tmp_path / "vault" / "Pestinha" / "bryan" / "diario"
    if diario.exists():
        texto = "".join(p.read_text(encoding="utf-8") for p in diario.glob("*.md"))
        assert "cutucada" not in texto


def test_apagar_dados_nao_toca_no_vault(pet_app):
    app, tmp_path = pet_app
    app.save()
    base = tmp_path / "vault" / "Pestinha" / "bryan"
    assert base.exists() and not str(base).startswith(str(app.paths.memory))
