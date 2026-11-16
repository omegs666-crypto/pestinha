"""
BRACOS - os bracinhos mecânicos do pet: cápsulas laterais com molas próprias.

Portado do protótipo do usuário: quatro molas independentes (X e Y de cada braço).
Falando, gesticulam com ondas harmônicas assíncronas e picos expressivos para fora;
em repouso, flutuam devagarinho como quem respira. `passo(falando, boca)` segue o
mesmo contrato da Boca - `falando` vem da Voz e `boca` é a abertura bucal atual,
que aumenta a amplitude dos gestos.
"""

import math
import random
import time

from .boca import Mola


class Bracos:
    """As molas dos braços mecânicos (esquerdo/direito, X/Y), uma por articulação."""

    def __init__(self):
        self.esq_y = Mola(0.0, 0.10, 0.60)
        self.dir_y = Mola(0.0, 0.10, 0.60)
        self.esq_x = Mola(0.0, 0.10, 0.60)
        self.dir_x = Mola(0.0, 0.10, 0.60)

    def passo(self, falando, boca=0.0):
        """Um passo de física por frame; os alvos mudam com a fala e a abertura da boca."""
        for mola in (self.esq_y, self.dir_y, self.esq_x, self.dir_x):
            mola.passo()
        t = time.monotonic()
        if falando:
            self.esq_y.alvo = math.sin(t * 16) * 10 - boca * 0.3
            self.dir_y.alvo = math.cos(t * 14) * 10 - boca * 0.3
            if random.random() < 0.05:                       # pico expressivo: braços para fora
                self.esq_x.alvo = -random.uniform(0, 12)
                self.dir_x.alvo = random.uniform(0, 12)
        else:                                                # repouso: flutuação de respiração
            self.esq_y.alvo = math.sin(t * 3) * 2
            self.dir_y.alvo = math.sin(t * 3) * 2
            self.esq_x.alvo = self.dir_x.alvo = 0.0
