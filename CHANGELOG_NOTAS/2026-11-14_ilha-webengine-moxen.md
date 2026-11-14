# 2026-11-14 — Ilha em WebEngine com Moxen e áudio do sistema

## Objetivo

Trocar a ilha nativa por uma interface HTML no estilo Coucou (pílula preta no topo da tela,
expansão suave, cartões escuros), integrando os três componentes Moxen (Parrilla, Eslabón e
Centro), um painel de música com visualizador ligado ao áudio do sistema e o chat local.

## Arquitetura

- `pestinha/ui/web_island.py` — `WebIlha`: janela frameless, sempre no topo, centralizada no topo
  da tela. Hospeda um `QWebEngineView`; a expansão anima a geometria da janela (260 ms, OutCubic).
  `criar_ilha(app)` escolhe a ilha WebEngine (padrão, perm `ilha_web`) ou a nativa `Ilha`
  como fallback quando o WebEngine não está instalado.
- `pestinha/ui/web_bridge.py` — `Ponte`, registrada no QWebChannel como `ponte`. A página só pode
  pedir ações de uma lista fixa (`acao`, `painel`, `salvar`, `carregar`, chat, voz, áudio). Estado
  do backend sai a cada 500 ms, só enquanto a ilha está visível. Persistência restrita a `layout` e
  `diagrama`, sempre validada como JSON e limitada a 200 KB, em `memory/web_<nome>.json`.
- `pestinha/sense/audio.py` — `analisar()` (função pura: FFT, 24 bandas em escala logarítmica,
  RMS e pico; entradas inválidas viram zeros) e `CapturaLoopback` (QThread com `soundcard` 0.4.6,
  loopback do sistema). Nada é gravado.
- `pestinha/ui/web/` — `index.html`, `ilha.css` e `ilha.js`: casca da ilha, abas, cartão do
  chat, espectro em canvas e ligação com os quadros dos Moxen (via `postMessage`).
- `pestinha/ui/web/moxen/{centro,parrilla,eslabon}/` — cópias dos Moxen com o texto visível em
  português, fontes externas removidas e hooks para o backend. Cada um roda num `iframe` isolado
  e só é carregado quando sua aba é aberta.

## Moxen (Parrilla, Eslabón e Centro)

- Textos da interface traduzidos (espanhol → português). Comentários de código de terceiros
  continuam em espanhol.
- Removidos os links de Google Fonts e Fontshare (o app é local-first; teste automatizado impede
  recursos externos em `ui/web/`).
- **Parrilla**: os widgets de demonstração (vendas, visitas) foram trocados por métricas do pet
  (energia, atividade neural, estímulo, logs recentes) atualizadas ao vivo. A disposição é salva
  pela ilha e restaurada na abertura. Os mini-gráficos decorativos continuam sendo demonstração.
- **Eslabón**: o fluxo "Aviso de pedido novo" é um exemplo. Cada alteração é salva em
  `web_diagrama.json` e recarregada na próxima abertura.
- **Centro**: o reprodutor de demonstração foi substituído pelo cartão **Áudio do sistema**, com
  barras reagindo ao espectro real. "Avião" desliga o chat local (modo offline). "Foco" pausa o pet.
  Brilho, volume, rede, perto, dados, lanterna e rotação continuam visuais, sem efeito no backend.

## Painel de música

- Aba **Música**: botão "Iniciar áudio" liga a captura do loopback do sistema. Espectro de 24
  bandas, nível RMS e pico, em canvas com gradiente ciano/azul.
- Se não houver dispositivo de saída ou a biblioteca faltar, a aba mostra a mensagem
  "Áudio do sistema indisponível" sem derrubar a ilha.

## Chat

- Mesmo backend do chat anterior (`OllamaLocal`, `ChatVoice`), agora na ponte: streaming, cancelamento,
  seletor de modelo (preferência salva no perfil local), histórico de 20 mensagens, "Analisar
  resultados" com métricas e 12 logs recentes, entrada por voz ("Falar") e "Ler respostas".
- Erro de conexão ("Ollama desconectado. Inicie o serviço local.") fica visível até o serviço voltar.

## Dependências

- `requirements.txt`: `PySide6-Addons>=6.11.0`, `PySide6-WebEngine>=6.11.0`, `soundcard==0.4.6`.
- O WebEngine vem em pacotes separados do Essentials. Os números de versão do WebEngine são do tipo
  `6.12.0.140`; use a mesma versão maior do PySide6 instalado.

## Testes

- `tests/test_web_island.py` (novo): espectro com tom conhecido e entradas inválidas; lista
  permitida de ações; modo avião e mensagens malformadas; fallback da voz; persistência validada;
  dados corrompidos viram zero; ausência de recursos externos; factory; carregamento da página com
  os três quadros e o QWebChannel.
- `tests/test_ilha.py`: passa a forçar a ilha nativa (`WEB_OK=False`), porque testa a classe nativa.
- Suíte completa: ver resultado no fim da sessão.

## Correções encontradas durante a verificação

- **Botão Enviar do chat nativo quebrava sempre** (`pestinha/ui/ilha.py`): `clicked` passa o
  argumento `checked` (False) para `_enviar_chat(prompt=...)`, que chamava `.strip()` nele
  (`AttributeError: 'bool' object has no attribute 'strip'`). Agora o botão chama o método sem
  argumentos. Teste de regressão: `test_botao_enviar_do_chat_envia_o_texto_digitado`. Provavelmente
  era a falha de "escrever no chat" relatada antes.
- **Testes dependentes da área de trabalho** (`tests/test_ilha.py`, `tests/test_app.py`,
  `tests/test_paineis.py`): os painéis e a ilha se escondem quando algo está em tela cheia (regra do
  app). Os testes agora isolam esse estado com `is_fullscreen` fixo em `False`, como outros testes
  do projeto já faziam. Antes, passavam ou falhavam conforme o que estava aberto no PC.

## Limitações conhecidas

- A janela WebEngine ativa o Pestinha ao ser clicada (a ilha nativa evitava roubar o foco).
- Os toggles do Centro são locais: se a voz ou as travessuras mudarem pelo menu da bandeja, o
  painel não reflete a mudança até a próxima ação.
- Não testado com Ollama real nesta máquina (o serviço não estava rodando); o caminho de erro foi verificado.
- Captura do áudio validada apenas com a saída padrão do Windows (WASAPI loopback).
