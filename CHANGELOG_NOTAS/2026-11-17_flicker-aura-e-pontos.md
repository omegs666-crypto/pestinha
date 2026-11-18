# 2026-11-17 — Fim do flicker real (aura + backdrop-filter) e dos pontos azuis

Continuação do alívio do painel: a causa profunda do "painel inteiro
piscando" não era o repaint das cores — era renderização.

## O que piscava

1. **`.aura` (borda de luz da pílula)**: um conic-gradient girando
   (`transform: rotate`) **sob `-webkit-mask` + `mask-composite: xor`**.
   Máscara força re-rasterização a cada frame — no QWebEngine translúcido
   do Windows, isso vira recomposição da superfície inteira = flicker do
   painel todo, 60×/s, mais CPU de graça.
   → Removido o `girar`. A borda continua colorida (cyan+violeta) e
   **respirando** (opacity, que é compositor puro — zero repaint).
   `girar`, `--giro-s`, `@property --giro` e a escrita do JS removidos.
2. **`backdrop-filter: blur(18px)`** em `.card, .chat, .fluxos,
   .gv-principal, .gv-lista, .ctl, .escolha-lista`: os fundos já são ~88%
   opacos (`--vidro-2`), o blur era praticamente invisível — mas é a
   operação de render mais cara que existe e, em janela translúcida, um
   clássico gerador de flicker.
   → Removido. Visual praticamente idêntico, custo zerado.

## Os 2 pontos azuis no Início

- `.avatar .sinal` (dot ciano de status no canto do botão) — elemento
  removido do HTML.
- `.dock button.ativo::after` (dot ciano de "aba atual" na borda
  esquerda) — escondido só no botão `.avatar` (`display: none`); nos
  demais botões o marcador continua.

## Arquivos

- `pestinha/ui/web/ilha.css` — aura sem giro, backdrop-filter removido,
  pontos do avatar removidos.
- `pestinha/ui/web/ilha.js` — escrita de `--giro-s` removida.
- `pestinha/ui/web/index.html` — `<i class="sinal">` fora do botão
  Início; cache-buster `?v=2026-11-17d`.
