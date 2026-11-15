# 2026-11-15 — Arrastar o painel do MLP voltou a funcionar

## Problema
- Não dava para mover o Laboratório MLP por cima do gráfico de perda.
- Causa: `CurvaPerda.mouseMoveEvent` (hover) aceitava o evento, então o movimento não subia ao painel
  (`FloatingWidget`), que é quem move a janela. A curva engolia o arraste.

## Correção (`pestinha/ui/lab_mlp.py`)
- `CurvaPerda.mouseMoveEvent` chama `event.ignore()` depois de atualizar o hover: o movimento segue para o painel.

## Verificação
- Reproduzido por eventos de mouse: arrastar pelo fundo, cabeçalho, rede e gráfico movia o painel;
  pelo gráfico, antes da correção, não movia.
- `test_arrastar_pelo_grafico_move_o_painel` cobre a regressão.

## Limitações
- Arrastar pelos botões e sliders não move o painel (eles são controles, como antes).
