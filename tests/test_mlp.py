"""Validação de dimensões, finitude e cancelamento da MLP didática."""

import threading

import numpy as np
import pytest

from pestinha.core.mlp import NeuralNetwork


def test_forward_aceita_vetor_ou_batch_com_formas_definidas():
    net = NeuralNetwork()
    assert net.forward(np.zeros(6)).shape == (2,)
    assert net.forward(np.zeros((3, 6))).shape == (3, 2)


@pytest.mark.parametrize("data", [
    np.zeros(5),
    np.zeros((2, 5)),
    np.zeros((2, 3, 6)),
    np.full((1, 6), np.nan),
])
def test_forward_rejeita_forma_ou_valor_invalido(data):
    with pytest.raises(ValueError):
        NeuralNetwork().forward(data)


def test_train_rejeita_alvo_com_batch_incompativel():
    with pytest.raises(ValueError, match="Alvo MLP"):
        NeuralNetwork().train(np.zeros((2, 6)), np.zeros((1, 2)))


def test_backward_exige_entrada_igual_ao_forward():
    net = NeuralNetwork()
    x = np.zeros((1, 6))
    net.forward(x)
    with pytest.raises(ValueError, match="difere"):
        net.backward(np.ones((1, 6)), np.zeros((1, 2)), 0.1)


def test_treino_respeita_cancelamento_entre_epocas():
    cancel = threading.Event()
    cancel.set()
    losses = NeuralNetwork().train(
        np.zeros((1, 6)), np.zeros((1, 2)), epocas=500, cancel_event=cancel
    )
    assert losses == []


def test_treino_valido_retorna_perdas_finitas():
    x = np.array([[0.2, 0.8, 0.5, 0.1, 0.9, 0.3]])
    y = np.array([[0.9, 0.1]])
    losses = NeuralNetwork().train(x, y, epocas=25)
    assert len(losses) == 25
    assert np.isfinite(losses).all()
