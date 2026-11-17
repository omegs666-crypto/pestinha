# 2026-11-16 — Cérebro vivo e cheio: lembranças da convivência + deriva constante

## O que foi feito

O grafo real parecia estático e ralo por dois motivos, ambos corrigidos:

### 1. Cérebro ralo → lembranças da convivência
O `episodes.jsonl` ainda não existe (o pet não fez travessuras gravadas), então
só sobravam drives/pistas/emoção. Agora os **pontos** de `convivencia.json` — as
~30 frases que ele aprendeu de você, com a valência do que sentiu — entram no
grafo como nós de memória ligados a "você", com a mesma cor de valência das
arestas (verde = bom, vermelho = ruim). O cérebro fica cheio de verdade desde o
primeiro dia.

### 2. Cérebro estático → vida constante
- **Deriva orgânica**: cada nó recebe um empurrãozinho senoidal em fase própria —
  a teia nunca congela, flutua como no Obsidian.
- **Emoção atual pulsa**: o nó da emoção vigente (`agora`) ganha um anel que pulsa
  a cada ~0,5 s, no ritmo dele.
- O pet continua fixo no centro respirando; o sonho mantém o anel tracejado.

### 3. Versão antiga servida → cache-buster
A ilha estava rodando o build anterior (havia duas instâncias `pythonw` ativas).
`ilha.css` e `ilha.js` ganharam `?v=2026-11-16b` no `index.html` para o
QWebEngine nunca servir arquivo velho.

## Arquivos

- `pestinha/ui/web_bridge.py` — nós `ponto:*` a partir de `convivencia.pontos`.
- `pestinha/ui/web/ilha.js` — deriva senoidal + pulso da emoção atual.
- `pestinha/ui/web/index.html` — `?v=` nos assets.
