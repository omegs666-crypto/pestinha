"""Painéis do menu (monitor neural e painel de protesto): abrir à mão deve manter o painel na tela."""
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def pet_app(tmp_path):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS))           # modo teste desligado (padrão)
    app = PestinhaApp(store, paths)
    yield app
    app.floats.hidden_by_tray = True
    for w in list(app.floats.windows.values()):
        w.close()


def test_painel_aberto_no_menu_fica_na_tela_fora_do_modo_teste(pet_app):
    pet_app.floats.open("neural")
    pet_app.floats.sync(pet_app.floats_allowed(), pet_app.floats_base())
    assert pet_app.floats.window("neural").isVisible()


def test_clicar_de_novo_fecha_o_painel(pet_app):
    pet_app.floats.toggle("greve")
    pet_app.floats.toggle("greve")
    pet_app.floats.sync(pet_app.floats_allowed(), pet_app.floats_base())
    assert not pet_app.floats.window("greve").isVisible()


def test_esconder_o_bryan_esconde_o_painel(pet_app):
    pet_app.floats.open("greve")
    pet_app.floats.sync(False, False)
    assert not pet_app.floats.window("greve").isVisible()


def test_timers_de_paineis_param_quando_ocultos(pet_app):
    monitor = pet_app.floats.window("neural")
    protest = pet_app.floats.window("greve")
    mlp = pet_app.floats.window("mlp")
    monitor.show()
    protest.show()
    mlp.show()
    assert monitor.timer.isActive()
    assert protest.timer.isActive()
    monitor.hide()
    protest.hide()
    mlp.hide()
    assert not monitor.timer.isActive()
    assert not protest.timer.isActive()
    pet_app.floats.shutdown()


def test_treino_mlp_nao_roda_na_thread_da_interface(pet_app):
    mlp = pet_app.floats.window("mlp")
    mlp.show()
    mlp.treinar()
    task = mlp._treino_task
    assert mlp.btn_treinar.text() == "Pausar"
    assert not mlp.btn_reiniciar.isEnabled()
    QTest.qWait(400)
    assert mlp._treino_task is None and mlp.btn_treinar.text() != "Pausar"
    assert mlp.btn_treinar.isEnabled()
    assert mlp.perdas
    assert task.thread_ident != threading.get_ident()
    mlp.hide()
    mlp.shutdown()


def test_renderizacao_trata_matriz_mlp_corrompida(pet_app):
    mlp = pet_app.floats.window("mlp")
    mlp.resize(380, 420)
    mlp.rede.W1 = [[0.0]]
    surface = QImage(380, 420, QImage.Format_ARGB32)
    mlp.render(surface)
    assert not surface.isNull()


def test_monitor_nao_crasha_com_dimensao_de_rede_invalida(pet_app):
    from types import SimpleNamespace
    monitor = pet_app.floats.window("neural")
    monitor.resize(1000, 620)
    pet_app.brain = SimpleNamespace(N=0, kind=[], raster=[])
    surface = QImage(1000, 620, QImage.Format_ARGB32)
    monitor.render(surface)
    assert not surface.isNull()

@pytest.fixture(autouse=True)
def _sem_tela_cheia(monkeypatch):
    """A área de trabalho real pode estar em tela cheia (vídeo, jogo); os painéis dependem disso."""
    monkeypatch.setattr("pestinha.app.senses.is_fullscreen", lambda: False)
