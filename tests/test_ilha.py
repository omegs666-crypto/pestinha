"""Ilha interativa (estilo Coucou): 2 painéis, pin, arraste com limiar e posição salva."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402
from pestinha.ui.ilha import GRANDE_H, GRANDE_W, PEQUENO  # noqa: E402
from pestinha.world.arrastavel import load_positions  # noqa: E402
from pestinha import log as log_module  # noqa: E402


@pytest.fixture
def pet_app(tmp_path):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS))
    app = PestinhaApp(store, paths)
    yield app


def _clique(ilha, x, y):
    """Simula um clique esquerdo sem arraste dentro da ilha."""
    global_pos = ilha.mapToGlobal(QPoint(x, y))
    press = QMouseEvent(QEvent.MouseButtonPress, QPointF(x, y), global_pos,
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    ilha.eventFilter(ilha._compact, press)
    release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(x, y), global_pos,
                          Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    ilha.eventFilter(ilha._compact, release)


def test_cria_comprimida_e_visivel(pet_app):
    ilha = pet_app.ilha
    ilha.show()
    QApplication.processEvents()
    assert ilha.isVisible()
    assert ilha.width() == PEQUENO[0]
    assert not ilha._dashboard.isVisibleTo(ilha)


def test_toggle_abre_e_recolhe(pet_app):
    ilha = pet_app.ilha
    ilha.abrir()
    QApplication.processEvents()
    assert ilha._aberta
    assert ilha._dashboard.isVisibleTo(ilha)
    ilha.recolher()
    assert not ilha._aberta
    ilha.toggle()
    assert ilha._aberta


def test_clique_na_capsula_compacta_abre_dashboard(pet_app):
    ilha = pet_app.ilha
    _clique(ilha, 20, 20)
    assert ilha._aberta
    assert ilha._dashboard.isVisibleTo(ilha)


def test_tamanho_grande_cabe_na_tela(pet_app):
    ilha = pet_app.ilha
    ilha.abrir()
    l, t, d, b = pet_app.bounds()
    assert ilha.width() <= min(GRANDE_W, d - l - 16)
    assert ilha.height() <= min(GRANDE_H, b - t - 20)


def test_fixar_impede_recolher(pet_app):
    ilha = pet_app.ilha
    ilha.abrir()
    ilha._pin_button.setChecked(True)
    assert ilha._fixada
    ilha.recolher()               # recolher() manual sempre funciona
    assert not ilha._aberta
    ilha.abrir()
    ilha._pin_button.setChecked(False)
    assert not ilha._fixada


def test_arraste_salva_posicao(pet_app):
    ilha = pet_app.ilha
    ilha.show()
    QApplication.processEvents()
    x0 = ilha.x()
    press_pos = ilha.mapToGlobal(QPoint(20, 20))
    press = QMouseEvent(QEvent.MouseButtonPress, QPointF(20, 20), press_pos,
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    ilha.mousePressEvent(press)
    for dx in (10, 30, 60):
        move = QMouseEvent(QEvent.MouseMove, QPointF(20 + dx, 20),
                           press_pos + QPoint(dx, 0),
                           Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        ilha.mouseMoveEvent(move)
    assert ilha._arrastou
    assert ilha.x() != x0
    release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(80, 20),
                          press_pos + QPoint(60, 0),
                          Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    ilha.mouseReleaseEvent(release)
    assert "ilha" in load_positions(pet_app.paths.panels)


def test_pills_abrem_paineis_e_recolhem(pet_app):
    ilha = pet_app.ilha
    ilha.abrir()
    ilha._open_neural.click()
    assert "neural" in pet_app.floats.opened
    assert ilha._aberta              # dashboard segue aberto até fechar ou sair


def test_timer_para_quando_escondida(pet_app):
    ilha = pet_app.ilha
    ilha.show()
    assert ilha._timer.isActive()
    ilha.hide()
    QApplication.processEvents()
    assert not ilha._timer.isActive()


def test_dashboard_exibe_tres_colunas_e_controles_reais(pet_app):
    ilha = pet_app.ilha
    ilha.abrir()
    assert ilha._controls_card.isVisibleTo(ilha)
    assert ilha._chart_card.isVisibleTo(ilha)
    assert ilha._log_card.isVisibleTo(ilha)
    assert ilha._metric.count() == 4
    assert ilha._delay_slider.minimum() == 1
    assert ilha._delay_slider.maximum() == 10


def test_seletor_atualiza_grafico_com_snapshot_local(pet_app):
    ilha = pet_app.ilha
    ilha._atualizar_dados()
    ilha._atualizar_dados()
    ilha._metric.setCurrentText("Insatisfação")
    ilha._render_grafico("Insatisfação")
    assert ilha._series["insatisfacao"]
    assert ilha._chart._headline == "Insatisfação"


def test_controles_aplicam_permissoes_ao_backend(pet_app):
    ilha = pet_app.ilha
    ilha._alternar_voz()
    assert pet_app.perms["voz"]
    ilha._alternar_travessuras()
    assert pet_app.perms["travessuras"]
    ilha._mudar_delay(5)
    assert ilha._delay_s == 5


def test_eventos_do_backend_aparecem_no_console_da_ilha(pet_app):
    ilha = pet_app.ilha
    ilha.abrir()
    log_module.log("evento de teste do backend")
    ilha._atualizar_dados()
    assert "evento de teste do backend" in ilha._log_view.toPlainText()


def test_hover_tem_expansao_completa_apos_delay_curto(pet_app):
    ilha = pet_app.ilha
    ilha.show()
    ilha._timer_hover.start(0)
    QApplication.processEvents()
    assert ilha._aberta
    assert ilha._dashboard.isVisibleTo(ilha)


def test_aba_chat_tem_modelos_historico_e_compositor_local(pet_app, monkeypatch):
    ilha = pet_app.ilha
    monkeypatch.setattr(ilha._ollama, "list_models_async", lambda: None)
    ilha._tabs.setCurrentIndex(1)
    assert ilha._tabs.tabText(1) == "Chat local"
    assert ilha._model_combo is not None
    assert ilha._chat_view.isReadOnly()
    assert ilha._chat_input is not None
    assert ilha._context_button.text() == "Analisar resultados"


def test_envio_de_contexto_usa_snapshot_explicito_e_modelo_escolhido(pet_app):
    ilha = pet_app.ilha
    ilha._model_combo.addItem("qwen2.5:latest")
    calls = []
    ilha._ollama.chat_stream_async = lambda model, messages: calls.append((model, messages))
    context = '{"energia":0.73,"logs_recentes":["local"]}'
    ilha._enviar_chat("diagnóstico", context=context)
    assert calls[0][0] == "qwen2.5:latest"
    assert calls[0][1][-1]["content"].startswith("diagnóstico")
    assert context in calls[0][1][-1]["content"]
    assert calls[0][1][0]["role"] == "system"
    ilha._chat_concluido()


def test_streaming_aparece_incrementalmente_no_historico_da_ui(pet_app):
    ilha = pet_app.ilha
    ilha._chat_view.clear()
    ilha._receber_token("Resposta ")
    ilha._receber_token("incremental")
    assert "Resposta incremental" in ilha._chat_view.toPlainText()
    ilha._chat_concluido()


def test_analisar_resultados_anexa_snapshot_e_logs_locais(pet_app):
    ilha = pet_app.ilha
    ilha._model_combo.addItem("llama3.2")
    calls = []
    ilha._ollama.chat_stream_async = lambda model, messages: calls.append((model, messages))
    ilha._analisar_contexto()
    prompt = calls[0][1][-1]["content"]
    assert calls[0][0] == "llama3.2"
    assert "Dados locais do projeto (JSON)" in prompt
    assert "energia" in prompt
    assert "logs_recentes" in prompt
    ilha._chat_concluido()


def test_modelos_localizados_atualizam_seletor_e_preferencia(pet_app):
    ilha = pet_app.ilha
    ilha._modelos_recebidos(["phi3:mini", "qwen2.5:latest"])
    assert ilha._model_combo.count() == 2
    assert pet_app.perms["ollama_chat_modelo"] == "phi3:mini"


def test_erro_de_conexao_mostra_aviso_vermelho(pet_app):
    ilha = pet_app.ilha
    ilha._ollama_erro("Ollama desconectado. Inicie o serviço local.")
    assert ilha._ollama_status.text() == "Ollama desconectado. Inicie o serviço local."


def test_campo_chat_recebe_foco_e_capsula_o_devolve_ao_recolher(pet_app, monkeypatch):
    from PySide6.QtTest import QTest
    from pestinha.ui.ilha import ANIM_MS

    ilha = pet_app.ilha
    monkeypatch.setattr(ilha._ollama, "list_models_async", lambda: None)
    ilha.show()
    ilha.abrir()
    ilha._tabs.setCurrentIndex(1)
    QApplication.processEvents()
    assert ilha._foco_chat
    assert not (ilha.windowFlags() & Qt.WindowDoesNotAcceptFocus)
    ilha._chat_input.setFocus()
    QApplication.processEvents()
    assert QApplication.focusWidget() is ilha._chat_input
    ilha.recolher()
    QTest.qWait(ANIM_MS + 40)
    assert not ilha._foco_chat
    assert bool(ilha.windowFlags() & Qt.WindowDoesNotAcceptFocus)


def test_clique_na_aba_chat_reabilita_foco_apos_reabrir(pet_app, monkeypatch):
    from PySide6.QtTest import QTest
    ilha = pet_app.ilha
    monkeypatch.setattr(ilha._ollama, "list_models_async", lambda: None)
    ilha.show()
    ilha.abrir()
    ilha._tabs.setCurrentIndex(1)
    ilha._definir_foco_chat(False)
    QApplication.processEvents()
    tab_bar = ilha._tabs.tabBar()
    point = tab_bar.tabRect(1).center()
    event = QMouseEvent(
        QEvent.MouseButtonRelease,
        QPointF(point),
        QPointF(tab_bar.mapToGlobal(point)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    ilha.eventFilter(tab_bar, event)
    QTest.qWait(20)
    assert ilha._foco_chat
    assert not (ilha.windowFlags() & Qt.WindowDoesNotAcceptFocus)


def test_controles_de_voz_sao_visiveis_e_configuraveis(pet_app):
    ilha = pet_app.ilha
    assert ilha._voice_reply_button.isCheckable()
    ilha._voice_reply_button.setChecked(True)
    assert ilha._voice_reply_button.text() == "Ler respostas: sim"


def test_transcricao_local_vira_prompt_no_chat(pet_app):
    ilha = pet_app.ilha
    ilha._model_combo.addItem("llama3.2")
    capturados = []
    ilha._ollama.chat_stream_async = lambda model, messages: capturados.append(
        (model, messages)
    )
    ilha._texto_reconhecido("Como está a energia do pet?")
    assert ilha._chat_input.toPlainText() == ""
    assert capturados[0][0] == "llama3.2"
    assert capturados[0][1][-1]["content"] == "Como está a energia do pet?"
    ilha._chat_concluido()


def test_resposta_do_chat_pode_ser_lida_localmente(pet_app, monkeypatch):
    ilha = pet_app.ilha
    faladas = []
    monkeypatch.setattr(ilha._speech, "speak", faladas.append)
    ilha._voice_reply_button.setChecked(True)
    ilha._chat_busy = True
    ilha._assistant_buffer = "Resposta em voz."
    ilha._chat_concluido()
    assert faladas == ["Resposta em voz."]
