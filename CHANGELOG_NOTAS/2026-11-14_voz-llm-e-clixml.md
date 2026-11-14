# 2026-11-14 — Voz do próprio LLM + correção do erro CLIXML

## Problema

1. O chat mostrava `Voz local indisponível: #< CLIXML <Objs ...>` — o PowerShell
   serializa registros de erro como CLIXML quando o stderr é redirecionado, e esse
   ruído técnico era exibido cru na ilha.
2. A leitura de respostas ("Ler respostas") usava apenas a voz do sistema
   (System.Speech). O pedido era usar a voz do próprio LLM local, como no Coucou
   (`/v1/audio/speech`).

## Mudanças

### `pestinha/mind/ollama_local.py`
- Nova operação `speech` no `_OllamaTask`: `POST {OLLAMA_HOST}/v1/audio/speech`
  com `{"model", "input", "response_format": "wav"}`, mesmo session sem proxy,
  sem redirects, Bearer opcional via `OLLAMA_API_KEY`.
- Limites: texto até `MAX_SPEECH_TEXT` (4.000 chars), áudio até
  `MAX_SPEECH_BYTES` (8 MB), timeout `(2, 60)`; valida cabeçalho `RIFF/WAVE`.
- Cancelável via `_cancelled`/`response.close()` como as demais operações.
- `OllamaLocal.speak_async(model, text)` + sinais `speech_ready(bytes)` e
  `speech_failed(str)`. O aviso de "fila cheia" agora sai pelo sinal de erro da
  própria tarefa, então uma fala não acende o status de erro do chat.

### `pestinha/mind/chat_voice.py`
- Scripts PowerShell de escuta e fala embrulhados em `try/catch` que escreve a
  mensagem real em `[Console]::Error.WriteLine` — elimina a serialização CLIXML.
- `_run` sanitiza stderr: qualquer resto de CLIXML vira a mensagem genérica
  "O mecanismo local de voz falhou."
- Novo `play_wav(data)`: valida RIFF/WAVE, grava WAV temporário e toca em
  processo oculto (`SoundPlayer.PlaySync()` no Windows, `afplay` no macOS,
  `paplay`/`aplay` no Linux). O temporário é apagado ao final, mesmo em erro.

### `pestinha/ui/ilha.py`
- "Ler respostas" agora chama `_falar_resposta()`: tenta primeiro
  `OllamaLocal.speak_async()` com `_modelo_voz()` — que prefere modelos com
  "tts", "kokoro", "piper", "f5-", "chattts" ou "speech" no nome e cai para o
  modelo do chat.
- `_voz_llm_falhou()`: se o endpoint de voz não existir/ falhar, registra no
  console de eventos e faz fallback automático para a voz do sistema
  (`ChatVoice.speak`). `_tts_llm_ok` é rearmado quando a lista de modelos
  atualiza.

## Verificação
- `pyflakes` limpo nos arquivos alterados.
- Novos testes: speech WAV ok, rejeição de não-WAV, `play_wav` com
  temporário removido, rejeição de áudio inválido, CLIXML sanitizado.
- Suíte completa: **459 passed, 5 skipped** (1 warning de compatibilidade
  `requests`/`urllib3` já conhecido).

## Observação
- A **entrada** de voz continua sendo o reconhecimento local pt-BR do Windows
  (Ollama não oferece STT local). Só a **saída** usa a voz do LLM.
- Se o Ollama local não tiver modelo de TTS, o `/v1/audio/speech` responde erro
  e o fallback para a voz do sistema é automático — nada quebra.
