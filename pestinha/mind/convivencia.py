"""
CONVIVÊNCIA - o que o pet lembra de você e o que aprende com isso.

Três partes, todas locais:
- Memória por pet (memory/pets/<pet>/convivencia.json): quantas vezes você cutucou, deu carinho,
  dispensou travessuras, arremessou ou prendeu o pet. Vira fato em texto para o Ollama.
- Aprendizado de falas: cada fala mostrada ganha ponto se você reagir logo depois (cutucar ou
  carinho) e perde um pouco se for ignorada. Falas que você responde saem mais vezes.
- Reações configuradas (memory/pets/<pet>/reacoes.json, aba Diagramas): gatilho -> fala inicial ->
  espera -> se você reagir, fala e ação A; se não, fala e ação B.

Nada disso sai do PC. As falas de IA são pedidas ao Ollama local pela ponte, em worker.
"""

from ..config import EMOTION_NAMES
from ..log import log
from ..store import read_json, write_json

JANELA_REACAO_S = 30.0       # depois disso, uma fala mostrada conta como ignorada
BALAO_INTERVALO_S = 25.0     # no mínimo entre dois balões espontâneos do pet
PONTOS_MIN, PONTOS_MAX = -5.0, 5.0
PESO_MIN, PESO_MAX = 0.3, 3.0
MAX_FALAS = 500
MAX_REGRAS = 30
MAX_TEXTO = 160
ESPERA_PADRAO, ESPERA_MIN, ESPERA_MAX = 20.0, 5.0, 120.0
EVENTOS = {
    "preso": "Preso no cantinho", "fuga": "Fugiu do cantinho", "notebook": "Sentou no notebook",
    "arremesso": "Foi arremessado", "dispensa": "Você dispensou uma travessura",
}
GATILHOS = {**{chave: nome.capitalize() for chave, nome in EMOTION_NAMES.items()}, **EVENTOS}
ACOES = {"falar": "Fala no balão", "falar_voz": "Fala no balão e em voz",
         "carinho": "Fica feliz", "nada": "Não faz nada"}
TONS = ("calmo", "alerta")
FATOS = {"cutucada": "cutucadas", "carinho": "carinhos", "dispensa": "travessuras que você dispensou",
         "arremesso": "arremessos", "preso": "vezes que você o prendeu no cantinho",
         "fuga": "fugas do cantinho", "notebook": "vezes que ele sentou para trabalhar"}

PADRAO = {"ia": True, "regras": [
    {"id": "preso-ignorado", "gatilho": "preso", "ativa": True, "texto": "me tira daqui!", "tom": "alerta",
     "voz": False, "espera": 20,
     "sim": {"texto": "obrigado por olhar pra mim...", "acao": "carinho"},
     "nao": {"texto": "ninguém me quer aqui dentro", "acao": "falar"}},
    {"id": "bravo-ignorado", "gatilho": "bravo", "ativa": True, "texto": "", "tom": "alerta",
     "voz": False, "espera": 25,
     "sim": {"texto": "ok, ok, paz!", "acao": "falar"},
     "nao": {"texto": "tá me ignorando, né?", "acao": "falar_voz"}},
]}


def _dict(valor):
    return valor if isinstance(valor, dict) else {}


def _texto(valor, limite=MAX_TEXTO):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def _ramo(bruto):
    bruto = _dict(bruto)
    acao = bruto.get("acao") if bruto.get("acao") in ACOES else "nada"
    return {"texto": _texto(bruto.get("texto")), "acao": acao}


def normalizar_regras(bruto):
    """Só regras bem formadas entram. Um arquivo editado à mão com erro não derruba o app."""
    out, ids = [], set()
    for i, regra in enumerate(bruto if isinstance(bruto, list) else []):
        if len(out) >= MAX_REGRAS:
            break
        if not isinstance(regra, dict) or regra.get("gatilho") not in GATILHOS:
            continue
        rid = _texto(str(regra.get("id") or ""), 40) or f"regra-{i}"
        rid = rid if rid not in ids else f"{rid}-{i}"
        ids.add(rid)
        espera = regra.get("espera", ESPERA_PADRAO)
        espera = float(espera) if type(espera) in (int, float) and espera == espera else ESPERA_PADRAO
        out.append({
            "id": rid, "gatilho": regra["gatilho"], "ativa": regra.get("ativa") is not False,
            "texto": _texto(regra.get("texto")),
            "tom": regra.get("tom") if regra.get("tom") in TONS else "calmo",
            "voz": regra.get("voz") is True,
            "espera": min(ESPERA_MAX, max(ESPERA_MIN, espera)),
            "sim": _ramo(regra.get("sim")), "nao": _ramo(regra.get("nao")),
        })
    return out


class Convivencia:
    """Memória de convivência de um pet: contagens de interação e o que você costuma responder."""

    def __init__(self, path):
        self.path = path
        self.contagens = {}
        self.pontos = {}          # fala -> pontos de aprendizado
        self._mostradas = []      # [(fala, quando)] esperando a sua reação
        self._sujo = False        # muda na memória: o save() do app grava (respeita 'apagar tudo')

    def load(self):
        dados = _dict(read_json(self.path, default=None))
        self.contagens = {k: v for k, v in _dict(dados.get("contagens")).items()
                          if isinstance(k, str) and type(v) is int and 0 <= v < 10 ** 9}
        self.pontos = {k: min(PONTOS_MAX, max(PONTOS_MIN, float(v))) for k, v in _dict(dados.get("pontos")).items()
                       if isinstance(k, str) and type(v) in (int, float) and v == v}
        if len(self.pontos) > MAX_FALAS:
            self.pontos = dict(list(self.pontos.items())[-MAX_FALAS:])

    def registrar(self, evento, now=None):
        """Conta uma interação (cutucada, carinho, dispensa...)."""
        self.contagens[evento] = self.contagens.get(evento, 0) + 1
        self._sujo = True

    def mostrou(self, fala, now):
        """Uma fala apareceu: fica esperando a sua reação para virar aprendizado."""
        if fala:
            self._mostradas = [m for m in self._mostradas if m[0] != fala][-19:] + [(fala, now)]

    def reagiu(self, now):
        """Você reagiu (cutucou ou deu carinho): as falas recentes ganham ponto."""
        dentro = [m for m in self._mostradas if now - m[1] <= JANELA_REACAO_S]
        for fala, _ in dentro:
            self._ajustar(fala, 1.0)
        self._mostradas = [m for m in self._mostradas if m not in dentro]

    def expirar(self, now):
        """Falas que passaram do tempo sem reação perdem um pouco de pontos."""
        velhas = [m for m in self._mostradas if now - m[1] > JANELA_REACAO_S]
        for fala, _ in velhas:
            self._ajustar(fala, -0.25)
        self._mostradas = [m for m in self._mostradas if m not in velhas]

    def _ajustar(self, fala, delta):
        self.pontos[fala] = min(PONTOS_MAX, max(PONTOS_MIN, self.pontos.get(fala, 0.0) + delta))
        self._sujo = True

    def peso(self, fala):
        """Peso de sorteio de uma fala: 1 é neutro; falas que você responde saem mais."""
        return min(PESO_MAX, max(PESO_MIN, 1.0 + 0.4 * self.pontos.get(fala, 0.0)))

    def fatos(self):
        """Resumo em português do que ele lembra, para o prompt do Ollama."""
        mais = sorted(((n, k) for k, n in self.contagens.items() if k in FATOS and n > 0), reverse=True)[:4]
        return "; ".join(f"{n} {FATOS[k]}" for n, k in mais) or "ainda nos conhecemos pouco"

    def salvar(self):
        if not self._sujo:
            return
        self._sujo = False
        try:
            write_json(self.path, {"contagens": self.contagens, "pontos": self.pontos}, indent=1)
        except OSError as error:
            log(f"[convivência] não salvou a memória: {error}")


class Reacoes:
    """Reações configuradas pelo usuário: gatilho -> fala -> espera -> ramo sim ou não."""

    def __init__(self, path):
        self.path = path
        self.ia = True
        self.regras = normalizar_regras(PADRAO["regras"])
        self._pendentes = []      # [(regra, quando)] esperando a sua reação

    def load(self):
        dados = read_json(self.path, default=None)
        self.definir(dados if dados is not None else PADRAO)

    def definir(self, bruto, salvar=False):
        """Aceita o formato do arquivo ({ia, regras}) ou só a lista de regras; valida tudo."""
        if isinstance(bruto, dict):
            self.ia = bruto.get("ia") is not False
            bruto = bruto.get("regras")
        self.regras = normalizar_regras(bruto)
        self._pendentes = []
        if salvar:
            self.salvar()

    def exportar(self):
        return {"ia": self.ia, "regras": self.regras, "gatilhos": GATILHOS, "acoes": ACOES}

    def salvar(self):
        try:
            write_json(self.path, {"ia": self.ia, "regras": self.regras}, indent=1)
        except OSError as error:
            log(f"[reações] não salvou: {error}")

    def disparar(self, gatilho, now):
        """Um gatilho aconteceu: devolve a fala inicial da regra (ou None) e espera a sua reação."""
        regra = next((r for r in self.regras if r["ativa"] and r["gatilho"] == gatilho), None)
        if regra is None:
            return None
        self._pendentes = [(r, q) for r, q in self._pendentes if r["id"] != regra["id"]] + [(regra, now)]
        return {"texto": regra["texto"], "tom": regra["tom"], "voz": regra["voz"]}

    def reagiu(self, now):
        """Você reagiu a tempo: as regras que esperavam seguem o ramo sim."""
        dentro = [(r, q) for r, q in self._pendentes if now - q <= r["espera"]]
        self._pendentes = [p for p in self._pendentes if p not in dentro]
        return [self._ramo(r, "sim") for r, _ in dentro]

    def expirar(self, now):
        """Passou o tempo sem reação: as regras pendentes seguem o ramo não."""
        fora = [(r, q) for r, q in self._pendentes if now - q > r["espera"]]
        self._pendentes = [p for p in self._pendentes if p not in fora]
        return [self._ramo(r, "nao") for r, _ in fora]

    @staticmethod
    def _ramo(regra, ramo):
        saida = regra[ramo]
        return {"texto": saida["texto"], "acao": saida["acao"], "tom": regra["tom"],
                "voz": regra["voz"] or saida["acao"] == "falar_voz"}


def ler_persona(pasta):
    """Jeito de ser do pet (pets/<pet>/persona.txt), resumido; vazio se o arquivo não existir."""
    try:
        return " ".join((pasta / "persona.txt").read_text(encoding="utf-8").split())[:600]
    except OSError:
        return ""


def prompt_fala(nome, persona, emocao, fatos, exemplos):
    """Mensagens para o Ollama criar uma fala do pet no jeito dos exemplos dele, com o que ele lembra."""
    sistema = (f"Você é {nome}, um bichinho virtual que vive na tela do usuário. {persona} "
               "Fale em primeira pessoa, em português do Brasil, com UMA frase curta (até 14 palavras), "
               "no mesmo jeito dos exemplos. Sem aspas, emojis ou listas. Use só os fatos recebidos.")
    usuario = (f"Agora você está: {emocao}. O que você lembra do usuário: {fatos}.\n"
               f"Exemplos do seu jeito de falar: {' | '.join(exemplos[:8])}\nFrase:")
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]
