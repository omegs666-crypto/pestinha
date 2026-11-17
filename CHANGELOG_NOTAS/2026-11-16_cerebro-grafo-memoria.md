# 2026-11-16 — Aba "Cérebro": a memória do pet como grafo vivo (estilo Obsidian)

## O que foi feito

Nova aba na ilha, "Cérebro dele" (ícone de rede neural no dock), que desenha a
memória do pet como um grafo interativo — igual à Graph View do Obsidian, mas
com os dados reais dele, atualizados a cada 2 s enquanto a aba está aberta.

## Nós e arestas (dados reais, `ponte.grafo()`)

- **pet** (centro, ciano, respirando): o Bryan, âncora do grafo — fixo em (0,0).
- **emoção** (roxo): cada emoção que aparece nos episódios + a atual.
- **ação** (verde): travessuras que ele tentou (bilhete, meme, atravessar…).
- **contexto** (azul): o que você fazia (work, play, web, idle).
- **memória** (cinza, pequenos): os últimos 14 episódios resolvidos; rótulo só no hover.
- **drive** (laranja): energia, estímulo, carinho — com o valor atual.
- **pista** (rosa): condicionamento — "pressão no corpo", "você por perto", "placa do castigo".

Arestas: episódio → ação/emoção/contexto; `memory.table` → contexto→ação com a
**valência aprendida** (linha verde = deu certo, vermelha = deu ruim, mais grossa = mais forte);
drives e pistas → pet.

## Física (force-directed)

- Repulsão entre todos os nós (`REPULSAO`), arestas como molas até o repouso
  (`MOLA_K`, `MOLA_L`), gravidade fraca ao centro (`GRAVIDADE`), atrito (`AMORT`).
- Nós novos nascem perto do centro com anel de pulso (~0,9 s) — você vê a memória
  crescer ao vivo.
- Nós removidos (memória podada) somem do mapa.

## Interações

- Arrastar nó: reposiciona (o pet fica fixo).
- Arrastar fundo: move a câmera; rodinha: zoom (0,4–2,6×).
- Hover: cartão com detalhe (episódio mostra ação → resultado · valência · quando).

## Arquivos

- `pestinha/ui/web_bridge.py` — slot `grafo()` + `_grafo_memoria()` montando o JSON.
- `pestinha/ui/web/index.html` — `section[data-vista="cerebro"]` + botão no dock.
- `pestinha/ui/web/ilha.css` — `.cerebro`, `.cb-info`, `.cb-legenda`.
- `pestinha/ui/web/ilha.js` — módulo `cerebro` (física, render, eventos, poll).
- `tests/test_web_island.py` — 2 testes do slot (monta nós/arestas; sem memória não quebra).

## Observações

- Bug de CSS: `inset:0` shorthand não expande canvas neste Chromium do WebEngine —
  usado `left/top/width/height` como nas demais regras do projeto.
- Zero dependência externa; roda no canvas que já existia.
- Suíte: 549 testes.
