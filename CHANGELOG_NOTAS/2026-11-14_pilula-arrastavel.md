# 2026-11-14 — Pílula arrastável

## O que mudou
- Segurando a barra da pílula (data, orbe, hora) e movendo o mouse, a ilha vai para qualquer
  lugar da tela. A janela acompanha o cursor.
- Limite de 4 px: um clique simples continua abrindo a ilha (orbe e balão), e o clique que vem
  logo depois de um arraste é ignorado.
- Posição salva em `memory/web_posicao.json` (só x e y). Ao abrir, a pílula volta ao último lugar;
  se o monitor sumiu, ela é trazida de volta para a tela, com 120 px sempre visíveis na horizontal.
- Cursor de mão na barra.

## Arquivos
- `pestinha/ui/web_island.py`: `limitar_posicao`, `mover_por`, salvar e ler a posição.
- `pestinha/ui/web_bridge.py`: sinais `movimento` e `soltou`, e os slots `arrastar` e `soltar`.
- `pestinha/ui/web/ilha.js` e `ilha.css`: arraste pela barra e cursor.
- `tests/test_web_island.py`: limites da posição.

## Testes
- Testes da ilha: 11 passam. Arraste verificado na página renderizada: (+200, +100) no mouse
  moveu a janela (+200, +100) e salvou a posição.
- Limitação: o arraste não foi testado com o mouse físico, só com eventos de ponteiro sintéticos.

## Privacidade
- `web_posicao.json` guarda só coordenadas da tela. Nada sai do PC.
