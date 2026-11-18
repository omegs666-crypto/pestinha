# Pílula: mini-faixa igual ao rodapé + personas nas pontas + abrir só no clique

## O que mudou

- **A pílula fechada no topo agora tem o mesmo tamanho da mini-faixa do rodapé** (250×32, r16): `TAM.compacta` igual a `TAM.rodape`. O visual da mini-faixa (trio encolhido, sem data/hora, balão compacto) passou a valer para **todo** estado fechado — topo, livre e rodapé — unificando os seletores `.nucleo.rodape:not(.aberto)` em `.nucleo:not(.aberto)`.
- **Personas nas pontas** (`(P)___(N)___(P)`): o `#jorge-ilha` passou para depois do `.balao` no DOM e, fechada, `.meio` ocupa a barra inteira com `margin-right:auto` no mascote e `margin-left:auto` no Jorge — Bryan colado à esquerda, orbe+balão centralizados, Jorge colado à direita.
- **Abrir só no clique**: removido o `mouseenter` que abria após 260 ms — passar o mouse por cima não abre mais nada. O orbe e o balão continuam abrindo no clique; voltar com o mouse só **segura** o painel aberto (cancela a contagem de recolher), sair recomeça a contagem.

## Arquivos

- `index.html`: `#jorge-ilha` movido para o fim do `.meio`; cache-buster `?v=2026-11-18b`.
- `ilha.css`: regras da mini-faixa unificadas para todo estado fechado + personas nos extremos.
- `ilha.js`: `TAM.compacta` = mini-faixa; `timerAbrir` e o agendamento de abertura por hover removidos.

## Verificação

- `node --check` OK.
- Captura de tela real: a mini-faixa no rodapé mostra Bryan à esquerda, orbe ao centro, Jorge à direita — o desenho `(P)___(N)___(P)`.
