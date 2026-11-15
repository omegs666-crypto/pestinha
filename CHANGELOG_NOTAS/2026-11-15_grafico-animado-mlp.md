# 2026-11-15 — Gráfico de perda animado (Laboratório MLP)

## O que mudou (`pestinha/ui/lab_mlp.py`, classe `CurvaPerda`)
- **Escala logarítmica:** a perda cai de ~0,16 para ~0,00004 no treino de exemplo; em escala linear a
  curva virava uma linha colada no zero. Marcas em potências de 10 (1e-1, 1e-2…).
- **Animação suave:** cada valor se aproxima do alvo em frações por quadro; pontos novos crescem a partir
  do último exibido.
- **Pulso** no último ponto enquanto o treino roda.
- **Degradê** sob a curva e **leitura ao passar o mouse** (época e perda exatas).
- **Custo controlado:** o timer (~30 fps) só roda com o painel visível e enquanto há movimento ou treino;
  ao assentar ou ao esconder o painel, ele para. Medido: ~2 ms por pintura com 500 pontos (~6% de um quadro).

## Testes
- `tests/test_lab_mlp.py`: a curva anima até assentar e para; o pulso para quando o painel some; entradas
  vazias ou inválidas (NaN, infinito) são descartadas.

## Limitações
- O gráfico não tem zoom nem exportação.
