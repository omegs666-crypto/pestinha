# Braços reagem às ações, não só à emoção

## Problema relatado
"Animação de idle fixa em todas as reações": os braços só mudavam pela
emoção, mas cutucada/carinho/arremesso são eventos que nem sempre mudam a
emoção — então o braço ficava na respiração mesmo quando o Bryan reagia.

## O que mudou

### `pestinha/body/bracos.py` — camada de reação
- `REACAO_DUR`: duração de cada gesto transitório (cutucada .7s, carinho
  1.4s, arremesso 1.3s, dispensa .8s, preso 1s, fuga 1s, assustado .7s).
- `reagir(acao)`: dispara o gesto e dá o arranque como impulso de
  VELOCIDADE (o solavanco com inércia, não mudança de alvo).
- `_gesto(acao, t)`: os alvos de cada reação — recuo para cima na
  cutucada, mãos no rosto remexendo no carinho, moinho de pânico no
  arremesso, empurrão na dispensa, batida alternada no preso, sobressalto
  no assustado.
- A reação tem PRIORIDADE sobre fala e repouso enquanto dura.

### Ligação no app
- `_reagiu(tipo)` chama `bracos.reagir(tipo)` → cutucada e carinho.
- `_evento(motivo)` chama `bracos.reagir(motivo)` e, quando é ação
  conhecida, emite `gesto` para a ilha → arremesso, dispensa, preso,
  fuga e assustado (a emissão explícita de arremesso saiu do handler).

### Mascote (ilha.js)
- `REACAO_DUR` e `_gesto` espelhados; `aoGesto` arma a reação e aplica os
  mesmos impulsos (antes só fazia o mascote pular).

## Verificação
- Capturas Qt: cutucada (mãos para cima e fora), carinho (mãos no rosto),
  arremesso (moinho no meio do giro) — poses distintas do repouso.
- `node --check` e pyflakes limpos; suíte: 544 pass, 5 skip.

## Para ajustar
- Durações em `REACAO_DUR`; força do reflexo nos impulsos de `reagir()`;
  poses em `_gesto()`. Constantes comentadas na seção 4 de bracos.py.
