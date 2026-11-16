# 2026-11-15 — Mover a ilha ficou fácil: deslize no topo, desgrudar tolerante e painel arrastável

## O que travava
- Encostada no topo, o Python ignorava todo arraste (`mover_por` só agia em modo livre).
- Desgrudar exigia puxada quase vertical (18 px, e vertical > horizontal).
- Só a barra de 46 px e a alça fina da tira aceitavam arraste; o painel aberto não respondia.

## O que mudou
- `web_island.py::mover_por`: encostada, a ilha desliza na horizontal pelo topo (dy ignorado);
  em modo livre move em qualquer direção, como antes.
- `web_island.py::_posicionar`: o deslize horizontal no topo é salvo e restaurado na próxima
  abertura (o arquivo já guardava `modo`, agora o `x` do modo topo também vale).
- `ilha.js`: o arraste começa em qualquer área vazia do núcleo — fundo do painel, áreas entre
  controles, espaços da barra, a alça da tira. Elementos interativos não arrastam (botões,
  campos, listas com rolagem, canvas, iframe, o trilho de cards que tem arraste próprio).
- Desgrudar mais tolerante: 14 px para baixo já solta, e diagonal conta (vertical > 60% do
  horizontal).
- `ilha.css`: cursor `grab`/`grabbing` nas áreas arrastáveis; alça da tira com área de toque
  maior (18 px) mantendo o traço fino.

## Verificação (eventos de ponteiro reais)
- Encostada: arraste horizontal moveu 440 → 540 e continuou `topo`.
- Puxada diagonal desgrudou para `livre`.
- Arrastar de volta ao topo reencaixou e recentralizou.
- Arraste começando no fundo de um cartão do painel moveu a ilha encostada.
- Suíte: 540 testes, pyflakes e sintaxe JS limpos.

## Limitações
- O trilho de cards (vista Início) continua com arraste próprio horizontal; ali a ilha se move
  pela barra, pela tira ou pelo rodapé.
