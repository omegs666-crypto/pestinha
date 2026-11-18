"""Ponte entre a ilha em HTML (QWebChannel) e o backend Python.

A página só pode pedir ações de uma lista fixa; não há execução de código vindo da web.
Persistência: apenas os nomes LAYOUT/DIAGRAMA, como JSON validado, em memory/.
Chamadas de rede (Ollama) e áudio rodam em workers; a ponte só troca sinais leves.
"""

import json
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .. import log as log_module
from ..body.desenho_rosto import CAMPOS_DE_COR, PADRAO
from ..config import EMOTION_NAMES
from ..core.emotion import EYE_SHAPES
from ..core.homeostasis import WAKE_ABOVE
from ..mind.chat_voice import ChatVoice
from ..mind.convivencia import ler_persona, prompt_fala
from ..mind.narrador import Narrador, escolher_modelo, limpar_frase, prompt_insight
from ..mind.ollama_local import OllamaLocal
from ..sense import ouvir as ouvir_mod
from ..sense.envelope import envelope_wav
from ..sense.audio import CapturaLoopback

PERSISTIVEIS = {"layout", "diagrama"}
LIMITE_PERSISTENCIA = 200_000
ESTADO_MS = 500
LOGS_A_CADA = 4               # os logs vão junto a cada 2 s: o resto do estado é leve
INSIGHT_MS = 120_000          # o Ollama comenta as métricas a cada 2 min com a ilha visível
FALA_IA_MS = 75_000           # verifica se vale pedir uma fala do pet ao Ollama
INTERVALO_FALA_IA_S = 240.0   # no mínimo 4 min entre falas de IA do pet
PAINEIS = {"neural", "greve", "mlp"}
LIMITE_REGIAO = 4_000


def _percentual(valor):
    """Número do backend como percentual 0–100; qualquer valor ruim vira 0."""
    try:
        return round(min(1.0, max(0.0, float(valor))) * 100)
    except (TypeError, ValueError):
        return 0


class Ponte(QObject):
    """Objeto registrado no QWebChannel como `ponte`."""

    estado = Signal(str)
    regiao = Signal(int, int, int, int)
    movimento = Signal(int, int)
    soltou = Signal()
    aviso = Signal(str)
    narrador_estado = Signal(str)
    niveis = Signal(str)
    audio_estado = Signal(str)
    modelos = Signal(str)
    token = Signal(str)
    chat_fim = Signal()
    erro = Signal(str)
    transcrito = Signal(str)
    voz_estado = Signal(str)
    voz_modelo = Signal(str)        # "pronto", "ausente", "baixando", erro
    voz_download = Signal(int)
    modelo_pull = Signal(str)         # progresso do ollama pull do modelo fixo (JSON)
    envelope = Signal(str)          # volume da fala do LLM ao longo do tempo (para a vibração do chat)
    desgrudou = Signal()            # a pílula saiu do topo (o usuário a puxou para baixo)
    modo_mudou = Signal(str)        # "topo" (encostada) ou "livre"
    gesto = Signal(str)             # interação no pet Qt ("cutucada"|"carinho"|"arremesso") p/ o mascote reagir
    emocao = Signal(str)            # a emoção mudou AGORA (o snapshot de 500 ms chegaria atrasado)
    solo_livre = Signal(bool)       # modo um-persona-só: True = ele saiu da ilha (o mascote some)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.offline = False
        self.modo = "topo"
        self._ultimo_texto = ""
        self._ollama = OllamaLocal(self)
        self._voz = ChatVoice(self)
        self._captura = None
        self._timer = QTimer(self)
        self._timer.setInterval(ESTADO_MS)
        self._timer.timeout.connect(self._emitir_estado)
        self._ollama.models_ready.connect(lambda nomes: self.modelos.emit(json.dumps(list(nomes))))
        self._ollama.token.connect(self.token)
        self._ollama.chat_finished.connect(self.chat_fim)
        self._ollama.error.connect(self.erro)
        self._ollama.response_limited.connect(lambda: self.erro("Resposta longa demais: o texto foi limitado."))
        self._ollama.speech_ready.connect(self._envelope_fala)      # antes de tocar: a vibração começa junto com o som
        self._ollama.speech_ready.connect(self._voz.play_wav)
        self._ollama.speech_failed.connect(self._voz_do_sistema)
        self._ollama.pull_progress.connect(
            lambda d: self.modelo_pull.emit(json.dumps(d)))
        self._ollama.pull_finished.connect(self._modelo_baixado)
        self._voz.transcribed.connect(self.transcrito)
        self._voz.error.connect(self.erro)
        self._voz.activity_changed.connect(self.voz_estado)
        # narrador: regras locais a cada estado + insight do Ollama num cliente separado do chat
        self._narrador = Narrador()
        self.narrador_ligado = True
        self._modelos = []
        self._modelo_preferido = ""
        self._insight = ""
        self._pedindo_insight = False
        self._falhou_insight = False
        self._ollama_narrador = OllamaLocal(self)
        self._ollama_narrador.token.connect(self._insight_token)
        self._ollama_narrador.chat_finished.connect(self._insight_fim)
        self._ollama_narrador.error.connect(self._insight_erro)
        self._ollama.models_ready.connect(self._guardar_modelos)
        self._timer_insight = QTimer(self)
        self._timer_insight.setInterval(INSIGHT_MS)
        self._timer_insight.timeout.connect(self.pedir_insight)
        # falas do pet geradas pelo Ollama local (cliente próprio, em worker)
        self._contador = 0
        self._pedindo_fala = False
        self._fala_ia = ""
        self._ultima_fala_ia = -1e9
        self._ollama_falas = OllamaLocal(self)
        self._ollama_falas.token.connect(self._falas_token)
        self._ollama_falas.chat_finished.connect(self._falas_fim)
        self._ollama_falas.error.connect(self._falas_erro)
        self._timer_falas = QTimer(self)
        self._timer_falas.setInterval(FALA_IA_MS)
        self._timer_falas.timeout.connect(self.pedir_fala_ia)

    # ----- ciclo de vida -----
    def iniciar(self):
        self._timer.start()
        self._timer_insight.start()
        self._timer_falas.start()
        self._emitir_estado()

    def parar(self):
        self._timer.stop()
        self._timer_insight.stop()
        self._timer_falas.stop()

    def shutdown(self):
        """Encerra workers de rede, voz e áudio ao fechar a ilha."""
        self.parar()
        self.audio(False)
        self._ollama.shutdown()
        self._ollama_narrador.shutdown()
        self._ollama_falas.shutdown()
        self._voz.shutdown()
        for nome in ("_ouvinte", "_baixador"):
            tarefa = getattr(self, nome, None)
            if tarefa is not None and tarefa.isRunning():
                tarefa.requestInterruption()
                tarefa.wait(1500)

    # ----- falas do pet (balões) -----
    def anunciar(self, texto, tom="calmo", origem="pet"):
        """Um balão do pet (ou da IA dele) no topo da ilha. Não bloqueia: só emite o sinal."""
        self.aviso.emit(json.dumps({"texto": str(texto)[:160], "tom": tom, "origem": origem}, ensure_ascii=False))

    @Slot()
    def pedir_fala_ia(self):
        """Pede ao Ollama uma fala do pet no jeito dele, com o que ele lembra de você (worker)."""
        app = self.app
        if not app.reacoes.ia or self.offline or self._pedindo_fala or app.paused or not app.pet.isVisible():
            return
        agora = time.monotonic()
        modelo = escolher_modelo(self._modelos, self._modelo_preferido)
        if not modelo or agora - self._ultima_fala_ia < INTERVALO_FALA_IA_S:
            return
        self._pedindo_fala = True
        self._fala_ia = ""
        self._ultima_fala_ia = agora
        mensagens = prompt_fala(app.nome, ler_persona(app.conteudo.proprio), self.snapshot()["emocao"].lower(),
                                app.convivencia.fatos(), app.voz.exemplos(8))
        self._ollama_falas.chat_stream_async(modelo, mensagens)

    def _falas_token(self, pedaco):
        self._fala_ia = (self._fala_ia + pedaco)[-2_000:]

    def _falas_fim(self):
        texto = limpar_frase(self._fala_ia)
        self._pedindo_fala = False
        self._fala_ia = ""
        if texto:
            self.app.falar_pet(texto, "calmo", "ollama")

    def _falas_erro(self, mensagem):
        self._pedindo_fala = False
        self._fala_ia = ""
        log_module.log(f"[falas] Ollama não respondeu ao pet: {mensagem}")

    # ----- janela: a página informa a área visível (o resto deixa o clique passar) -----
    @Slot(int, int)
    def arrastar(self, dx, dy):
        """A barra foi arrastada: a janela acompanha o mouse (limites aplicados pela janela)."""
        self.movimento.emit(max(-4000, min(4000, int(dx))), max(-4000, min(4000, int(dy))))

    @Slot()
    def soltar(self):
        self.soltou.emit()

    @Slot()
    def desgrudar(self):
        self.desgrudou.emit()

    @Slot(result=str)
    def modo_inicial(self):
        return self.modo

    def definir_modo(self, modo):
        self.modo = modo
        self.modo_mudou.emit(modo)

    @Slot(result=str)
    def aparencia_pet(self):
        """Cores do rosto do pet e a forma dos olhos por emoção (mesma fonte do desenho Qt)."""
        ap = getattr(getattr(self.app, "pet", None), "aparencia", None) or PADRAO
        return json.dumps({
            "cores": {campo: getattr(ap, campo).name() for campo in CAMPOS_DE_COR},
            "acessorios": {nome: cor.name() for nome, cor in ap.acessorios},
            "bracos": ap.bracos.name() if ap.bracos else None,
            "olhos": EYE_SHAPES,
        })

    @Slot(str)
    def mascote_interacao(self, acao):
        """O mascote da ilha é o mesmo pet: o gesto dele entra pelos mesmos caminhos do pet Qt."""
        alvo = {"cutucada": "on_poke", "carinho": "menu_caress", "carinho_forte": "on_double_click"}.get(acao)
        fn = getattr(self.app, alvo or "", None)
        if fn:
            fn()

    @Slot(str)
    def jslog(self, texto):
        """Depuração: mensagens do JS da ilha vão para o log (descobrir por que um gesto não pega)."""
        log_module.log(f"[ilha-js] {str(texto)[:200]}")

    @Slot()
    def mascote_liberar(self):
        """Você puxou o mascote para fora da ilha (modo um-persona-só): ele aparece na tela."""
        fn = getattr(self.app, "liberar_da_ilha", None)
        log_module.log(f"[solo] mascote_liberar recebido; app tem liberar_da_ilha={fn is not None}")
        if fn:
            fn()

    # ----- aba Cérebro: a memória dele como grafo (estilo Obsidian) -----

    # rótulos amigáveis das pistas do condicionamento; quantos episódios recentes entram no grafo
    ROTULOS_PISTA = {"PRESS": "pressão no corpo", "APPROACH": "você por perto", "PLACA": "placa do castigo"}
    EPISODIOS_NO_GRAFO = 14

    @Slot(result=str)
    def grafo(self):
        """Mapa da memória do pet (nós + arestas em JSON) — o "cérebro" visível na aba Cérebro."""
        try:
            dados = self._grafo_memoria()
        except Exception as error:            # memória corrompida não derruba a ilha
            log_module.log(f"[ilha-web] grafo indisponível: {error}")
            dados = {"nos": [], "arestas": []}
        return json.dumps(dados, ensure_ascii=False)

    def _grafo_memoria(self):
        """Junta episódios, aprendizado por contexto, pistas e drives num grafo só.

        Nós: pet (centro), emocao, acao, contexto (atividade), episodio, drive e pista.
        Arestas: episódio→o que envolveu; contexto→ação com a valência aprendida; pistas e drives→pet.
        """
        app = self.app
        memoria = getattr(app, "memory", None)
        drives = getattr(app, "drives", None)
        condicionamento = getattr(app, "conditioning", None)
        estado = getattr(app, "pet_state", None)
        nome = str(getattr(app, "nome", "Pestinha"))[:40]
        emocao = str(getattr(estado, "emotion", "observando") or "observando")[:40]

        nos, arestas, idx = [], [], {}

        def no(id_, tipo, rotulo, **extra):
            """Cria o nó uma vez; chamadas seguintes só acumulam peso/extras."""
            existente = idx.get(id_)
            if existente is not None:
                existente["peso"] = existente.get("peso", 0) + extra.pop("peso", 0)
                existente.update(extra)
                return existente
            n = {"id": id_, "tipo": tipo, "rotulo": rotulo}
            n.update(extra)
            idx[id_] = n
            nos.append(n)
            return n

        def aresta(de, para, **extra):
            arestas.append({"de": de, "para": para, **extra})

        # centro: o pet e como ele está agora
        no("pet", "pet", nome, extra=emocao)
        if drives is not None:
            for chave, rotulo in (("energy", "energia"), ("stimulation", "estímulo"), ("contact", "carinho")):
                valor = _percentual(getattr(drives, chave, 0.0)) / 100
                no(f"drive:{chave}", "drive", rotulo, valor=round(valor, 2))
                aresta("pet", f"drive:{chave}", peso=round(valor, 2))
        no(f"emo:{emocao}", "emocao", emocao, peso=1, agora=True)
        aresta("pet", f"emo:{emocao}", peso=1.0)

        # memória episódica: cada lembrança liga ação + emoção + atividade daquele momento;
        # dormindo, elas se fundem em conceitos por emoção — ele "sonha organizando"
        if memoria is not None:
            episodios = list(getattr(memoria, "recent", []))[-self.EPISODIOS_NO_GRAFO:]
            if getattr(app, "asleep", False) and episodios:
                grupos = {}
                for ep in episodios:
                    _, _, emo_ep = str(ep.get("contexto", "")).partition("|")
                    grupos.setdefault(emo_ep or "calmo", []).append(str(ep.get("acao", "?"))[:24])
                for emo_ep, acoes in grupos.items():
                    cid = f"sonho:{emo_ep}"
                    no(cid, "conceito", f"{len(acoes)} lembranças {emo_ep}", peso=len(acoes), sonho=True)
                    no(f"emo:{emo_ep}", "emocao", emo_ep, peso=1)
                    aresta(cid, f"emo:{emo_ep}", peso=1.0)
                    for acao in sorted(set(acoes)):
                        no(f"acao:{acao}", "acao", acao, peso=1)
                        aresta(cid, f"acao:{acao}", peso=0.5)
            else:
                for ep in episodios:
                    ctx = str(ep.get("contexto", ""))
                    atividade, _, emo_ep = ctx.partition("|")
                    acao = str(ep.get("acao", "?"))[:24]
                    ep_id = f"ep:{ep.get('id') or ep.get('quando', '?')}"
                    no(ep_id, "episodio", acao, quando=str(ep.get("quando", ""))[:19],
                       resultado=str(ep.get("resultado", ""))[:40], valencia=float(ep.get("valencia", 0.0)))
                    no(f"acao:{acao}", "acao", acao, peso=1)
                    aresta(ep_id, f"acao:{acao}", peso=abs(float(ep.get("valencia", 0.0))), valencia=float(ep.get("valencia", 0.0)))
                    if emo_ep:
                        no(f"emo:{emo_ep}", "emocao", emo_ep, peso=1)
                        aresta(ep_id, f"emo:{emo_ep}", peso=0.6)
                    if atividade:
                        no(f"ctx:{atividade}", "contexto", atividade.lower(), peso=1)
                        aresta(ep_id, f"ctx:{atividade}", peso=0.5)

            # o que ele aprendeu por contexto: a força da linha é a valência média da ação ali
            for ctx, acoes in (getattr(memoria, "table", None) or {}).items():
                if not isinstance(acoes, dict):
                    continue
                atividade, _, emo_ctx = str(ctx).partition("|")
                if atividade:
                    no(f"ctx:{atividade}", "contexto", atividade.lower(), peso=0)
                for acao, stats in acoes.items():
                    if not isinstance(stats, (list, tuple)) or len(stats) < 2 or not stats[0]:
                        continue
                    no(f"acao:{acao}", "acao", acao, peso=0)
                    if atividade:
                        aresta(f"ctx:{atividade}", f"acao:{acao}", peso=abs(float(stats[1])), valencia=float(stats[1]))
                    if emo_ctx:
                        aresta(f"emo:{emo_ctx}", f"acao:{acao}", peso=0.3)

        # pistas do condicionamento: o que ele aprendeu a esperar de você
        for pista, forca in (getattr(condicionamento, "V", None) or {}).items():
            no(f"pista:{pista}", "pista", self.ROTULOS_PISTA.get(pista, str(pista).lower()), forca=round(float(forca), 2))
            aresta("pet", f"pista:{pista}", peso=abs(float(forca)), valencia=float(forca))

        # você: o que ele lembra da convivência — as interações mais vividas penduradas em você
        conv = getattr(app, "convivencia", None)
        if conv is not None:
            no("voce", "voce", "você")
            aresta("pet", "voce", peso=1.4)
            for evento, qtd in sorted((getattr(conv, "contagens", None) or {}).items(),
                                      key=lambda kv: -kv[1])[:5]:
                no(f"conta:{evento}", "conta", f"{evento} ×{int(qtd)}", peso=1)
                aresta("voce", f"conta:{evento}", peso=min(1.5, qtd / 20))
            # os pontos são lembranças das suas interações: frases que ele aprendeu
            # ligadas a você, com a valência do que ele sentiu — enche o cérebro
            # mesmo antes das primeiras travessuras (episodes.jsonl)
            for i, (frase, pontos) in enumerate(sorted((getattr(conv, "pontos", None) or {}).items(),
                                                     key=lambda kv: -abs(kv[1]))[:12]):
                val = max(-1.0, min(1.0, float(pontos) / 5))
                no(f"ponto:{i}", "episodio", frase[:34], quando="", resultado="convivência",
                   valencia=val)
                aresta(f"ponto:{i}", "voce", peso=abs(val), valencia=val)

        return {"pet": nome, "emocao": emocao, "dormindo": bool(getattr(app, "asleep", False)),
                "nos": nos, "arestas": arestas}

    # frases dele quando você cutuca um pedaço do próprio cérebro
    def _fala_do_no(self, n):
        tipo, rotulo = n.get("tipo", ""), n.get("rotulo", "?")
        if tipo == "pet":
            return "sou eu! o centro de tudo isso aqui."
        if tipo == "voce":
            return "você! a parte favorita do meu mapa."
        if tipo == "episodio":
            sinal = "deu certo" if (n.get("valencia") or 0) > 0 else "deu ruim"
            return f"aquela vez que eu fiz '{rotulo}'… {sinal} ({n.get('resultado', '')})."
        if tipo == "emocao":
            return f"'{rotulo}'… quando eu tô assim, é por isso que as coisas ligam desse jeito."
        if tipo == "acao":
            return f"'{rotulo}' — eu lembro de todas as vezes que tentei isso."
        if tipo == "contexto":
            return f"quando você tá em '{rotulo}', eu já sei mais ou menos o que esperar."
        if tipo == "drive":
            return f"minha {rotulo} tá em {round((n.get('valor') or 0) * 100)}% agora."
        if tipo == "pista":
            return f"aprendi que '{rotulo}' quer dizer alguma coisa… tô sempre de olho."
        if tipo == "conta":
            return f"'{rotulo}' — a gente já viveu bastante isso juntos."
        if tipo == "conceito":
            return "shhh… tô sonhando com isso agora. as lembranças tão se juntando."
        return f"'{rotulo}'."

    @Slot(str)
    def cutucar_no(self, no_id):
        """Você cutucou um nó do cérebro dele: ele comenta o que aquele pedaço significa."""
        try:
            dados = self._grafo_memoria()
        except Exception:
            return
        alvo = next((n for n in dados.get("nos", []) if n.get("id") == no_id), None)
        if alvo:
            self.aviso.emit(json.dumps({"texto": self._fala_do_no(alvo)[:160], "tom": "calmo",
                                        "origem": "pet"}, ensure_ascii=False))

    @Slot(int, int, int, int)
    def definir_regiao(self, x, y, largura, altura):
        def lim(v):
            return max(0, min(LIMITE_REGIAO, int(v)))
        self.regiao.emit(lim(x), lim(y), max(1, lim(largura)), max(1, lim(altura)))

    # ----- narrador -----
    def _guardar_modelos(self, nomes):
        self._modelos = [str(n) for n in nomes][:256]

    @Slot(str)
    def definir_modelo(self, nome):
        """Modelo escolhido no chat; o narrador o usa se ele for local."""
        self._modelo_preferido = str(nome)[:200]

    @Slot(str)
    def baixar_modelo(self, nome):
        """Baixa o modelo fixo do chat pelo /api/pull (a ilha mostra o progresso)."""
        nome = "".join(c for c in str(nome) if c.isalnum() or c in ":.-_/")[:200]
        if not nome:
            return
        self._ollama.pull_async(nome)

    def _modelo_baixado(self):
        self.modelo_pull.emit(json.dumps({"status": "pronto", "pct": 100}))
        self._ollama.list_models_async()   # a lista se refresca e o chat pega o modelo novo

    @Slot(bool)
    def ligar_narrador(self, ligado):
        self.narrador_ligado = bool(ligado)

    @Slot()
    def pedir_insight(self):
        """Pede ao Ollama uma frase sobre as métricas atuais (worker; a UI não espera)."""
        if not self.narrador_ligado or self.offline or self._pedindo_insight:
            return
        modelo = escolher_modelo(self._modelos, self._modelo_preferido)
        if not modelo:
            return
        self._pedindo_insight = True
        self._insight = ""
        self.narrador_estado.emit("pensando")
        self._ollama_narrador.chat_stream_async(modelo, prompt_insight(self.snapshot(), getattr(self.app, "nome", "Pestinha")))

    def _insight_token(self, pedaco):
        self._insight = (self._insight + pedaco)[-2_000:]

    def _insight_fim(self):
        texto = limpar_frase(self._insight)
        self._pedindo_insight = False
        self._insight = ""
        self.narrador_estado.emit("pronto")
        if texto:
            self._falhou_insight = False
            # com a mente ligada, o insight é do Jorge; desligada, é a IA genérica
            origem = "jorge" if self.app.perms.get("mente_llm", True) else "ollama"
            self.aviso.emit(json.dumps({"texto": texto, "tom": "insight", "origem": origem}, ensure_ascii=False))

    def _insight_erro(self, mensagem):
        self._pedindo_insight = False
        self.narrador_estado.emit("erro")
        if not self._falhou_insight:
            self._falhou_insight = True
            self.aviso.emit(json.dumps({"texto": "Não consegui falar com o Ollama agora.", "tom": "alerta",
                                        "origem": "sistema"}, ensure_ascii=False))
            log_module.log(f"[narrador] {mensagem}")

    # ----- estado do backend (somente leitura) -----
    def snapshot(self, logs=True):
        drives = getattr(self.app, "drives", None)
        estado = getattr(self.app, "pet_state", None)
        emocao = getattr(estado, "emotion", None)
        taxas = getattr(getattr(estado, "tone", None), "r", {})
        valores = taxas.values() if isinstance(taxas, dict) else (taxas if isinstance(taxas, (list, tuple)) else [])
        atividade = max((_percentual(v) for v in valores if isinstance(v, (int, float))), default=0)
        # modo um-persona-só: descansando na ilha, o mascote mostra o soninho até recarregar
        emocao_chave = str(emocao or "observando")[:40]
        descansando = (self.app.perms.get("ilha_solo") and not getattr(self.app, "_solo_livre", True)
                       and getattr(drives, "energy", 1.0) < WAKE_ABOVE)
        return {
            "pet": str(getattr(self.app, "nome", "Pestinha"))[:60],
            "emocao": str(EMOTION_NAMES.get(emocao, emocao))[:40],
            "emocao_chave": "dormindo" if descansando else emocao_chave,
            "energia": _percentual(getattr(drives, "energy", 0.0)),
            "estimulacao": _percentual(getattr(drives, "stimulation", 0.0)),
            "insatisfacao": _percentual(getattr(getattr(self.app, "protest", None), "grievance", 0.0)),
            "atividade": atividade,
            "carinho": bool(getattr(estado, "feliz_fechado", lambda *a: False)()) if estado else False,
            "solo": bool(self.app.perms.get("ilha_solo")),
            "solo_livre": bool(getattr(self.app, "_solo_livre", False)),
            "mente": str((getattr(self.app, "mente", None) or {}).get("nome") or "")[:40]
                     if self.app.perms.get("mente_llm", True) else "",
            "mente_llm": bool(self.app.perms.get("mente_llm", True)),
            "pausado": bool(getattr(self.app, "paused", False)),
            "voz": bool(self.app.perms.get("voz")),
            "travessuras": bool(self.app.perms.get("travessuras")),
            "ia_arquivos": bool(self.app.perms.get("ia_arquivos", True)),
            "offline": self.offline,
            "processando": atividade >= 60 or self._treinando(),
            "logs": [str(linha)[:300] for linha in log_module.recent(40)] if logs else None,
        }

    def _treinando(self):
        """Laboratório MLP com treino em andamento (thread secundária)."""
        janelas = getattr(getattr(self.app, "floats", None), "windows", None)
        lab = janelas.get("mlp") if isinstance(janelas, dict) else None
        return getattr(lab, "_treino_task", None) is not None

    def _emitir_estado(self):
        try:
            self._contador += 1
            dados = self.snapshot(logs=self._contador % LOGS_A_CADA == 0)
            self.estado.emit(json.dumps(dados, ensure_ascii=False))
            if self.narrador_ligado:
                fala = self._narrador.observar(dados, time.monotonic())
                if fala:
                    self.aviso.emit(json.dumps(fala, ensure_ascii=False))
        except Exception as error:  # dado corrompido no backend não derruba a ilha
            log_module.log(f"[ilha-web] estado indisponível: {error}")

    @Slot(result=str)
    def obter_estado(self):
        return json.dumps(self.snapshot(), ensure_ascii=False)

    @Slot(result=str)
    def mente_dados(self):
        """Nome + aparência da mente (Jorge), para o mini-mascote e o rótulo no chat."""
        mente = getattr(self.app, "mente", None) or {}
        return json.dumps({"nome": str(mente.get("nome") or "Jorge")[:40],
                           "aparencia": mente.get("aparencia") or {}}, ensure_ascii=False)

    # ----- ações permitidas -----
    @Slot(str, bool)
    def acao(self, nome, valor):
        """Executa uma ação da lista permitida; nomes desconhecidos são ignorados."""
        if nome == "pausa":
            self.app.toggle_pause()
        elif nome == "concentracion" and bool(self.app.paused) != bool(valor):
            self.app.toggle_pause()
        elif nome == "voz":
            self.app.apply_perms({"voz": not self.app.perms.get("voz")})
        elif nome == "travessuras":
            self.app.apply_perms({"travessuras": not self.app.perms.get("travessuras")})
        elif nome == "solo":
            self.app.apply_perms({"ilha_solo": not self.app.perms.get("ilha_solo")})
        elif nome == "mente":
            self.app.apply_perms({"mente_llm": not self.app.perms.get("mente_llm", True)})
        elif nome == "arquivos":
            self.app.apply_perms({"ia_arquivos": not self.app.perms.get("ia_arquivos", True)})
        elif nome == "avion":
            self.offline = bool(valor)
            if self.offline:
                self._ollama.cancel_chat()
        self._emitir_estado()

    @Slot(str)
    def painel(self, chave):
        if chave in PAINEIS:
            self.app.floats.toggle(chave)

    # ----- persistência (layout da Parrilla e diagrama do Eslabón) -----
    def _arquivo(self, nome):
        return Path(self.app.paths.memory) / f"web_{nome}.json"

    @Slot(str, str)
    def salvar(self, nome, dados):
        if nome == "reacoes" and isinstance(dados, str) and len(dados) <= LIMITE_PERSISTENCIA:
            try:
                self.app.reacoes.definir(json.loads(dados), salvar=True)
            except ValueError:
                log_module.log("[reações] JSON inválido recebido da interface")
            return
        if nome not in PERSISTIVEIS or not isinstance(dados, str) or len(dados) > LIMITE_PERSISTENCIA:
            return
        try:
            json.loads(dados)
            self._arquivo(nome).write_text(dados, encoding="utf-8")
        except (ValueError, OSError) as error:
            log_module.log(f"[ilha-web] não salvou {nome}: {error}")

    @Slot(str, result=str)
    def carregar(self, nome):
        if nome == "reacoes":
            return json.dumps(self.app.reacoes.exportar(), ensure_ascii=False)
        if nome not in PERSISTIVEIS:
            return ""
        try:
            texto = self._arquivo(nome).read_text(encoding="utf-8")
            json.loads(texto)
            return texto
        except (OSError, ValueError):
            return ""

    # ----- chat local (Ollama) -----
    @Slot()
    def listar_modelos(self):
        self._ollama.list_models_async()

    @Slot(str, str)
    def enviar_chat(self, modelo, mensagens):
        if self.offline:
            self.erro.emit("Modo avião ativo: o chat local está desligado.")
            self.chat_fim.emit()
            return
        try:
            lista = json.loads(mensagens)
        except ValueError:
            self.erro.emit("Mensagem inválida.")
            self.chat_fim.emit()
            return
        if not isinstance(lista, list):
            lista = []
        # a mente responde: system com a persona dela entra aqui, no servidor —
        # o JS não precisa saber da persona e nunca a duplica
        mente = getattr(self.app, "mente", None) or {}
        if self.app.perms.get("mente_llm", True) and mente:
            nome = str(mente.get("nome") or "Jorge")[:40]
            persona = str(mente.get("persona") or "")[:800]
            sistema = {"role": "system", "content":
                       f"Você é {nome}, a mente do Pestinha — o lado que pensa e explica. "
                       f"{persona} Responda em português do Brasil."
                       + (" Quando precisar entregar um arquivo, responda com um bloco "
                          "```arquivo:nome.ext``` contendo o conteúdo completo — o chat o "
                          "oferece para download."
                          if self.app.perms.get("ia_arquivos", True) else "")}
            lista = [sistema] + [m for m in lista
                                 if not (isinstance(m, dict) and m.get("role") == "system")]
        self._ollama.chat_stream_async(modelo, lista)

    @Slot()
    def cancelar_chat(self):
        self._ollama.cancel_chat()

    @Slot(str, str)
    def falar_resposta(self, modelo, texto):
        """Voz do próprio LLM (/v1/audio/speech); sem ela, cai na voz do sistema."""
        self._ultimo_texto = str(texto)[:2_000]
        candidatos = [m for m in self._modelos if m != modelo]   # outro modelo instalado pode ter voz (ex.: lfm3-omni)
        if modelo or candidatos:
            self._ollama.speak_async(modelo or candidatos[0], self._ultimo_texto, candidatos)
        else:
            self._voz.speak(self._ultimo_texto)

    def _envelope_fala(self, dados):
        env = envelope_wav(bytes(dados))
        if env:
            self.envelope.emit(json.dumps(env))

    def _voz_do_sistema(self, _mensagem):
        """Falha da voz do LLM: fala o último texto com a voz do sistema, sem travar o chat."""
        self.erro.emit("Voz do modelo indisponível; usando a voz do sistema.")
        if self._ultimo_texto:
            self._voz.speak(self._ultimo_texto)

    # ----- arquivos gerados pela IA -----
    _MAX_ARQUIVO = 2_000_000

    def _aviso_sistema(self, texto):
        self.aviso.emit(json.dumps({"texto": texto, "origem": "sistema", "tom": "calmo"}))

    def _gravar_arquivo(self, alvo, conteudo):
        try:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(str(conteudo)[: self._MAX_ARQUIVO], encoding="utf-8")
        except OSError as error:
            self._aviso_sistema(f"Não consegui salvar o arquivo: {error}")
            return
        self._aviso_sistema(f"Arquivo salvo em {alvo}")

    @Slot(str, str)
    def salvar_arquivo(self, nome, conteudo):
        """Baixa direto em ~/Downloads/Pestinha/ (sem diálogo), nome desduplicado."""
        if not self.app.perms.get("ia_arquivos", True):
            return
        nome = Path(str(nome)).name or "arquivo.txt"
        pasta = Path.home() / "Downloads" / "Pestinha"
        alvo = pasta / nome
        for i in range(1, 100):
            if not alvo.exists():
                break
            alvo = pasta / f"{alvo.stem}-{i}{alvo.suffix}"
        self._gravar_arquivo(alvo, conteudo)

    @Slot(str, str)
    def salvar_arquivo_como(self, nome, conteudo):
        """'Salvar como…': diálogo nativo para escolher onde o arquivo vai parar."""
        if not self.app.perms.get("ia_arquivos", True):
            return
        from PySide6.QtWidgets import QFileDialog
        nome = Path(str(nome)).name or "arquivo.txt"
        inicial = str(Path.home() / "Downloads" / "Pestinha" / nome)
        destino, _ = QFileDialog.getSaveFileName(None, "Salvar arquivo criado pela IA", inicial)
        if destino:
            self._gravar_arquivo(Path(destino), conteudo)

    # ----- voz de entrada -----
    @Slot()
    def ouvir(self):
        """Ouve uma fala pelo microfone e transcreve com o Parakeet local (como o Coucou)."""
        if not ouvir_mod.pronto():
            self.voz_modelo.emit("ausente")
            return
        if getattr(self, "_ouvinte", None) is not None and self._ouvinte.isRunning():
            self._ouvinte.requestInterruption()
            return
        self._ouvinte = ouvir_mod.Ouvinte(self)
        self._ouvinte.estado.connect(self.voz_estado)
        self._ouvinte.transcrito.connect(self.transcrito)
        self._ouvinte.erro.connect(self.erro)
        self._ouvinte.start()

    @Slot(result=str)
    def estado_modelo_voz(self):
        return json.dumps({"pronto": ouvir_mod.pronto(), "tamanho_mb": ouvir_mod.TAMANHO_MB})

    @Slot()
    def baixar_modelo_voz(self):
        """Baixa o Parakeet (~670 MB) só quando você pede; o progresso vai para a ilha."""
        if getattr(self, "_baixador", None) is not None and self._baixador.isRunning():
            return
        self._baixador = ouvir_mod.Baixador(self)
        self._baixador.progresso.connect(self.voz_download)
        self._baixador.concluido.connect(lambda: self.voz_modelo.emit("pronto"))
        self._baixador.erro.connect(self.voz_modelo)
        self.voz_modelo.emit("baixando")
        self._baixador.start()

    # ----- áudio do sistema (loopback) -----
    @Slot(bool)
    def audio(self, ligado):
        if ligado and self._captura is None:
            self._captura = CapturaLoopback(self)
            self._captura.niveis.connect(lambda dados: self.niveis.emit(json.dumps(dados)))
            self._captura.conectado.connect(lambda: self.audio_estado.emit("ativo"))
            self._captura.erro.connect(self.audio_estado)
            self._captura.finished.connect(lambda: self.audio_estado.emit("parado"))
            self._captura.start()
            self.audio_estado.emit("conectando")
        elif not ligado and self._captura is not None:
            captura, self._captura = self._captura, None
            captura.requestInterruption()
            captura.wait(1500)
            self.audio_estado.emit("parado")
