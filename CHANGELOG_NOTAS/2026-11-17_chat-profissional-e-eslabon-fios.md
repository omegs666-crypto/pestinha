# 2026-11-17 — Chat profissional (lfm3-omni fixa) + Eslabon com caixas soltas e fios

Duas frentes do plano `docs/PLANO_CHAT_DIAGRAMA.md`, executadas por inteiro.

## Chat (aba Conversas)

- **Modelo fixo `lfm3-omni`** — `pestinha/config.py`: `ollama_chat_modelo`.
  O seletor do chat agora só indica o modelo (desabilitado); sem ela
  instalada, um chip "Baixar lfm3-omni" aparece e baixa via `ollama pull`
  com progresso em %.
- **`ollama_local.py`** — nova operação `pull` (`POST /api/pull`, JSONL
  com `completed`/`total` por camada → sinais `progress`/`pull_done`);
  `pull_async()` na fachada. A ponte expõe `modelo_pull` + slot
  `baixar_modelo`.
- **Layout em 2 colunas** (`index.html` + `ilha.css`): à esquerda a
  conversa (mensagens com avatar, meta "Você/Jorge · hora", corpo em
  markdown — títulos, listas, código, negrito — e indicador de digitação);
  à direita a **ficha do Jorge**: avatar desenhado, status
  pronto/pensando/escrevendo, modelo, voz, barra de contexto da sessão,
  atividade, "Exportar conversa" (salva `.md`) e "Limpar".
- **Enter envia, Shift+Enter quebra linha** — era Ctrl+Enter.
- **"Falar" (voz de entrada)** — `sense/ouvir.py`: parar a gravação
  agora **transcreve o que foi capturado** (antes `requestInterruption`
  descartava o áudio). Se a LLM estiver respondendo, a transcrição fica na
  caixa e é enviada ao fim (antes se perdia). Botão ganha estados
  gravando/transcrevendo com pulso e a barra de vibração informa.
- **Arquivos criados pela IA** — permissão `ia_arquivos` (padrão ligada).
  O system prompt do Jorge instrui: para entregar arquivo, responda um
  bloco ` ```arquivo:nome.ext``` `. O renderer vira cartão de anexo com
  **Baixar** (grava em `~/Downloads/Pestinha/`, nome desduplicado
  `arquivo-1.ext`…) e **Salvar como…** (QFileDialog nativo). Slots:
  `salvar_arquivo` / `salvar_arquivo_como` em `web_bridge.py`; nome
  sanitizado com `Path(nome).name`, conteúdo limitado a 2 MB.
- Mantidos: streaming, "Ler respostas" (TTS do modelo → fallback voz do
  sistema), animações de fala/vibração, Jorgito no topo.

## Diagrama (aba Fluxos → Diagrama livre) — opção A, linear

- **Paleta lateral** (`eslabon/index.html` + JS): 5 tipos de passo;
  **arraste um tipo** e a caixa nasce **solta** onde você soltar, com
  posição própria `(x, y)` e selo âmbar **"solto"** (borda tracejada).
  **Duplo clique no vazio** abre o menu de tipos e cria solta ali.
- **Portas de saída**: todo nó ganha uma bolinha na borda direita — o
  `Si…` tem duas ("Sim"/"Não"). **Puxe o fio** (bezier tracejado animado)
  e solte:
  - **numa caixa solta** → ela entra na sequência logo após a origem
    (ou no ramo escolhido do Si…) — o resorte a realinha no fluxo;
  - **num passo ligado** → menu de tipos no ponto; o novo nasce ligado
    depois dele;
  - **num cabo** → o passo novo nasce no meio do cabo, ligado dos dois
    lados;
  - **no vazio** → menu de tipos; o novo nasce ligado à origem.
- **Arrastar a solta** move-a livre; sobre o fluxo, o cabo/passo mais
  próximo **acende (imã)** e soltar conecta ali.
- `Si…` solto dentro de ramo é recusado (regra "só uma bifurcação") — a
  caixa **volta a ser solta** em vez de sumir.
- **Persistência**: `web_diagrama.json` agora é `{flujo, soltos:[{id,
  tipo, campos, x, y}]}`; saves antigos (só `flujo`) abrem normal.
  `Restaurar` recria as soltas do save. O selo de estado conta
  "· N caixas soltas".
- Execução **inalterada**: o `Testar` continua linear/ramificado; soltos
  não executam até conectar. O "+" entre passos continua funcionando.
- A variante "grafo livre" (opção B) ficou registrada como futuro em
  `docs/POSSIVEIS_ATUALIZACOES.md` (F1).

## Testes e validação

- `pytest`: 402 testes, 1 expectativa atualizada em
  `tests/test_narrador.py` (insight do narrador sai com `origem: jorge`
  desde a Fase 1 dos dois cérebros).
- `node --check` em `ilha.js` e `eslabon.js`; `py_compile` nos Python.
- Funcional do eslabon (eventos de ponteiro sintéticos): paleta cria
  solto → fio da porta conecta → save serializa `{flujo, soltos}` →
  solto restaura na reabertura.
- Cache-buster: `ilha.css?v=…b`, `ilha.js?v=…b`.
