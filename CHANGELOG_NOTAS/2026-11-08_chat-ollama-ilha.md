# Chat local com Ollama — Laboratório estilo Coucou

## Objetivo

Adicionar uma conversa com modelos locais à ilha flutuante do Pestinha, sem
abrir uma janela convencional, sem enviar prompts à internet e sem bloquear a
animação enquanto o Ollama lista modelos ou gera uma resposta.

## Funcionalidades

- Nova aba **Chat local** ao lado da visão geral da ilha.
- Seletor preenchido automaticamente com os modelos instalados no servidor
  local, botão para atualizar e preferência de modelo salva em
  `memory/permissions.json` (`ollama_chat_modelo`).
- Histórico de conversa em console limpo, campo de texto com `Ctrl+Enter` para
  envio, botão **Enviar** e resposta exibida incrementalmente enquanto o modelo
  transmite conteúdo.
- Botão **Analisar resultados** anexa, somente quando clicado, um snapshot
  resumido (emoção, atividade, energia, estimulação, insatisfação, estágio de
  protesto e até 12 logs recentes limitados a 500 caracteres cada).
- O Ollama é acessado exclusivamente em `http://127.0.0.1:11434`:
  `GET /v1/models` lista modelos e `POST /api/chat` transmite a conversa.
- Falhas de conexão exibem dentro da aba: **“Ollama desconectado. Inicie o
  serviço local.”** A interface continua responsiva.

## Arquitetura

- `pestinha/mind/ollama_local.py`: fachada assíncrona; listagem e geração HTTP
  rodam em threads daemon limitadas a duas solicitações simultâneas. Tokens e
  resultados voltam à UI por sinais Qt; cancelamento fecha a resposta ativa.
- `pestinha/ui/ilha.py`: constrói a aba, o seletor, histórico, compositor e
  botão de contexto; a thread principal apenas atualiza widgets.
- `pestinha/config.py`: adiciona a preferência `ollama_chat_modelo`.
- `requirements.txt`: declara `requests>=2.32.3` e `chardet>=5.2,<6`;
  streaming usa a API HTTP local do Ollama e não depende de uma versão
  específica do pacote cliente.

## Revisão da entrada e saída de voz

- O campo do chat alterna a janela de frameless sem foco para foco temporário
  apenas quando a aba é escolhida ou clicada, permitindo digitar sem deixar a
  pílula roubar teclado no estado compacto.
- A aba inclui botão de microfone para transcrição offline do Windows com
  `System.Speech` em `pt-BR`, e opção para falar respostas usando o sintetizador
  local. Processos são ocultos, executados em worker, canceláveis e não gravam
  áudio.
- O seletor segue o catálogo OpenAI-compatible `/v1/models`, filtra modelos de
  embedding e só anexa `Authorization` se `OLLAMA_API_KEY` estiver definida.

## Privacidade e limites

- O host está fixo em loopback (`127.0.0.1`); não existe configuração de host
  remoto nem tráfego para serviços externos.
- Métricas e logs só entram no prompt quando o usuário aciona **Analisar
  resultados**. Chat normal envia apenas a conversa.
- O histórico é mantido em memória durante a sessão. O conteúdo de chat não é
  salvo na memória do Pestinha.
- Esta thread isola a rede do chat e a geração do modelo. O ciclo neural
  original do Pestinha permanece na thread Qt devido aos seus efeitos em
  controladores e widgets; ele não é movido por esta integração.

## Verificação

- Testes mockados cobrem `/api/tags`, streaming, falha de conexão, execução em
  worker secundário, troca de modelo, contexto explícito e renderização
  incremental.
- Nenhum teste chama um Ollama real ou transmite dados para fora da máquina.
- Suíte completa: **427 passaram, 5 skipped**; Pyflakes sem apontamentos.
- O ambiente local emitiu um `RequestsDependencyWarning` por incompatibilidade
  pré-existente entre `urllib3` e `charset_normalizer`; não falhou nenhum teste.
