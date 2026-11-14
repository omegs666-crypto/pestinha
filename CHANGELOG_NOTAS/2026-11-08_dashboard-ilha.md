# 2026-11-08 — Dashboard flutuante em formato Dynamic Island

## Objetivo

Reformar a ilha como uma interface real de controle, mantendo o backend e a
identidade escura/minimalista inspirada no Coucou. A janela é frameless,
ancorada ao topo e expande por hover ou clique.

## Mudanças

- `pestinha/ui/ilha.py` foi refeito como dashboard de três colunas:
  - **Controles:** pausar/retomar o pet, ligar/desligar voz e travessuras,
    ajustar o atraso de recolhimento e abrir o monitor neural/protesto.
  - **Gráfico:** seletor de métrica e séries recentes de energia,
    insatisfação, estimulação e atividade neural.
  - **Eventos:** console local que combina ações da interface com mensagens
    recentes do logger do projeto.
- A cápsula compacta mostra o pet, nome, estado e relógio. Hover abre o
  dashboard após 320 ms; clique abre/fecha. A janela anima o tamanho, respeita
  o monitor do pet e continua arrastável/persistente.
- `pestinha/ui/ilha.py` desenha o gráfico com QPainter. Matplotlib não foi
  adicionado: o repositório não o usa e o gráfico é pequeno, portanto a pintura
  nativa evita peso de inicialização e dependência adicional.
- `pestinha/log.py` mantém uma fila recente, limitada e protegida por lock.
  A ilha lê essa fila em memória; não lê arquivos nem faz I/O síncrono durante
  a atualização da interface.
- `tests/test_ilha.py` cobre abertura por hover/clique, layout de três colunas,
  controles conectados ao backend, seletor/snapshot do gráfico e logs.

## Integração e limites de threading

Os controles chamam as APIs existentes (`toggle_pause`, `apply_perms` e
`FloatManager.toggle`). O dashboard apenas lê snapshots pequenos do estado e
atualiza em intervalo de 500 ms; não executa rede, HTTP, Matplotlib, leitura de
arquivos ou simulação no caminho de pintura.

O ciclo original `PestinhaApp.think()` continua no `QTimer` da thread Qt:
ele também altera controladores e cria/atualiza widgets, então movê-lo
diretamente para uma thread worker causaria acesso cruzado a `QWidget` e corrida
entre cérebro, física e interação. Uma migração segura do backend neural para
worker exige separar o modelo puro dos efeitos Qt e publicar snapshots por
sinais; não foi mascarada como concluída nesta mudança.

## Verificação

- `pyflakes pestinha tests main.py ferramentas conftest.py`: limpo.
- `pytest tests/test_ilha.py tests/test_paineis.py tests/test_app.py
  tests/test_voz.py`: 35 passaram.
- Suíte completa: **415 passaram, 5 skipped**.
