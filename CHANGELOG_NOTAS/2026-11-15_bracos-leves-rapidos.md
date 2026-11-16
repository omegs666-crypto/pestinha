# Braços leves e rápidos — molas reafinadas

## Pedido
"Muito devagar e inorgânico — animação leve, rápida, sem muito lelelê."

## Causa
A mola de posição (rigidez .10, amortecimento .60) matava a velocidade a
cada frame: resposta suave demais, sem "snap" — a sensação de gordura
hidráulica em vez de braço leve. A rotação (.07/.55) ainda deixava um
rabo de balanço (o "lelelê").

## Novos pesos (simulados antes de aplicar)
Resposta ao degrau medida: tempo até 50% do alvo e overshoot.

- Posição: .10/.60 -> **.16/.72** — 50% em 33 ms (antes ~83 ms), assenta
  em 13 frames, quica leve de ~21% (antes 0% = pastoso).
- Rotação: .07/.55 -> **.13/.70** — pêndulo acompanha o gesto sem
  rabo de oscilação.
- Squash: .16/.55 -> **.22/.70** — deforma e volta num flash.
- Ganhos: `GANHO_ROT` .9 -> .55, `GANHO_SQ` .06 -> .05, `SQ_MAX` .35 -> .30
  (menos fonte de balanço residual).
- Mola do pulo do mascote: .14/.55 -> .16/.72 (mesma sensação).

Aplicado em `bracos.py` (CFG) e `ilha.js` (BRACO_CFG), espelhados.

## Verificação
- Simulação da mola: snap 2,5x mais rápido com overshoot de 21% (quica
  curta, uma vez — não tremedeira).
- `node --check` e pyflakes limpos; suíte: 544 pass, 5 skip.
- A sensação final pede avaliação ao vivo — se quiser mais seco, subir
  AMORT_POS p/ .78; se quiser mais cartoon, descer p/ .66.
