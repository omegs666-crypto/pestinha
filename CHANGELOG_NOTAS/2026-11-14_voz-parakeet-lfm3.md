# 2026-11-14 — Voz: ouvir com Parakeet e responder com a voz do LLM (como o Coucou)

## Diagnóstico
- **Ouvir não funcionava:** o Windows desta máquina não tem nenhum reconhecedor de fala instalado
  (`InstalledRecognizers` vazio); o botão Falar dependia dele.
- **A voz do LLM não era usada:** a ilha escolhia o modelo de voz pelo nome (tts, kokoro…) e caía no modelo do
  chat, que responde 400 em `/v1/audio/speech`. Só o `lfm3-omni` tem a capacidade `speech`.
- O WAV que o Ollama manda em streaming vem com tamanhos `0xFFFFFFFF`, e o texto ia inteiro numa requisição só.

## O que mudou (seguindo `coucou-main/windows/src-tauri/src/local_chat.rs` e `speech/mod.rs`)
- **Fala** (`mind/ollama_local.py`): escolhe o modelo pela capacidade `speech` (`/api/show`), começando pelo
  do chat e depois os instalados; uma requisição por frase (no máximo 12); cabeçalho WAV corrigido; frases
  unidas num WAV só. Sem modelo com voz: avisa e usa a voz do Windows.
- **Ouvir** (`sense/ouvir.py`, novo): Parakeet TDT 0.6B v3 int8 via `sherpa-onnx` 1.13.8 (mesma versão e
  mesmos arquivos fixos do Coucou, conferidos por SHA-256). Download só pelo botão **Baixar** na ilha, com
  progresso, em `%LOCALAPPDATA%\Pestinha\Models`. Gravação do microfone com detecção de fala por energia
  (para em 1,2 s de silêncio, máximo 12 s). Áudio só na memória.
- **Chat**: perguntou falando, a resposta é falada (sem precisar marcar "Ler respostas"). O botão mostra
  "Ouvindo…" e "Entendendo…"; clicar de novo para a escuta.
- Arraste da pílula não abre mais a ilha (commit separado `5afddeb`).

## Testes
- `tests/test_ouvir.py` (8) e 5 testes novos de voz em `tests/test_ollama_local.py`.

## Limitações
- A fala do lfm3-omni foi lenta nesta máquina (minutos por frase) durante o teste, com um jogo usando a GPU.
  A requisição por frase ajuda, mas a velocidade depende do hardware livre.
- O Parakeet não foi testado com a sua voz: o modelo ainda não foi baixado (só baixa quando você clicar).
