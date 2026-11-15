# 2026-11-15 — Som de clique na ilha (como o blip do Coucou)

## O que mudou
- Cada clique em botão, cartão, orbe, mascote, balão, campo de modelo do chat ou item da lista toca um
  "blip" curto (880 → 1320 Hz, 90 ms, volume 0.12 — mesmo volume padrão do Coucou).
- O som é **sintetizado** em Web Audio (`ui/web/ilha.js`, `tocarClique`). Não copiamos os arquivos de
  som do Coucou: eles têm licença própria (Louis Raillé, LICENSE-ASSETS.md) e não podem ser redistribuídos
  neste projeto.

## Testes
- `test_clique_em_botao_toca_o_blip`: clica em botão, mascote e em um botão da aba Som; confere 3 sons
  (um por clique), via WebEngine.

## Limitações
- Sem opção para desligar o som ainda. Se quiser, adiciono um interruptor em Controles.
