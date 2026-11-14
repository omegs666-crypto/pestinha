"""Narrador: transforma mudanças do estado do pet em frases curtas para a interface.

Duas fontes de fala:
- regras locais, instantâneas e sem rede (`Narrador.observar`);
- insights do Ollama local, pedidos pela ponte de tempos em tempos (`prompt_insight`).
Modelos de nuvem (`:cloud`) nunca são escolhidos automaticamente: o narrador é local.
"""

INTERVALO_MIN_S = 12.0        # entre duas falas quaisquer
REPETIR_MIN_S = 90.0          # a mesma regra não se repete antes disso
MAX_FRASE = 160
PREFERIDOS_LEVES = ("1b", "2b", "3b", "mini", "small", "tiny", "phi")


def modelo_de_nuvem(nome):
    """Modelos `:cloud`/`-cloud` rodam fora do PC; o narrador não os usa."""
    nome = str(nome or "").casefold()
    return nome.endswith(":cloud") or "-cloud" in nome or ":cloud" in nome


RACIOCINIO_LONGO = ("deepseek-r1", "qwq", "-r1", "reason")


def escolher_modelo(modelos, preferido=""):
    """O narrador precisa ser rápido: modelo local leve primeiro, depois o do chat, nunca um de nuvem.

    Modelos de raciocínio longo (que "pensam" antes de responder) só entram se não houver outro.
    """
    locais = [m for m in (modelos or []) if isinstance(m, str) and m and not modelo_de_nuvem(m)]
    rapidos = [m for m in locais if not any(tag in m.casefold() for tag in RACIOCINIO_LONGO)]
    for m in rapidos:
        if any(tag in m.casefold() for tag in PREFERIDOS_LEVES):
            return m
    if preferido in rapidos:
        return preferido
    return (rapidos or locais or [""])[0]


def limpar_frase(texto):
    """Uma frase curta, sem aspas nem quebras; vazio se o modelo não respondeu nada útil."""
    texto = str(texto or "")
    if "</think>" in texto:                     # modelos de raciocínio: só o que vem depois do pensamento
        texto = texto.split("</think>")[-1]
    texto = " ".join(texto.replace("*", "").split()).strip(" \"'“”")
    return texto[:MAX_FRASE].rstrip()


def _nivel(valor):
    """Número 0–100 como palavra: modelos pequenos acertam mais com 'baixa' do que com '22'."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "desconhecido"
    return "muito baixo" if v < 20 else "baixo" if v < 40 else "médio" if v < 65 else "alto"


def prompt_insight(estado, nome="Pestinha"):
    """Mensagens para o Ollama comentar o estado em uma frase, a partir de fatos já escritos.

    Modelos locais pequenos interpretam mal JSON cru; por isso os números viram frases.
    """
    fatos = (
        f"Emoção agora: {estado.get('emocao') or 'desconhecida'}. "
        f"Energia: {estado.get('energia', 0)}% ({_nivel(estado.get('energia'))}). "
        f"Estímulo: {estado.get('estimulacao', 0)}% ({_nivel(estado.get('estimulacao'))}). "
        f"Insatisfação: {estado.get('insatisfacao', 0)}% ({_nivel(estado.get('insatisfacao'))}). "
        f"Atividade neural: {estado.get('atividade', 0)}% ({_nivel(estado.get('atividade'))}). "
        f"{'Está pausado.' if estado.get('pausado') else 'Está ativo.'}"
    )
    logs = [str(l)[:120] for l in list(estado.get("logs") or [])[-3:]]
    if logs:
        fatos += " Últimos eventos: " + " | ".join(logs)
    return [
        {"role": "system", "content": (
            f"Você narra o que acontece com o {nome}, um bichinho virtual na tela do usuário. Fale dele "
            "na terceira pessoa (ele). Baseie-se SOMENTE nos fatos recebidos e destaque o mais "
            "importante (por exemplo energia baixa ou insatisfação alta). Responda em português do Brasil "
            "com UMA frase curta, no máximo 14 palavras, amigável. Sem aspas, emojis ou listas.")},
        {"role": "user", "content": f"Fatos: {fatos}\nFrase:"},
    ]


class Narrador:
    """Regras simples sobre o estado, com intervalo mínimo para não virar spam."""

    def __init__(self):
        self._anterior = None
        self._ultima_fala = -1e9
        self._ultima_por_regra = {}

    def _pode(self, regra, agora):
        return (agora - self._ultima_fala >= INTERVALO_MIN_S
                and agora - self._ultima_por_regra.get(regra, -1e9) >= REPETIR_MIN_S)

    def _falar(self, regra, texto, tom, agora):
        self._ultima_fala = agora
        self._ultima_por_regra[regra] = agora
        return {"texto": texto[:MAX_FRASE], "tom": tom, "origem": "regras"}

    def observar(self, estado, agora):
        """Compara com o estado anterior e devolve no máximo uma fala (ou None)."""
        antes, self._anterior = self._anterior, dict(estado or {})
        if antes is None or not estado:
            return None
        candidatos = []
        if estado.get("pausado") != antes.get("pausado"):
            candidatos.append(("pausa", "Pausei tudo. Respira um pouco." if estado.get("pausado")
                               else "Voltei! Seguindo de onde paramos.", "calmo"))
        if estado.get("processando") and not antes.get("processando"):
            candidatos.append(("processando", "Iniciando ciclos de aprendizado...", "processando"))
        if antes.get("processando") and not estado.get("processando"):
            candidatos.append(("processado", "Terminei a análise, quer dar uma olhada?", "calmo"))
        if estado.get("energia", 100) < 25 <= antes.get("energia", 100):
            candidatos.append(("energia", "Energia baixa: ele está pedindo uma pausa.", "alerta"))
        if estado.get("insatisfacao", 0) >= 60 > antes.get("insatisfacao", 0):
            candidatos.append(("insatisfacao", "A insatisfação está subindo, cuidado com o protesto.", "alerta"))
        if estado.get("emocao") and estado.get("emocao") != antes.get("emocao"):
            candidatos.append(("emocao", f"Agora ele está {str(estado['emocao']).lower()}.", "calmo"))
        for regra, texto, tom in candidatos:
            if self._pode(regra, agora):
                return self._falar(regra, texto, tom, agora)
        return None
