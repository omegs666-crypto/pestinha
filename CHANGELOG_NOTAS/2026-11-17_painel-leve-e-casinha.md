# 2026-11-17 — Painel leve (sem flicker) + logo Início vira casinha

Correções de performance e um ajuste de identidade visual pedidos ao
vivo: o painel "piscava" e pesava, e o ícone Início tinha animações demais.

## Causa do flicker

`atualizarCores()` em `ilha.js` escrevia as variáveis `--a1`, `--a2` e
`--giro-s` no `:root` **a cada frame** (~60×/s), mesmo com os valores
já convergidos. Cada escrita em variável de `:root` invalida o estilo da
ilha inteira — repaint constante de bordas, sombras e textos = shimmer
percebido como "piscando", além do custo.

- Agora as três variáveis só são escritas quando o valor **muda**
  (cache em `ultimoCss`). Convergidas, zero escrita — a ilha para de
  repintar no ocioso e o gradiente ainda flui nas transições de humor.
- `nucleo.dataset.humor` também só é atribuído quando muda.

## Peso: só roda o que está na tela

- **Logo Início**: era um `<canvas>` que copiava o rosto vivo do mascote
  a 60 fps (`avatar.copiar()` + `ajustarCanvas` por frame). Removido o
  módulo inteiro — virou **casinha em SVG** igual aos outros ícones do
  dock (com o pontinho de status preservado).
- **Gráfico + mini-onda da Home**: desenhavam a 60 fps; agora a ~30 fps
  (imperceptível, metade do custo).
- **Relógio do estúdio de som** (`#gv-tempo`): um `setInterval` de 100 ms
  escrevia no DOM o tempo todo, mesmo com a aba Som fechada — agora só
  toca o DOM quando a aba está aberta (a contagem interna continua).
- O que já era lazy continua lazy: estúdio só na aba Som, vibra só no
  chat, cérebro só na aba Cérebro, Jorgito só no chat, orbe a 30 fps no
  ocioso, iframes (grade/eslabon) só carregam ao abrir.

## Arquivos

- `pestinha/ui/web/index.html` — botão Início com SVG de casa;
  cache-buster `?v=…c`.
- `pestinha/ui/web/ilha.js` — removido módulo `avatar`; `atualizarCores`
  com cache de escrita; `ultimoHome` (30 fps na Home); intervalo do
  contador de áudio gated por aba.
- `pestinha/ui/web/ilha.css` — `#avatar-cv` removido; `.dock .avatar svg`
  dimensiona a casinha.

Cache-buster atualizado para `?v=2026-11-17c` (regra do PADRAO_UI).
