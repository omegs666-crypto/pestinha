# 2026-11-16 — Cérebro interativo: filtros, foco, "você", sonhos e cutucar o cérebro

## O que foi feito

Incrementos na aba Cérebro (o grafo da memória estilo Obsidian), saindo do pacote
de recomendações: leitura, interação, o nó "você" e a consolidação no sono.

## Novidades

### Filtros por tipo (`#cb-filtros`)
Chips no topo: todos / memórias / emoções / ações / contextos / drives / pistas /
você. Nós fora do filtro esmaecem para ~10% em vez de sumir — a teia mantém a
geografia e você entende o que foi escondido.

### Modo foco (clique)
Clique num nó: ele e os vizinhos diretos acendem, o resto apaga. Clique de novo
ou no fundo para soltar. Clique conta só se o mouse não moveu (>5 px = arraste).

### Cutucar o cérebro (duplo clique)
Duplo clique num nó → `ponte.cutucar_no(id)` → ele comenta no balão o que aquele
pedaço da memória significa, com frases por tipo (episódio conta o resultado e a
valência, drive fala o nível atual, conceito pede silêncio porque está sonhando).

### Heat de recência
Episódios esmaecem ao longo de `ENVELHECE_H` (72 h): memória recente brilha,
antiga apaga devagar — o esquecimento visível.

### Nó "você"
`convivencia.contagens` vira um nó rosa "você" ligado ao pet, com as 5 interações
mais vividas penduradas ("carinho ×138", "cutucada ×264").

### Sonhos (consolidação no sono)
Enquanto `app.asleep`, os episódios se fundem em nós-conceito por emoção
("3 lembranças feliz") com anel tracejado flutuando — ele literalmente sonha
organizando as memórias; ao acordar, os episódios voltam como antes.

## Arquivos

- `pestinha/ui/web_bridge.py` — consolidação no sono, nó você/convivência,
  slot `cutucar_no` + frases por tipo, chave `dormindo` no JSON.
- `pestinha/ui/web/index.html` — chips de filtro + novos tipos na legenda.
- `pestinha/ui/web/ilha.css` — `.cb-filtros`.
- `pestinha/ui/web/ilha.js` — filtro/foco/heat/sonho, dblclick→cutucar, clique=foco.

## Testes

- `test_web_island.py`: 27 passam. Suíte completa anterior: 549.
- Capturas validadas: teia acordada (nó você + contagens), modo sonho
  (conceitos fundidos), filtro ativo (emoções+ações acesas, resto esmaecido).
