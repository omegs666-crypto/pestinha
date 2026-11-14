"""Convivência: memória do pet, aprendizado de falas, reações configuradas e o prompt do Ollama."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.mind import convivencia as cv  # noqa: E402
from pestinha.mind.convivencia import Convivencia, Reacoes, normalizar_regras, prompt_fala, ler_persona  # noqa: E402
from pestinha.mind.voz import Voz  # noqa: E402
from pestinha.sense.audio import Suavizador, analisar  # noqa: E402


def regra(**extra):
    base = {"id": "r1", "gatilho": "bravo", "ativa": True, "texto": "ei!", "tom": "alerta", "voz": False,
            "espera": 20, "sim": {"texto": "ok", "acao": "carinho"}, "nao": {"texto": "hmph", "acao": "falar_voz"}}
    base.update(extra)
    return base


# ---------------- validação das reações ----------------

def test_normaliza_descarta_gatilho_desconhecido_e_acao_invalida():
    out = normalizar_regras([regra(gatilho="inexistente"), regra(id="ok", sim={"texto": "x", "acao": "explodir"})])
    assert len(out) == 1
    assert out[0]["sim"]["acao"] == "nada"


def test_normaliza_limita_espera_e_tipos():
    out = normalizar_regras([regra(espera=9999), regra(id="b", espera="lixo"), regra(id="c", tom="zangado", voz="sim")])
    assert out[0]["espera"] == cv.ESPERA_MAX
    assert out[1]["espera"] == cv.ESPERA_PADRAO
    assert out[2]["tom"] == "calmo" and out[2]["voz"] is False


def test_normaliza_ids_repetidos_e_limite():
    out = normalizar_regras([regra(), regra()] + [regra(id=f"x{i}") for i in range(60)])
    assert len({r["id"] for r in out}) == len(out)
    assert len(out) <= cv.MAX_REGRAS


def test_normaliza_lixo_nao_quebra():
    assert normalizar_regras(None) == []
    assert normalizar_regras(["texto", 3, {"gatilho": None}]) == []


# ---------------- reações: sim, não e espera ----------------

def test_reacao_sim_quando_voce_reage_a_tempo():
    r = Reacoes(Path("nao_usado.json"))
    r.definir([regra()])
    inicial = r.disparar("bravo", now=100.0)
    assert inicial == {"texto": "ei!", "tom": "alerta", "voz": False}
    ramos = r.reagiu(now=110.0)
    assert ramos == [{"texto": "ok", "acao": "carinho", "tom": "alerta", "voz": False}]
    assert r.expirar(now=500.0) == []                      # já resolvida: não vira ramo não


def test_reacao_nao_quando_passa_a_espera():
    r = Reacoes(Path("nao_usado.json"))
    r.definir([regra(espera=10)])
    r.disparar("bravo", now=100.0)
    assert r.expirar(now=105.0) == []                      # ainda dentro da espera
    ramos = r.expirar(now=111.0)
    assert ramos == [{"texto": "hmph", "acao": "falar_voz", "tom": "alerta", "voz": True}]


def test_regra_desativada_nao_dispara():
    r = Reacoes(Path("nao_usado.json"))
    r.definir([regra(ativa=False)])
    assert r.disparar("bravo", now=1.0) is None


def test_disparo_repetido_reinicia_a_espera():
    r = Reacoes(Path("nao_usado.json"))
    r.definir([regra(espera=10)])
    r.disparar("bravo", now=100.0)
    r.disparar("bravo", now=108.0)                         # segunda vez: a espera recomeça
    assert r.expirar(now=112.0) == []
    assert len(r.expirar(now=119.0)) == 1


def test_definir_aceita_formato_do_arquivo_e_salva(tmp_path):
    caminho = tmp_path / "reacoes.json"
    r = Reacoes(caminho)
    r.definir({"ia": False, "regras": [regra()]}, salvar=True)
    assert r.ia is False and len(r.regras) == 1
    novo = Reacoes(caminho)
    novo.load()
    assert novo.ia is False and novo.regras[0]["gatilho"] == "bravo"


def test_exportar_inclui_gatilhos_e_acoes():
    dados = Reacoes(Path("nao_usado.json")).exportar()
    assert "preso" in dados["gatilhos"] and "bravo" in dados["gatilhos"]
    assert set(dados["acoes"]) == {"falar", "falar_voz", "carinho", "nada"}


# ---------------- memória de convivência ----------------

def test_contagens_persistem(tmp_path):
    c = Convivencia(tmp_path / "convivencia.json")
    c.registrar("cutucada", now=0.0)
    c.registrar("cutucada", now=1.0)
    c.salvar()
    novo = Convivencia(tmp_path / "convivencia.json")
    novo.load()
    assert novo.contagens == {"cutucada": 2}


def test_load_descarta_entradas_invalidas(tmp_path):
    arq = tmp_path / "convivencia.json"
    arq.write_text('{"contagens": {"ok": 3, "ruim": "x", "neg": -1}, "pontos": {"a": 99, "b": "x"}}', encoding="utf-8")
    c = Convivencia(arq)
    c.load()
    assert c.contagens == {"ok": 3}
    assert c.pontos == {"a": cv.PONTOS_MAX}


def test_resposta_do_usuario_ensina_a_fala():
    c = Convivencia(Path("nao_usado.json"))
    c.mostrou("to feliz!", now=10.0)
    c.reagiu(now=20.0)
    assert c.peso("to feliz!") > 1.0


def test_fala_ignorada_perde_peso_e_peso_fica_limitado():
    c = Convivencia(Path("nao_usado.json"))
    c.mostrou("ninguém me quer", now=0.0)
    c.expirar(now=cv.JANELA_REACAO_S + 1)
    assert c.peso("ninguém me quer") < 1.0
    c.pontos["x"] = 5.0
    assert c.peso("x") <= cv.PESO_MAX
    assert c.peso("desconhecida") == 1.0


def test_fatos_resumem_o_que_ele_lembra():
    c = Convivencia(Path("nao_usado.json"))
    c.contagens = {"cutucada": 4, "carinho": 2, "dispensa": 7}
    texto = c.fatos()
    assert "7 travessuras que você dispensou" in texto and "4 cutucadas" in texto
    assert Convivencia(Path("nao_usado.json")).fatos() == "ainda nos conhecemos pouco"


# ---------------- Ollama: prompt e persona ----------------

def test_prompt_fala_leva_persona_fatos_e_exemplos():
    msgens = prompt_fala("Bryan", "Você é debochado.", "bravo", "3 cutucadas", ["oi!", "ei!"])
    assert msgens[0]["role"] == "system" and "Bryan" in msgens[0]["content"] and "debochado" in msgens[0]["content"]
    assert "3 cutucadas" in msgens[1]["content"] and "oi! | ei!" in msgens[1]["content"]


def test_persona_dos_pets_existe_e_falta_vazia(tmp_path):
    assert "debochado" in ler_persona(ROOT / "pets" / "bryan")
    assert "trambiqueiro" in ler_persona(ROOT / "pets" / "jorge")
    assert ler_persona(tmp_path) == ""


# ---------------- sorteio de falas com peso ----------------

def _voz(tmp_path, pesos, linhas="a\nb\n"):
    pasta = tmp_path / "pets" / "bryan"
    (pasta / "falas").mkdir(parents=True)
    (pasta / "falas" / "bravo.txt").write_text(linhas, encoding="utf-8")
    return Voz(dict(config.DEFAULT_PERMISSIONS, voz=False), SimpleNamespace(proprio=pasta), pesos=pesos)


def test_frase_prefere_a_fala_que_voce_responde(tmp_path):
    v = _voz(tmp_path, pesos=lambda fala: 3.0 if fala == "a" else 0.3)
    sorteios = [v.frase("bravo") for _ in range(200)]
    assert sorteios.count("a") > sorteios.count("b") * 3


def test_frase_nao_repete_a_ultima_quando_ha_outras(tmp_path):
    v = _voz(tmp_path, pesos=lambda fala: 1.0, linhas="a\nb\nc\n")
    seguidas = [v.frase("bravo") for _ in range(50)]
    assert all(x != y for x, y in zip(seguidas, seguidas[1:]))


def test_dizer_respeita_voz_desligada(tmp_path):
    v = _voz(tmp_path, pesos=lambda fala: 1.0)
    assert v.dizer("oi", now=100.0) is None


# ---------------- conteúdo dos pets ----------------

EMOCOES_E_EVENTOS = ["feliz", "contente", "curioso", "observando", "bravo", "triste", "dramatico", "dormindo",
                     "notebook", "preso", "fuga", "fogos", "arremesso", "assustado", "susto", "protesto", "dispensa",
                     "_padrao"]


def test_todo_pet_tem_falas_para_cada_emocao_e_evento():
    for pet in ("bryan", "jorge"):
        for motivo in EMOCOES_E_EVENTOS:
            arq = ROOT / "pets" / pet / "falas" / f"{motivo}.txt"
            linhas = [l for l in arq.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
            assert len(linhas) >= 4, f"{pet}/{motivo} tem poucas falas"


# ---------------- áudio: suavização e silêncio ----------------

def test_suavizador_sobe_rapido_e_cai_devagar():
    s = Suavizador(bandas=2)
    subiu = s.aplicar({"bandas": [1.0, 1.0], "rms": 0.2, "pico": 0.9}, agora=0.0)["bandas"][0]
    caiu = s.aplicar({"bandas": [0.0, 0.0], "rms": 0.2, "pico": 0.0}, agora=0.1)["bandas"][0]
    assert subiu > 0.5 and caiu > subiu * 0.8             # a queda é lenta: ainda perto do topo


def test_suavizador_detecta_silencio_so_depois_do_tempo():
    s = Suavizador(bandas=2)
    zero = {"bandas": [0.0, 0.0], "rms": 0.0, "pico": 0.0}
    assert s.aplicar(zero, agora=0.0)["silencio"] is False
    assert s.aplicar(zero, agora=cv_silencio() + 0.1)["silencio"] is True


def test_suavizador_ignora_quadro_de_tamanho_errado():
    dados = {"bandas": [0.5], "rms": 0.1, "pico": 0.1}
    assert Suavizador(bandas=2).aplicar(dados, agora=0.0) is dados


def test_analisar_sinal_senoidal_cai_numa_banda():
    taxa = 48_000
    t = np.arange(4096) / taxa
    dados = analisar(np.sin(2 * np.pi * 1000 * t), taxa=taxa)
    assert max(dados["bandas"]) > 0.5 and dados["rms"] > 0.5


def cv_silencio():
    from pestinha.sense.audio import SILENCIO_S
    return SILENCIO_S
