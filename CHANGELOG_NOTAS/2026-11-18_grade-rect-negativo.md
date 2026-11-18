# Grade: fim do spam `<rect> width="-7.5"`

## Diagnóstico

O console encheu de `Error: <rect> attribute width: A negative value is not valid. ("-7.5")`.

Causa: `mide()` (`parrilla.js`) mede `caja.clientWidth` — quando o iframe da Grade inicializa **antes de ser exibido** (ou em qualquer instante sem layout), a largura lê `0`. Com `S.W = 0` o modo estreito acende (`0 < 640` → 4 colunas) e `colW = (0 − 3·10) / 4 = −7.5`. O `pintaRejilla` então criava 32 `<rect>` com `width="-7.5"` — um erro por rect.

Pior que o spam: `adaptaColumnas(4)` **compactava a disposição** como se a tela fosse estreita, mexendo no layout sem motivo (o modo estreito guarda `S.ancho` para restaurar, mas o trabalho — e o flicker de posições — era todo inútil).

## O que mudou (`pestinha/ui/web/moxen/parrilla/parrilla.js`)

- `mide()`: sai cedo quando `S.W <= 0` — sem medida válida, mantém o estado anterior (12 colunas × 60 px no boot) e o `ResizeObserver` remede de verdade quando o iframe aparece.
- `pintaRejilla()`: guarda extra — `colW <= 0` limpa a malha em vez de gerar rects inválidos (defesa em profundidade, caso algo no futuro volte a produzir medida ruim).

## Verificação

`node --check` OK. O spam de console some na próxima abertura da Grade (o iframe recarrega o script a cada visita à aba).

## Errata — a causa da persistência do erro

O spam continuou depois do fix porque **`parrilla.js`/`parrilla.css` e `eslabon.js`/`eslabon.css` carregavam sem `?v=`** — o cache em disco do WebEngine servia a versão antiga mesmo com app reiniciado. Agora os quatro assets dos iframes têm `?v=2026-11-18a`, mesma política de cache-buster do `ilha.js`/`ilha.css`.
