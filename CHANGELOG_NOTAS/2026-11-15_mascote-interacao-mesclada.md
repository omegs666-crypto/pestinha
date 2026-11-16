# Um Bryan só: interações mescladas entre pet e mascote da ilha

## Pedido
O usuário notou "2 Bryans na tela": o pet Qt livre e o mascote da pílula.
Mesma emoção, mas interagir com um não afetava o outro.

## O que mudou

### Mascote → pet (ilha.js → Ponte.mascote_interacao)
- Clique no mascote = **cutucada** (`app.on_poke`, com cooldown e reflexo).
- Esfregar o mouse no mascote = **carinho** (`app.menu_caress`), detectando
  vai-e-vem igual ao `_track_rub` do pet (3 reversões + 60 px em 0,7 s).
- Duplo clique = **carinho instantâneo** (`app.on_double_click`).
- O mascote deixou de abrir o painel — ele agora é o pet. A ilha continua
  abrindo por hover (260 ms), orbe e balão.
- Título do canvas atualizado para os novos gestos.

### Pet → mascote
- `Ponte.gesto` (novo sinal): `on_poke`, `on_double_click`, `on_thrown` e
  `menu_caress` emitem "cutucada"/"carinho"/"arremesso"; o mascote pula
  (mola de pulo própria) ou mostra corações na hora.
- Snapshot ganhou `carinho` (de `pet_state.feliz_fechado`): o mascote fecha
  os olhinhos em ^^ e solta corações subindo enquanto o carinho dura —
  sem precisar do usuário tocar nele.

## Verificação
- Ao vivo (QWebEngineView): clique no mascote → `on_poke`; esfregar →
  `menu_caress`; `gesto.emit` → mascote pula e mostra carinho na captura.
- Testes novos: `carinho` no snapshot e mapeamento das três ações do
  mascote para os métodos do pet.
- Suíte: 544 pass, 5 skip; `node --check` e pyflakes limpos.

## Observações
- O clique no mascote virou cutucada; quem clicava nele para abrir agora
  usa o hover, o orbe ou o balão.
- `gesto` é espelho visual — a lógica de estado continua sendo do pet.
