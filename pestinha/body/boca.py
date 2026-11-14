"""
BOCA - a boca do pet com física de molas (squash & stretch), desenhada no rosto.

Adaptado do protótipo "Gatuno": cada dimensão (abertura, largura, achatamento do
queixo e o balanço da gravata) é uma mola com rigidez e amortecimento — o alvo
muda no ritmo dos fonemas e a mola dá o efeito elástico orgânico.

`passo(dt, falando)`: `falando` vem da Voz (pestinha/mind/voz.py): enquanto ela
fala, os alvos sorteiam fonemas a cada 80-220 ms; parou, a boca relaxa sozinha.
"""

import random
import time


class Mola:
    """Uma mola: valor persegue o alvo com aceleração amortecida (efeito elástico)."""
    def __init__(self, alvo=0.0, rigidez=0.12, amortecimento=0.65):
        """Começa parada no alvo, com a rigidez e o amortecimento dados."""
        self.valor = alvo
        self.alvo = alvo
        self.vel = 0.0
        self.rigidez = rigidez
        self.amortecimento = amortecimento

    def passo(self):
        """Um passo de física da mola (chamar a cada frame)."""
        self.vel += (self.alvo - self.valor) * self.rigidez
        self.vel *= self.amortecimento
        self.valor += self.vel


class Boca:
    """As molas da boca (abertura, largura, squash do queixo) e do balanço da gravata."""
    def __init__(self):
        """Começa fechada, descansada, sem fala marcada."""
        self.abertura = Mola(0.0, 0.20, 0.55)   # altura da cavidade bucal
        self.largura = Mola(26.0, 0.14, 0.60)   # largura labial
        self.squash = Mola(1.0, 0.15, 0.60)     # deformação vertical do queixo
        self.g_swing = Mola(0.0, 0.08, 0.70)    # pêndulo horizontal da gravata
        self.g_bounce = Mola(0.0, 0.12, 0.65)   # peso vertical da gravata
        self.falando = False
        self._prox_fonema = 0.0

    def passo(self, falando):
        """Atualiza as molas e sorteia o próximo fonema enquanto a Voz fala."""
        for mola in (self.abertura, self.largura, self.squash, self.g_swing, self.g_bounce):
            mola.passo()
        agora = time.monotonic()
        if falando and agora > self._prox_fonema:
            self.abertura.alvo = random.uniform(4.0, 16.0)       # fonema: boca abre variada
            self.largura.alvo = random.uniform(20.0, 34.0)
            self.squash.valor = 1.06                              # impacto elástico no queixo
            self.squash.alvo = 1.0
            self.g_swing.alvo = random.uniform(-8.0, 8.0)         # gravata balança de arrasto
            self.g_bounce.alvo = random.uniform(0.0, 4.0)
            self._prox_fonema = agora + random.uniform(0.08, 0.22)
        elif not falando:
            self.abertura.alvo = 0.0                              # relaxa para o repouso
            self.largura.alvo = 26.0
            self.g_swing.alvo = 0.0
            self.g_bounce.alvo = 0.0
        self.falando = falando
