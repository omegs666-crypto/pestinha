"""
TEMA - identidade visual dos painéis do Pestinha.

Paleta e medidas copiadas do Coucou (windows/src/style.css): ilha preta
pendurada no topo, cartões #141518 com hairline, pills-cápsula #0e0f11,
texto ink #f5f6f8 / dim #9398a1 / dim-3 #6b7079. Fontes: Segoe UI.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen

# ---------------- paleta Coucou ----------------
BG = QColor("#000000")          # ilha: preto puro
CARD = QColor("#141518")        # cartões
CARD_FLAT = QColor("#0e0f11")   # pills
HAIRLINE = QColor(255, 255, 255, 9)    # rgba(255,255,255,0.035)
HAIRLINE_FORTE = QColor(255, 255, 255, 36)  # rgba(255,255,255,0.14)

INK = QColor("#f5f6f8")         # texto principal
INK_2 = QColor("#f1f2f4")
DIM = QColor("#9398a1")         # texto secundário
DIM_2 = QColor("#8e939c")
DIM_3 = QColor("#6b7079")       # labels de pill
DIM_4 = QColor("#5f646d")

RED = QColor("#f4505e")
RED_TEXT = QColor("#ff8d97")
GREEN = QColor("#22c55e")
GREEN_2 = QColor("#34d399")
BLUE = QColor("#3b82f6")
AMBER = QColor("#f5a524")
CYAN = QColor("#22d3ee")
INDIGO = QColor("#6366f1")
PINK = QColor("#f472b6")

# aliases usados pelos painéis pintados
CARTAO = CARD
BORDA = HAIRLINE
BORDA_FORTE = HAIRLINE_FORTE
TEXTO = INK
FRACO = DIM
VERDE = GREEN
AZUL = CYAN
LARANJA = AMBER
VERMELHO = RED
ROSA = PINK

# ---------------- fontes ----------------
FONTE = "Segoe UI"
FONTE_MONO = "Cascadia Mono"

def fonte(tamanho, peso=QFont.Normal, mono=False):
    """Fonte do tema: Segoe UI no texto, mono só para números técnicos."""
    return QFont(FONTE_MONO if mono else FONTE, tamanho, peso)

# ---------------- helpers de pintura ----------------

def fundo_arredondado(p, w, h, raio=14, cor=BG):
    """Pinta o fundo do painel como um cartão arredondado."""
    p.setPen(Qt.NoPen)
    p.setBrush(cor)
    p.drawRoundedRect(QRectF(0, 0, w, h), raio, raio)

def cartao(p, rect, raio=14, cor=CARD, borda=HAIRLINE):
    """Desenha um cartão interno com hairline (borda quase invisível)."""
    p.setPen(QPen(borda, 1))
    p.setBrush(cor)
    p.drawRoundedRect(rect, raio, raio)

def titulo_secao(p, x, y, texto, cor=DIM_3):
    """Título de seção em caixa alta, espaçado — o 'rótulo' do design."""
    p.setPen(cor)
    p.setFont(fonte(8, QFont.Bold))
    p.drawText(int(x), int(y), texto.upper())

def barra(p, x, y, w, valor, cor, h=6, raio=None):
    """Barra de progresso 0..1 com trilho arredondado."""
    r = h / 2 if raio is None else raio
    p.setPen(Qt.NoPen)
    p.setBrush(CARD_FLAT)
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)
    p.setBrush(cor)
    p.drawRoundedRect(QRectF(x, y, w * max(0.0, min(1.0, valor)), h), r, r)

# ---------------- stylesheets (widgets Qt) ----------------

def qss_pill():
    """Pill do Coucou: cápsula #0e0f11, hairline forte, label 600 10px dim-3."""
    return (
        f"QPushButton {{ background: {CARD_FLAT.name()}; color: {DIM_3.name()};"
        f" border: 1px solid rgba(255,255,255,0.14); border-radius: 13px;"
        f" font-family: '{FONTE}'; font-size: 10px; font-weight: 600; padding: 0 10px; }}"
        f"QPushButton:hover {{ background: rgba(255,255,255,0.10);"
        f" color: {DIM_2.name()}; }}"
        f"QPushButton:pressed {{ background: rgba(255,255,255,0.16); }}"
        f"QPushButton[ativo='true'] {{ color: {INK.name()};"
        f" border-color: rgba(255,255,255,0.4); }}"
    )

def qss_botao(primario=False):
    """Botão do Coucou: cápsula; primário é branco com texto preto."""
    if primario:
        return (f"QPushButton {{ background: {INK.name()}; color: #0b0c0e;"
                f" border: 0; border-radius: 999px; font-family: '{FONTE}';"
                f" font-size: 11px; font-weight: 500;"
                f" padding: 6px 14px; }}"
                f"QPushButton:hover {{ background: #ffffff; }}")
    return (f"QPushButton {{ background: rgba(255,255,255,0.09); color: {INK_2.name()};"
            f" border: 0; border-radius: 999px; font-family: '{FONTE}';"
            f" font-size: 11px; font-weight: 500;"
            f" padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.15); }}")
