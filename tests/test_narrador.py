"""Narrador do Núcleo: regras locais, escolha segura de modelo e insight do Ollama pela ponte."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.mind.narrador import (  # noqa: E402
    INTERVALO_MIN_S, Narrador, escolher_modelo, limpar_frase, modelo_de_nuvem, prompt_insight,
)
from pestinha.ui.web_bridge import Ponte  # noqa: E402


def _estado(**mudancas):
    base = {"emocao": "Feliz", "energia": 70, "estimulacao": 40, "insatisfacao": 10,
            "atividade": 30, "pausado": False, "processando": False, "logs": []}
    base.update(mudancas)
    return base


def test_regras_falam_nas_transicoes_e_respeitam_o_intervalo():
    n = Narrador()
    assert n.observar(_estado(), 0) is None                       # primeira leitura só guarda
    fala = n.observar(_estado(energia=20), 1)
    assert fala and "Energia baixa" in fala["texto"] and fala["tom"] == "alerta"
    assert n.observar(_estado(energia=20, emocao="Bravo"), 2) is None   # cedo demais
    fala = n.observar(_estado(energia=20, emocao="Bravo", processando=True), 2 + INTERVALO_MIN_S)
    assert fala["texto"].startswith("Iniciando ciclos")


def test_regra_nao_se_repete_em_seguida():
    n = Narrador()
    n.observar(_estado(), 0)
    assert n.observar(_estado(emocao="Bravo"), 0)
    n.observar(_estado(emocao="Feliz"), 1)
    assert n.observar(_estado(emocao="Bravo"), 20) is None        # mesma regra antes de 90 s


def test_modelo_do_narrador_nunca_e_de_nuvem_e_prefere_leve():
    modelos = ["deepseek-r1:8b", "glm4:latest", "minimax-m2:cloud", "qwen2.5:3b"]
    assert modelo_de_nuvem("minimax-m2:cloud") and not modelo_de_nuvem("qwen2.5:3b")
    assert escolher_modelo(modelos, "minimax-m2:cloud") == "qwen2.5:3b"
    assert escolher_modelo(["deepseek-r1:8b", "glm4:latest"], "deepseek-r1:8b") == "glm4:latest"
    assert escolher_modelo(["deepseek-r1:8b"], "") == "deepseek-r1:8b"   # só raciocínio: usa mesmo assim
    assert escolher_modelo(["x:cloud"], "x:cloud") == ""


def test_frase_limpa_tira_raciocinio_aspas_e_limita_tamanho():
    assert limpar_frase('<think>muito texto</think> "Ele está cansado."') == "Ele está cansado."
    assert len(limpar_frase("a " * 500)) <= 160
    assert limpar_frase(None) == ""


def test_prompt_traduz_numeros_em_fatos():
    mensagens = prompt_insight(_estado(energia=15, insatisfacao=80), "Bryan")
    assert mensagens[0]["role"] == "system" and "Bryan" in mensagens[0]["content"]
    assert "Energia: 15% (muito baixo)" in mensagens[1]["content"]
    assert "Insatisfação: 80% (alto)" in mensagens[1]["content"]


class _App:
    perms = {"voz": False, "travessuras": False}
    paused = False
    nome = "Pestinha"
    floats = SimpleNamespace(toggle=lambda k: None, windows={})

    def __init__(self, memoria):
        self.paths = SimpleNamespace(memory=memoria)


def test_insight_do_ollama_vira_aviso_sem_usar_o_chat(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    ponte = Ponte(_App(tmp_path))
    pedidos, avisos, estados = [], [], []
    ponte.aviso.connect(lambda s: avisos.append(json.loads(s)))
    ponte.narrador_estado.connect(estados.append)

    def falso_stream(modelo, mensagens):
        pedidos.append(modelo)
        ponte._insight_token("<think>…</think> Ele está ")
        ponte._insight_token("cheio de energia.")
        ponte._insight_fim()

    monkeypatch.setattr(ponte._ollama_narrador, "chat_stream_async", falso_stream)
    chat = []
    monkeypatch.setattr(ponte._ollama, "chat_stream_async", lambda *a: chat.append(a))
    ponte._guardar_modelos(["minimax-m2:cloud", "qwen2.5:3b"])
    ponte.pedir_insight()
    assert pedidos == ["qwen2.5:3b"] and chat == []
    assert avisos == [{"texto": "Ele está cheio de energia.", "tom": "insight", "origem": "jorge"}]
    assert estados == ["pensando", "pronto"]
    ponte.acao("avion", True)                                    # modo avião: nada de rede
    ponte.pedir_insight()
    assert pedidos == ["qwen2.5:3b"]
    ponte.shutdown()


def test_falha_do_ollama_avisa_uma_vez(tmp_path):
    QApplication.instance() or QApplication([])
    ponte = Ponte(_App(tmp_path))
    avisos = []
    ponte.aviso.connect(lambda s: avisos.append(json.loads(s)))
    ponte._insight_erro("connection refused")
    ponte._insight_erro("connection refused")
    assert len(avisos) == 1 and avisos[0]["tom"] == "alerta"
    ponte.shutdown()


def test_regiao_de_clique_e_limitada(tmp_path):
    QApplication.instance() or QApplication([])
    ponte = Ponte(_App(tmp_path))
    recebidas = []
    ponte.regiao.connect(lambda *r: recebidas.append(r))
    ponte.definir_regiao(-50, 10, 999_999, 0)
    assert recebidas == [(0, 10, 4000, 1)]
    ponte.shutdown()
