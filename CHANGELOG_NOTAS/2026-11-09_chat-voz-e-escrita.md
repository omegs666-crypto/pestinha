# Chat local — correção de digitação, catálogo de modelos e voz

## Diagnóstico

O editor do chat era filho de uma janela criada com `Qt.WindowDoesNotAcceptFocus`.
Além disso, a janela nativa do Windows recebia `WS_EX_NOACTIVATE` em todos os
`showEvent`s. O editor aparecia, mas não podia receber foco de teclado — causa
da falha ao escrever. A busca de modelos também usava `/api/tags`, enquanto o
fluxo pedido para o chat usa a API OpenAI-compatible `/v1/models`.

## Correções

- O foco continua bloqueado no estado compacto. Ao abrir a aba Chat local ou
  clicar na aba já selecionada, a ilha libera foco temporariamente, ativa o
  editor e devolve o modo sem foco ao recolher/esconder.
- Adicionada `com_foco_nativo()` aos adaptadores de plataforma; no Windows
  remove `WS_EX_NOACTIVATE` para a sessão de digitação, mantendo a janela
  frameless/topmost.
- O catálogo consulta `GET http://127.0.0.1:11434/v1/models`, aceita o formato
  `data[].id`, filtra modelos de embedding e usa o fallback de normalização
  Ollama tradicional. `OLLAMA_API_KEY`, quando definida no ambiente, é enviada
  como Bearer apenas ao loopback; proxies e redirects são desativados.
- Chat ganha **Falar** (transcrição offline `System.Speech`, Windows `pt-BR`)
  e **Ler respostas** (síntese local do sistema). Entrada só grava/usa áudio
  durante a ação explícita do usuário; áudio não é persistido nem enviado à rede.
- O subprocesso PowerShell usa `CREATE_NO_WINDOW`, argumentos codificados e
  timeout. Workers de voz são cancelados ao ocultar/encerrar a ilha.

## Arquivos

- `pestinha/ui/ilha.py`: foco temporário, detecção de clique na aba, botões de
  microfone/voz e ligação da transcrição ao envio de prompt.
- `pestinha/mind/ollama_local.py`: `/v1/models`, autenticação opcional local e
  proteção contra proxy/redirect.
- `pestinha/mind/chat_voice.py`: reconhecimento/síntese local em subprocesso
  oculto e worker daemon cancelável.
- `pestinha/plataforma/{__init__,windows,linux,macos}.py`: API de foco
  temporário.
- `PRIVACIDADE.md`: documenta microfone, contexto enviado ao modelo e retenção.

## Testes e limites

- Testes simulam `/v1/models`, Bearer opcional, foco de teclado, transcrição,
  síntese e streaming; não usam Ollama real nem microfone real.
- Entrada por voz é habilitada no Windows e requer pacote de reconhecimento
  offline `pt-BR`; em outros sistemas o botão fica indisponível com explicação.
- No Windows, a mudança temporária de foco recria a janela frameless ao entrar
  ou sair do modo chat; não altera a animação de hover/expansão.
- Pyflakes limpo e suíte completa: **454 passaram, 5 skipped**. O ambiente de
  desenvolvimento ainda tem `requests 2.31.0` incompatível com as versões
  instaladas de `urllib3`/`chardet`; os requisitos agora pedem versões
  compatíveis, mas não foram atualizados via rede durante esta tarefa.
