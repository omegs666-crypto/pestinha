"""Ilha em WebEngine: análise do áudio, ponte com ações permitidas, persistência e página local."""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.mind.convivencia import Reacoes  # noqa: E402
from pestinha.sense.audio import BANDAS, TAXA, analisar  # noqa: E402
from pestinha.ui import web_island  # noqa: E402
from pestinha.ui.web_bridge import Ponte  # noqa: E402

WEB_DIR = ROOT / "pestinha" / "ui" / "web"


class FakeApp:
    def __init__(self, memoria):
        self.perms = {"voz": False, "travessuras": False, "ilha_web": True}
        self.paused = False
        self.nome = "Teste"
        self.paths = SimpleNamespace(memory=memoria)
        self.chamadas = []
        self.floats = SimpleNamespace(toggle=lambda chave: self.chamadas.append(chave))
        self.reacoes = Reacoes(memoria / "reacoes.json")
        self.reacoes.load()

    def toggle_pause(self):
        self.paused = not self.paused

    def apply_perms(self, mudancas):
        self.perms.update(mudancas)


def _qt():
    return QApplication.instance() or QApplication([])


def test_espectro_coloca_o_tom_na_banda_certa():
    t = np.arange(4096) / TAXA
    bandas = analisar(np.sin(2 * np.pi * 1000 * t), TAXA, BANDAS)["bandas"]
    assert len(bandas) == BANDAS
    pico = int(np.argmax(bandas))
    bordas = np.geomspace(40.0, min(16_000.0, TAXA / 2), BANDAS + 1)
    assert bordas[pico] <= 1000 <= bordas[pico + 1] * 1.01
    assert all(0.0 <= v <= 1.0 for v in bandas)


def test_espectro_com_silencio_e_entrada_invalida_devolve_zeros():
    casos = [[], [0.0] * 10, [float("nan")] * 200, np.zeros((4, 4)), None, "abc"]
    for caso in casos:
        resultado = analisar(caso)
        assert resultado["bandas"] == [0.0] * BANDAS
        assert resultado["rms"] == 0.0 and resultado["pico"] == 0.0


def test_acoes_seguem_a_lista_permitida(tmp_path):
    _qt()
    app = FakeApp(tmp_path)
    ponte = Ponte(app)
    ponte.acao("pausa", True)
    assert app.paused
    ponte.acao("concentracion", True)          # já pausado: não alterna de novo
    assert app.paused
    ponte.acao("concentracion", False)
    assert not app.paused
    ponte.acao("voz", False)
    assert app.perms["voz"] is True
    ponte.acao("avion", True)
    assert ponte.offline
    ponte.acao("executar_qualquer_coisa", True)  # fora da lista: ignorado
    ponte.painel("neural")
    ponte.painel("../../etc")                  # fora da lista: ignorado
    assert app.chamadas == ["neural"]
    ponte.shutdown()


def test_chat_respeita_modo_aviao_e_recusa_mensagens_malformadas(tmp_path):
    _qt()
    ponte = Ponte(FakeApp(tmp_path))
    erros, fins = [], []
    ponte.erro.connect(erros.append)
    ponte.chat_fim.connect(lambda: fins.append(True))
    ponte.acao("avion", True)
    ponte.enviar_chat("qualquer", json.dumps([{"role": "user", "content": "oi"}]))
    assert erros == ["Modo avião ativo: o chat local está desligado."] and fins == [True]
    ponte.acao("avion", False)
    ponte.enviar_chat("qualquer", "{não é json")
    assert erros[-1] == "Mensagem inválida." and len(fins) == 2
    ponte.shutdown()


def test_voz_do_llm_sem_modelo_usa_voz_do_sistema(tmp_path, monkeypatch):
    _qt()
    ponte = Ponte(FakeApp(tmp_path))
    faladas = []
    monkeypatch.setattr(ponte._voz, "speak", faladas.append)
    ponte.falar_resposta("", "resposta curta")
    assert faladas == ["resposta curta"]
    ponte._voz_do_sistema("falha")
    assert faladas == ["resposta curta", "resposta curta"]
    ponte.shutdown()


def test_persistencia_aceita_so_json_valido_e_nomes_conhecidos(tmp_path):
    _qt()
    app = FakeApp(tmp_path)
    ponte = Ponte(app)
    ponte.salvar("layout", '{"ok": 1}')
    assert json.loads((tmp_path / "web_layout.json").read_text(encoding="utf-8")) == {"ok": 1}
    ponte.salvar("layout", "isto não é json")
    assert ponte.carregar("layout") == '{"ok": 1}'
    ponte.salvar("outro_arquivo", "{}")
    assert not (tmp_path / "web_outro_arquivo.json").exists()
    assert ponte.carregar("outro_arquivo") == ""
    ponte.shutdown()


def test_estado_normaliza_dados_corrompidos(tmp_path):
    _qt()
    app = FakeApp(tmp_path)
    app.drives = SimpleNamespace(energy="sem número", stimulation=2.5)
    app.protest = None
    app.pet_state = SimpleNamespace(emotion=None, tone=None)
    dados = Ponte(app).snapshot()
    assert dados["energia"] == 0
    assert dados["estimulacao"] == 100
    assert dados["insatisfacao"] == 0
    assert dados["atividade"] == 0
    assert isinstance(dados["logs"], list)


def test_pagina_nao_carrega_recursos_externos():
    """Privacidade: nada de fontes, scripts ou imagens vindos da internet."""
    proibido = re.compile(r"""(src|href)\s*=\s*["']https?://|@import\s+(url\()?["']?https?://|fetch\(\s*["']https?://""")
    arquivos = [p for p in WEB_DIR.rglob("*") if p.suffix in {".html", ".css", ".js"}]
    assert arquivos
    achados = [str(p.relative_to(WEB_DIR)) for p in arquivos if proibido.search(p.read_text(encoding="utf-8"))]
    assert achados == []


def test_factory_escolhe_webengine_ou_nativa(tmp_path, monkeypatch):
    _qt()
    app = FakeApp(tmp_path)
    if not web_island.WEB_OK:
        pytest.skip("PySide6-WebEngine não instalado")
    ilha = web_island.criar_ilha(app)
    assert isinstance(ilha, web_island.WebIlha)
    ilha.shutdown()
    ilha.close()
    app.perms["ilha_web"] = False
    monkeypatch.setattr(web_island, "Ilha", lambda a: ("nativa", a))
    assert web_island.criar_ilha(app) == ("nativa", app)


def test_pagina_carrega_com_dois_quadros_e_ponte(tmp_path):
    _qt()
    if not web_island.WEB_OK:
        pytest.skip("PySide6-WebEngine não instalado")
    ilha = web_island.WebIlha(FakeApp(tmp_path))
    ilha.show()
    laco = QEventLoop()
    ilha.view.loadFinished.connect(lambda _ok: laco.quit())
    QTimer.singleShot(15_000, laco.quit)
    laco.exec()
    resultado = {}
    laco2 = QEventLoop()

    def coletar(valor):
        resultado["v"] = valor
        laco2.quit()

    ilha.view.page().runJavaScript("document.querySelectorAll('iframe').length + ':' + typeof QWebChannel", coletar)
    QTimer.singleShot(5_000, laco2.quit)
    laco2.exec()
    assert resultado.get("v") == "2:function"
    ilha.shutdown()
    ilha.close()


def test_posicao_da_pilula_fica_dentro_da_tela():
    from PySide6.QtCore import QRect
    tela = QRect(0, 0, 1920, 1080)
    w, h = 1040, 620
    regiao = QRect(*web_island.REGIAO_INICIAL)            # pílula fechada: (330, 0, 380, 52)
    assert web_island.limitar_posicao(800, 0, tela, w, h, regiao) == (800, 0)
    x, y = web_island.limitar_posicao(-5000, -300, tela, w, h, regiao)
    assert x + regiao.left() == 0 and y == 0              # região encostada na borda esquerda
    x, y = web_island.limitar_posicao(9000, 5000, tela, w, h, regiao)
    assert x + regiao.right() == 1919 and y + regiao.bottom() == 1079
    x, y = web_island.limitar_posicao(1520, 529, tela, w, h, regiao)
    assert 0 <= x + regiao.left() and x + regiao.right() <= 1919


def test_posicao_limita_regiao_larga_do_balao():
    """O balão do narrador alarga a pílula (~940 px): a região inteira fica na tela, não só 380 px."""
    from PySide6.QtCore import QRect
    tela = QRect(0, 0, 1920, 1080)
    w, h = 1040, 620
    regiao = QRect(32, 0, 976, 88)                        # máscara real medida com balão ativo
    x, y = web_island.limitar_posicao(1520, 529, tela, w, h, regiao)
    assert x + regiao.right() == 1919 and x + regiao.left() >= 0


@pytest.mark.skipif(not web_island.WEB_OK, reason="sem QtWebEngine")
def test_posicao_salva_mantem_o_tamanho_cheio_da_janela(tmp_path):
    """Com posição salva a janela só era movida e ficava com 100x30 do Qt: a pílula aparecia cortada."""
    QApplication.instance() or QApplication([])
    (tmp_path / web_island.ARQUIVO_POSICAO).write_text(json.dumps({"x": 600, "y": 300}), encoding="utf-8")
    ilha = web_island.WebIlha(FakeApp(tmp_path))
    assert (ilha.width(), ilha.height()) == web_island.JANELA
    ilha.close()


def test_posicao_topo_centraliza_colada_no_topo():
    from PySide6.QtCore import QRect
    tela = QRect(0, 0, 1920, 1080)
    assert web_island.posicao_topo(tela, 1040) == (440, 0)
    assert web_island.posicao_topo(QRect(1920, 30, 1920, 1080), 1040) == (1920 + 440, 30)


@pytest.mark.skipif(not web_island.WEB_OK, reason="sem QtWebEngine")
def test_pilula_comeca_no_topo_e_desgruda_e_encaixa(tmp_path):
    """Encostada no topo: só sai ao ser puxada para baixo; soltando perto da borda, volta a encostar."""
    QApplication.instance() or QApplication([])
    ilha = web_island.WebIlha(FakeApp(tmp_path))
    assert ilha.modo == "topo" and ilha.y() == 0
    ilha.mover_por(0, 300)                         # encostada: mover não faz nada
    assert ilha.modo == "topo" and ilha.y() == 0
    ilha.desgrudar()
    assert ilha.modo == "livre"
    ilha.mover_por(0, 200)
    assert ilha.y() == 200
    ilha.move(ilha.x(), 10)                        # soltou colada na borda de cima
    ilha.ao_soltar()
    assert ilha.modo == "topo" and ilha.y() == 0
    assert json.loads((tmp_path / web_island.ARQUIVO_POSICAO).read_text(encoding="utf-8"))["modo"] == "topo"
    ilha.desgrudar()
    ilha.move(ilha.x(), 400)
    ilha.ao_soltar()
    assert ilha.modo == "livre"                    # longe do topo: fica onde foi solta
    ilha.close()


@pytest.mark.skipif(not web_island.WEB_OK, reason="sem QtWebEngine")
def test_posicao_salva_livre_volta_livre_e_topo_volta_centralizada(tmp_path):
    QApplication.instance() or QApplication([])
    (tmp_path / web_island.ARQUIVO_POSICAO).write_text(json.dumps({"x": 600, "y": 300, "modo": "livre"}), encoding="utf-8")
    ilha = web_island.WebIlha(FakeApp(tmp_path))
    assert ilha.modo == "livre" and (ilha.x(), ilha.y()) != (440, 0)
    ilha.close()
    (tmp_path / web_island.ARQUIVO_POSICAO).write_text(json.dumps({"x": 600, "y": 300, "modo": "topo"}), encoding="utf-8")
    ilha = web_island.WebIlha(FakeApp(tmp_path))
    assert ilha.modo == "topo" and ilha.y() == 0
    ilha.close()


def test_ponte_entrega_aparencia_do_pet_e_formas_dos_olhos(tmp_path):
    from pestinha.core.emotion import EYE_SHAPES
    _qt()
    dados = json.loads(Ponte(FakeApp(tmp_path)).aparencia_pet())
    assert dados["olhos"] == EYE_SHAPES
    assert set(dados["cores"]) == {"moldura", "casca", "tela", "olho", "brilho"}
    assert dados["acessorios"] == {}


def test_snapshot_traz_a_emocao_como_chave(tmp_path):
    _qt()
    app = FakeApp(tmp_path)
    app.pet_state = SimpleNamespace(emotion="feliz", tone=SimpleNamespace(r={}))
    assert Ponte(app).snapshot()["emocao_chave"] == "feliz"


def test_snapshot_traz_o_carinho_do_pet(tmp_path):
    """O mascote precisa saber quando o pet está com os olhinhos fechados de carinho."""
    _qt()
    app = FakeApp(tmp_path)
    app.pet_state = SimpleNamespace(emotion="contente", tone=None, feliz_fechado=lambda: True)
    assert Ponte(app).snapshot()["carinho"] is True
    app.pet_state = SimpleNamespace(emotion="observando", tone=None)
    assert Ponte(app).snapshot()["carinho"] is False


def test_gesto_do_mascote_entra_pelos_mesmos_caminhos_do_pet(tmp_path):
    """Cutucada, carinho e carinho instantâneo no mascote chamam as ações do pet."""
    _qt()
    app = FakeApp(tmp_path)
    app.on_poke = lambda: app.chamadas.append("cutucada")
    app.menu_caress = lambda: app.chamadas.append("carinho")
    app.on_double_click = lambda: app.chamadas.append("carinho_forte")
    ponte = Ponte(app)
    ponte.mascote_interacao("cutucada")
    ponte.mascote_interacao("carinho")
    ponte.mascote_interacao("carinho_forte")
    ponte.mascote_interacao("desconhecida")
    assert app.chamadas == ["cutucada", "carinho", "carinho_forte"]
    ponte.shutdown()


def test_mascote_liberar_chama_a_saida_do_pet(tmp_path):
    """Arrastar o mascote para fora da ilha chama liberar_da_ilha no app."""
    _qt()
    app = FakeApp(tmp_path)
    app.liberar_da_ilha = lambda: app.chamadas.append("saiu")
    ponte = Ponte(app)
    ponte.mascote_liberar()
    assert app.chamadas == ["saiu"]
    ponte.shutdown()


def test_snapshot_traz_o_modo_um_persona_so(tmp_path):
    """O mascote precisa saber se o modo solo está ligado e se o pet está fora."""
    _qt()
    app = FakeApp(tmp_path)
    app.perms["ilha_solo"] = True
    app._solo_livre = False
    estado = Ponte(app).snapshot()
    assert estado["solo"] is True and estado["solo_livre"] is False
    app._solo_livre = True
    assert Ponte(app).snapshot()["solo_livre"] is True


def test_acao_solo_alterna_a_permissao(tmp_path):
    _qt()
    app = FakeApp(tmp_path)
    app.perms["ilha_solo"] = False
    ponte = Ponte(app)
    ponte.acao("solo", True)
    assert app.perms["ilha_solo"] is True
    ponte.shutdown()


def _js(ilha, codigo):
    """Roda JS na página da ilha e devolve o resultado (espera o carregamento antes)."""
    laco = QEventLoop()
    ilha.view.loadFinished.connect(lambda _ok: laco.quit())
    QTimer.singleShot(15_000, laco.quit)
    laco.exec()
    resultado = {}
    laco2 = QEventLoop()

    def coletar(valor):
        resultado["v"] = valor
        laco2.quit()

    ilha.view.page().runJavaScript(codigo, coletar)
    QTimer.singleShot(5_000, laco2.quit)
    laco2.exec()
    return resultado.get("v")


@pytest.mark.skipif(not web_island.WEB_OK, reason="PySide6-WebEngine não instalado")
def test_clique_em_botao_toca_o_blip(tmp_path):
    """Cada clique em botão, cartão, orbe ou mascote gera o blip de clique (síntese Web Audio, sem arquivo de som)."""
    _qt()
    ilha = web_island.WebIlha(FakeApp(tmp_path))
    ilha.show()
    codigo = """(() => {
        window.__sons = 0;
        const iniciar = OscillatorNode.prototype.start;
        OscillatorNode.prototype.start = function (...a) { window.__sons++; return iniciar.apply(this, a); };
        document.querySelector('button[data-vista="som"]').click();
        document.querySelector('#mascote').click();
        document.querySelector('#gv-marcar') && document.querySelector('#gv-marcar').click();
        return String(window.__sons);
    })()"""
    assert _js(ilha, codigo) == "3"
    ilha.shutdown()
    ilha.close()


@pytest.mark.skipif(not web_island.WEB_OK, reason="PySide6-WebEngine não instalado")
def test_grade_termina_arrasto_quando_o_soltar_se_perde(tmp_path):
    """Se o botão é solto fora da janela, o próximo movimento sem botão encerra o arrasto (sem encaixe preso)."""
    _qt()
    ilha = web_island.WebIlha(FakeApp(tmp_path))
    ilha.show()
    _js(ilha, "document.querySelector('#mascote').click(); document.querySelector('button[data-vista=\"grade\"]').click(); 1")
    espera = QEventLoop()
    QTimer.singleShot(1500, espera.quit)
    espera.exec()
    codigo = """(() => {
        const d = document.querySelector('iframe[data-quadro="parrilla"]').contentDocument;
        const cab = d.querySelector('.pa-w .pa-cab'), r = cab.getBoundingClientRect();
        cab.dispatchEvent(new PointerEvent('pointerdown', { clientX: r.left + 20, clientY: r.top + 10, bubbles: true, button: 0, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
        d.dispatchEvent(new PointerEvent('pointermove', { clientX: r.left + 80, clientY: r.top + 40, buttons: 1, bubbles: true, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
        const preso = d.querySelector('.pa-caja').classList.contains('is-arrastra');
        d.dispatchEvent(new PointerEvent('pointermove', { clientX: r.left + 90, clientY: r.top + 40, buttons: 0, bubbles: true, pointerId: 1, pointerType: 'mouse', isPrimary: true }));
        return preso + ':' + d.querySelector('.pa-caja').classList.contains('is-arrastra');
    })()"""
    assert _js(ilha, codigo) == "true:false"
    ilha.shutdown()
    ilha.close()
