"""
BRACOS - os bracinhos mecânicos do pet: cápsulas laterais com física de molas.

Sistema massa-mola (Spring Mass System), evolução do protótipo do usuário.
Cada braço tem QUATRO molas independentes:

    posição X ..... vai e vem na lateral (para fora nos picos de gesto)
    posição Y ..... sobe e desce (respiração no repouso, ondas na fala)
    rotação ....... pêndulo: o braço inclina no sentido do próprio movimento
    squash ........ squash & stretch: estica na aceleração, achata no repouso

O que dá a sensação orgânica:
- o IMPULSO mexe na VELOCIDADE, não no alvo: a mola overshoota e volta
  elástica, com inércia de verdade;
- a rotação persegue a velocidade horizontal, como um braço pendurado;
- a deformação persegue a energia do movimento (squash & stretch);
- os dois braços usam fases e frequências levemente diferentes, então
  nunca se movem em espelho - o que quebraria a ilusão de vida.

`passo(falando, boca)` segue o contrato da Boca: `falando` vem da Voz e
`boca` é a abertura bucal atual, que aumenta a amplitude dos gestos.
"""

import math
import random
import time

from .boca import Mola

# ============================================================================
# 1. FÍSICA - pesos das molas (AJUSTE AQUI)
# ----------------------------------------------------------------------------
# rigidez (stiffness): força que puxa a mola de volta ao alvo.
#   alta = braço pesado/duro; baixa = braço mole, demora a chegar.
# amortecimento (damping): atrito por passo.
#   perto de 1 = movimento curto e seco; baixo = quica muito (inércia longa).
# ============================================================================
RIGIDEZ_POS = 0.10       # posição: resposta média, braço leve
AMORT_POS = 0.60         # posição: amortecimento do protótipo, balanço moderado
RIGIDEZ_ROT = 0.07       # rotação: pêndulo mole, inclina devagar
AMORT_ROT = 0.55         # rotação: oscila bastante antes de parar
RIGIDEZ_SQ = 0.16        # squash: deforma rápido ao acelerar
AMORT_SQ = 0.55          # squash: a elasticidade quica antes de assentar

GANHO_ROT = 0.9          # quanto a velocidade X vira inclinação (pendular)
GANHO_SQ = 0.06          # quanto a energia do movimento vira deformação
SQ_MAX = 0.35            # deformação máxima (35% - além disso parece borracha demais)

# ============================================================================
# 2. ALVOS POR ESTADO - repouso (respiração) e fala (gesticulação)
# ============================================================================
IDLE_AMP_Y = 2.0         # amplitude da respiração em repouso (px, na escala do corpo)
IDLE_FREQ = 3.0          # frequência da respiração (rad/s)
IDLE_FASE = 1.3          # defasagem do braço direito: nunca em espelho
FALA_AMP_Y = 14.0        # amplitude das ondas de gesto na fala
FALA_FREQ_E = 16.0       # frequência da onda do braço esquerdo
FALA_FREQ_D = 14.0       # frequência da onda do braço direito (diferente de propósito)
GANHO_BOCA = 0.3         # a abertura da boca levanta os braços (ênfase vocal)
IMPULSO_P = 0.08         # chance por frame de um pico de gesto (impulso, não alvo!)
IMPULSO_X = 3.0          # "chute" de velocidade lateral nos picos
IMPULSO_Y = 4.0          # "chute" de velocidade vertical nos picos (braço pula)
IMPULSO_ALCANCE = 12.0   # alcance do alvo lateral nos picos (px)

# ============================================================================
# 3. GESTOS POR EMOÇÃO - o repouso deixa de ser só respiração (AJUSTE AQUI)
# ----------------------------------------------------------------------------
# Cada emoção descreve UM gesto característico feito com os mesmos alvos de
# mola (x, y) - a física acima continua resolvendo peso, overshoot e squash.
# "energia" multiplica a amplitude e a chance de impulsos quando ele FALA.
# ============================================================================
EMOCAO_ENERGIA = {
    "feliz": 1.3, "bravo": 1.5, "assustado": 1.2, "dramatico": 1.4,
    "curioso": 1.0, "observando": 0.8, "contente": 0.9,
    "triste": 0.4, "dormindo": 0.1,
}
# feliz - "cut cut": cutucadas rápidas para o ar, alternando os braços
FELIZ_FREQ = 1.6         # cutucadas por segundo (o par inteiro alterna)
FELIZ_JAB = 9.0          # altura do soco para cima em cada cutucada (px)
FELIZ_JANELA = 0.30      # fração do meio-ciclo em que o braço está "cutucando"
FELIZ_ABRE = 3.0         # quanto o braço abre para fora na cutucada (px)
# bravo - tremor de raiva: braços fechados (punhos) sacudindo rápido
BRAVO_FREQ = 32.0        # frequência do tremor (rad/s - bem alto de propósito)
BRAVO_AMP = 2.6          # amplitude do tremor (px - pequeno e nervoso)
BRAVO_FECHA = 6.0        # braços colam no corpo, tensos (px para dentro)
BRAVO_SOBE = 5.0         # tensão levanta os punhos (px)
# triste / dormindo - braços caem pesados, quase sem movimento
TRISTE_CAEM = 9.0        # quanto os braços caem (px para baixo)
TRISTE_FREQ = 1.2        # respiração lenta e pesada (rad/s)
DORMINDO_CAEM = 11.0     # dormindo caem mais ainda e ficam parados
# assustado - braços para cima e abertos, tremendo de leve
SUSTO_SOBE = 10.0        # braços levantados (px para cima)
SUSTO_ABRE = 8.0         # braços abertos (px para fora)
SUSTO_TREMOR = 22.0      # tremidinha do susto (rad/s)
# curioso - um braço levantado "apontando", trocando de lado devagar
CURIO_SOBE = 9.0         # altura do braço que aponta (px)
CURIO_TROCA = 0.35       # ritmo de troca de lado (Hz, bem lento)
# dramatico - varreduras amplas e lentas, de teatro
DRAMA_AMP = 14.0         # amplitude da varredura (px)
DRAMA_FREQ = 4.0         # velocidade da varredura (rad/s)


class Braco:
    """Um braço: as quatro molas e o lado (para desenhar e assinar o pêndulo)."""

    def __init__(self, lado):
        self.lado = lado                          # -1 esquerdo, +1 direito
        self.x = Mola(0.0, RIGIDEZ_POS, AMORT_POS)
        self.y = Mola(0.0, RIGIDEZ_POS, AMORT_POS)
        self.rot = Mola(0.0, RIGIDEZ_ROT, AMORT_ROT)
        self.squash = Mola(1.0, RIGIDEZ_SQ, AMORT_SQ)

    def fisica(self):
        """Um passo por frame: as molas andam e os alvos cruzados dão a organicidade."""
        for mola in (self.x, self.y, self.rot, self.squash):
            mola.passo()
        # pendular: a inclinação persegue a velocidade lateral (balanço de braço solto)
        self.rot.alvo = -self.lado * self.x.vel * GANHO_ROT
        # squash & stretch: a deformação persegue a energia total do movimento
        energia = abs(self.x.vel) + abs(self.y.vel)
        self.squash.alvo = 1.0 + min(SQ_MAX, energia * GANHO_SQ)


class Bracos:
    """O par de braços: estado idle (respiração) e gestos (fala + picos de energia)."""

    def __init__(self):
        self.esq = Braco(-1)
        self.dir = Braco(1)

    def passo(self, falando, boca=0.0, emocao="observando"):
        """Um passo de física por frame; os alvos mudam com a fala, a boca e a emoção."""
        self.esq.fisica()
        self.dir.fisica()
        t = time.monotonic()
        if falando:
            # gesticulação: ondas assíncronas + ênfase da boca, temperadas pela emoção
            energia = EMOCAO_ENERGIA.get(emocao, 0.8)
            amp = FALA_AMP_Y * energia
            self.esq.y.alvo = math.sin(t * FALA_FREQ_E) * amp - boca * GANHO_BOCA
            self.dir.y.alvo = math.cos(t * FALA_FREQ_D) * amp - boca * GANHO_BOCA
            if random.random() < IMPULSO_P * energia:
                # pico de gesto: o impulso entra na VELOCIDADE - é ele que dá inércia
                self.esq.x.vel -= random.uniform(0, IMPULSO_X) * energia
                self.dir.x.vel += random.uniform(0, IMPULSO_X) * energia
                self.esq.y.vel -= random.uniform(0, IMPULSO_Y) * energia
                self.dir.y.vel -= random.uniform(0, IMPULSO_Y) * energia
                self.esq.x.alvo = -random.uniform(0, IMPULSO_ALCANCE)
                self.dir.x.alvo = random.uniform(0, IMPULSO_ALCANCE)
        else:
            self._repouso(emocao, t)

    def _repouso(self, emocao, t):
        """O gesto de repouso muda com a emoção; o padrão é a respiração."""
        resp = IDLE_AMP_Y
        self.esq.x.alvo = self.dir.x.alvo = 0.0
        if emocao == "feliz":
            # "cut cut": cutucada rápida para o ar, um braço de cada vez
            fase = (t * FELIZ_FREQ) % 2.0                     # 0-1: esquerdo, 1-2: direito
            self.esq.y.alvo = -FELIZ_JAB if fase < FELIZ_JANELA else math.sin(t * IDLE_FREQ) * resp
            self.dir.y.alvo = -FELIZ_JAB if 1.0 <= fase < 1.0 + FELIZ_JANELA else math.sin(t * IDLE_FREQ + IDLE_FASE) * resp
            self.esq.x.alvo = -FELIZ_ABRE if fase < FELIZ_JANELA else 0.0
            self.dir.x.alvo = FELIZ_ABRE if 1.0 <= fase < 1.0 + FELIZ_JANELA else 0.0
        elif emocao == "bravo":
            # punhos fechados tremendo de raiva
            self.esq.y.alvo = math.sin(t * BRAVO_FREQ) * BRAVO_AMP - BRAVO_SOBE
            self.dir.y.alvo = math.sin(t * BRAVO_FREQ + 0.9) * BRAVO_AMP - BRAVO_SOBE
            self.esq.x.alvo = BRAVO_FECHA + math.sin(t * BRAVO_FREQ * 0.7) * 1.2
            self.dir.x.alvo = -BRAVO_FECHA - math.sin(t * BRAVO_FREQ * 0.7) * 1.2
        elif emocao == "triste":
            # braços caídos, respirando devagar
            self.esq.y.alvo = TRISTE_CAEM + math.sin(t * TRISTE_FREQ) * resp
            self.dir.y.alvo = TRISTE_CAEM + math.sin(t * TRISTE_FREQ + IDLE_FASE) * resp
        elif emocao == "dormindo":
            # largados no corpo, quase estáticos
            self.esq.y.alvo = self.dir.y.alvo = DORMINDO_CAEM
        elif emocao == "assustado":
            # para cima e abertos, com tremidinha
            self.esq.y.alvo = -SUSTO_SOBE + math.sin(t * SUSTO_TREMOR) * 1.1
            self.dir.y.alvo = -SUSTO_SOBE + math.sin(t * SUSTO_TREMOR + 0.7) * 1.1
            self.esq.x.alvo = -SUSTO_ABRE
            self.dir.x.alvo = SUSTO_ABRE
        elif emocao == "curioso":
            # um braço aponta para cima e troca de lado devagar
            lado_sobe = -1 if math.sin(t * CURIO_TROCA * math.tau) > 0 else 1
            self.esq.y.alvo = -CURIO_SOBE if lado_sobe < 0 else math.sin(t * IDLE_FREQ) * resp
            self.dir.y.alvo = -CURIO_SOBE if lado_sobe > 0 else math.sin(t * IDLE_FREQ + IDLE_FASE) * resp
        elif emocao == "dramatico":
            # varreduras amplas de teatro, braços em oposição
            self.esq.y.alvo = math.sin(t * DRAMA_FREQ) * DRAMA_AMP
            self.dir.y.alvo = -math.sin(t * DRAMA_FREQ) * DRAMA_AMP
        else:
            # observando/contente: respiração senoidal com fases diferentes
            if emocao == "contente":
                resp = 3.0
            self.esq.y.alvo = math.sin(t * IDLE_FREQ) * resp
            self.dir.y.alvo = math.sin(t * IDLE_FREQ + IDLE_FASE) * resp
