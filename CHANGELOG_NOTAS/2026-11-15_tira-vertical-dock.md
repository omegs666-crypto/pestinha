# 2026-11-15 — Navegação da ilha vira tira vertical (estilo da foto 1 do usuário)

## O que mudou
- `pestinha/ui/web/index.html`: o dock deixou de ser barra horizontal embaixo e virou uma tira
  vertical na lateral esquerda do painel: avatar do pet no topo (é o botão Início, com sinal de
  status na cor do humor), ícones das vistas (Som, Grade, Diagramas, Chat, Controles — agora um
  deslizador no estilo da foto), separadores, Monitor neural (cristal), Laboratório MLP (frasco),
  Fixar (alfinete), Recolher (chevron) e uma alça de arraste no rodapé.
- `pestinha/ui/web/ilha.css`: `.corpo` desloca para a direita da tira; `.dock` vertical com
  tooltips para a direita, indicador de vista ativa na borda esquerda, avatar circular e alça.
- `pestinha/ui/web/ilha.js`: a lupa do dock mede a distância no eixo Y; o avatar copia o rosto do
  mascote a cada quadro (pisca e olha junto); a alça usa o mesmo gesto de arraste da barra;
  `TAM.home` cresceu para 480 px de altura para a tira caber.
- `moxen/parrilla/parrilla.css`: paleta da grade estreitou (250 → 204 px) para a área de widgets
  continuar acima do ponto de 12 colunas na largura nova.

## Verificação
- Capturas reais (home, chat, grade, controles): tira visível à esquerda, avatar com o rosto do
  pet, grade em 12 colunas (área de widgets ~653 px, acima do limite de 640).
- Suíte: 540 testes, pyflakes e sintaxe JS limpos.

## Limitações
- Gesto de arraste pela alça validado por código, não com o mouse físico.
- Na vista Início os cards ficaram mais altos (a tira pediu ~480 px de painel).
