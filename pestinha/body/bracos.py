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
FALA_AMP_Y = 10.0        # amplitude das ondas de gesto na fala
FALA_FREQ_E = 16.0       # frequência da onda do braço esquerdo
FALA_FREQ_D = 14.0       # frequência da onda do braço direito (diferente de propósito)
GANHO_BOCA = 0.3         # a abertura da boca levanta os braços (ênfase vocal)
IMPULSO_P = 0.05         # chance por frame de um pico de gesto (impulso, não alvo!)
IMPULSO_X = 3.0          # "chute" de velocidade lateral nos picos
IMPULSO_Y = 4.0          # "chute" de velocidade vertical nos picos (braço pula)
IMPULSO_ALCANCE = 12.0   # alcance do alvo lateral nos picos (px)


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

    def passo(self, falando, boca=0.0):
        """Um passo de física por frame; os alvos mudam com a fala e a abertura da boca."""
        self.esq.fisica()
        self.dir.fisica()
        t = time.monotonic()
        if falando:
            # gesticulação: ondas harmônicas assíncronas + ênfase pela boca
            self.esq.y.alvo = math.sin(t * FALA_FREQ_E) * FALA_AMP_Y - boca * GANHO_BOCA
            self.dir.y.alvo = math.cos(t * FALA_FREQ_D) * FALA_AMP_Y - boca * GANHO_BOCA
            if random.random() < IMPULSO_P:
                # pico de gesto: o impulso entra na VELOCIDADE - é ele que dá inércia
                self.esq.x.vel -= random.uniform(0, IMPULSO_X)
                self.dir.x.vel += random.uniform(0, IMPULSO_X)
                self.esq.y.vel -= random.uniform(0, IMPULSO_Y)
                self.dir.y.vel -= random.uniform(0, IMPULSO_Y)
                self.esq.x.alvo = -random.uniform(0, IMPULSO_ALCANCE)
                self.dir.x.alvo = random.uniform(0, IMPULSO_ALCANCE)
        else:
            # repouso: respiração senoidal com fases diferentes nos dois braços
            self.esq.y.alvo = math.sin(t * IDLE_FREQ) * IDLE_AMP_Y
            self.dir.y.alvo = math.sin(t * IDLE_FREQ + IDLE_FASE) * IDLE_AMP_Y
            self.esq.x.alvo = self.dir.x.alvo = 0.0
