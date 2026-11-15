"""Laboratório MLP: a rede reage às entradas, o treino emite progresso e pode ser pausado ou reiniciado."""
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pestinha.core.mlp import NeuralNetwork
from pestinha.ui import lab_mlp


def _qt():
    return QApplication.instance() or QApplication([])


def _lab(tmp_path):
    _qt()
    app = SimpleNamespace(paths=SimpleNamespace(panels=Path(tmp_path) / "panels.json"))
    return lab_mlp.LabMLP(app, (40, 40))


def _pesos_iniciais():
    rede = NeuralNetwork()
    return {n: getattr(rede, n).copy() for n in lab_mlp.NOMES_PESOS}


def test_saida_muda_quando_a_entrada_muda(tmp_path):
    lab = _lab(tmp_path)
    antes = lab.saida.copy()
    lab.sl_entrada[0].setValue(100)
    lab.sl_entrada[3].setValue(90)
    assert not np.allclose(antes, lab.saida)
    assert lab.desenho.ativ[0][0] == pytest.approx(1.0)
    lab.close()


def test_treino_emite_progresso_e_reduz_a_perda():
    X = np.array([list(lab_mlp.X_PADRAO)])
    Y = np.array([list(lab_mlp.Y_PADRAO)])
    progresso, concluidos = [], []
    task = lab_mlp._TreinoTask(_pesos_iniciais(), X, Y, 60, 0.5, threading.Event())
    task.signals.progresso.connect(progresso.append)
    task.signals.concluido.connect(concluidos.append)
    task.run()
    assert len(progresso) == 60 // lab_mlp.PASSO_PROGRESSO
    assert concluidos and concluidos[0]["epoca"] == 60 and not concluidos[0]["cancelado"]
    perdas = [v for p in progresso for v in p["perdas"]] + concluidos[0]["perdas"]
    assert len(perdas) == 60 and perdas[-1] < perdas[0]


def test_treino_pausado_guarda_o_ponto_alcancado():
    X = np.array([list(lab_mlp.X_PADRAO)])
    Y = np.array([list(lab_mlp.Y_PADRAO)])
    cancelamento = threading.Event()
    concluidos = []
    task = lab_mlp._TreinoTask(_pesos_iniciais(), X, Y, 500, 0.5, cancelamento)
    task.signals.progresso.connect(lambda _d: cancelamento.set())
    task.signals.concluido.connect(concluidos.append)
    task.run()
    assert concluidos[0]["cancelado"] is True
    assert 0 < concluidos[0]["epoca"] < 500


def test_reiniciar_volta_aos_pesos_iniciais(tmp_path):
    lab = _lab(tmp_path)
    lab.rede.W1 = lab.rede.W1 + 1.0
    lab.perdas = [0.5, 0.4]
    lab.reiniciar()
    assert np.allclose(lab.rede.W1, NeuralNetwork().W1)
    assert lab.perdas == []
    lab.close()


def test_pesos_com_forma_errada_nao_sao_aceitos():
    pesos = _pesos_iniciais()
    assert lab_mlp._pesos_validos(pesos)
    pesos["W2"] = np.zeros((3, 4))
    assert not lab_mlp._pesos_validos(pesos)


def test_curva_anima_ate_assentar_e_para(tmp_path):
    _qt()
    curva = lab_mlp.CurvaPerda()
    curva.resize(400, 120)
    curva.show()
    curva.definir([1.0, 0.1, 0.01, 0.001])
    assert curva._timer.isActive()
    for _ in range(400):
        curva._quadro()
    assert not curva._timer.isActive()
    assert curva._mostra == pytest.approx(curva._alvo, abs=1e-4)
    curva.close()


def test_curva_pulso_para_quando_some(tmp_path):
    _qt()
    curva = lab_mlp.CurvaPerda()
    curva.show()
    curva.pulsar(True)
    assert curva._timer.isActive()
    curva.hide()
    assert not curva._timer.isActive()
    curva.close()


def test_curva_aceita_vazio_e_valores_invalidos():
    _qt()
    curva = lab_mlp.CurvaPerda()
    curva.definir([])
    curva.definir([float("nan"), 0.5, float("inf"), 0.25])
    assert curva.perdas == [0.5, 0.25]
    curva.close()


def test_painel_tem_fundo_opaco_escuro_como_os_outros(tmp_path):
    """O painel não pode ficar transparente: o miolo é escuro e opaco; só os cantos arredondados são vazados."""
    lab = _lab(tmp_path)
    lab.resize(480, 660)
    lab.show()
    imagem = lab.grab().toImage()
    lab.close()
    cor = imagem.pixelColor(240, 40)
    assert cor.alpha() == 255 and cor.red() < 60 and cor.green() < 60
    assert imagem.pixelColor(1, 1).alpha() == 0


def test_arrastar_pelo_grafico_move_o_painel(tmp_path):
    """Os widgets de dentro (gráfico, rede) não podem engolir o arraste: o painel continua movível por eles."""
    lab = _lab(tmp_path)
    lab.show()
    antes = lab.pos()
    centro = QPoint(lab.curva.width() // 2, lab.curva.height() // 2)
    QTest.mousePress(lab.curva, Qt.LeftButton, Qt.NoModifier, centro)
    QTest.mouseMove(lab.curva, centro + QPoint(40, 30))
    QTest.mouseRelease(lab.curva, Qt.LeftButton, Qt.NoModifier, centro + QPoint(40, 30))
    assert lab.pos() != antes
    lab.close()
