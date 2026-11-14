# 2026-11-08 — Reforma visual: tema unificado estilo Coucou

O usuário pediu uma UI interativa e bonita "de outro jeito". Foi criado um
tema visual compartilhado e aplicado em TODOS os painéis.

## Novo arquivo

- `pestinha/ui/tema.py` — identidade visual dos painéis:
  - paleta (fundo quase-preto esverdeado, cartões, bordas, acento verde,
    cores semânticas azul/laranja/vermelho/rosa)
  - fontes (`Segoe UI` texto, `Consolas` números)
  - helpers de pintura: `fundo_arredondado`, `cartao`, `titulo_secao`, `barra`
  - stylesheets: `qss_pill()`, `qss_pill_ativo()`

## Painéis reformados

| Arquivo | Mudanças |
|---|---|
| `ui/ilha.py` | pills com **ícones** (🧠✊🧪⛓️🎲🔊), estado ●/○ mantido, resumo com emojis por linha, estilos via tema |
| `ui/monitor.py` | janela **translúcida** com fundo arredondado (raio 16), raster em cartão arredondado, barras arredondadas, fontes do tema |
| `ui/panel.py` | janela translúcida + fundo arredondado, fontes do tema |
| `ui/lab_mlp.py` | janela translúcida, desenho da rede em cartão arredondado, gráfico de perda em cartão, botão/label no estilo pill do tema |

## Efeito visual
- Painéis agora têm **cantos arredondados com transparência** (efeito vidro)
  em vez de retângulos sólidos.
- Hierarquia visual: títulos de seção em caixa alta espaçada, cartões internos,
  barras de progresso arredondadas.
- Pills da ilha com ícone + nome + indicador de estado.

## Verificação
- `pyflakes` limpo; `test_ilha.py`/`test_paineis.py`/`test_app.py` passando
  (ajustado unpack dos 4 campos de `_pills_meta` no teste).
