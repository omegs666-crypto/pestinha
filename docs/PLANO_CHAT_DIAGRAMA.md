# Plano — Chat profissional com LFM3 + Diagrama "criar e puxar o fio"

Duas frentes pedidas: remodelar a aba **Chat** (fixa na LFM3, visual
profissional estilo o print de referência) e evoluir a aba **Diagramas**
(criar nó solto e conectar arrastando o fio, estilo n8n). Execução só após
liberação.

---

## Frente A — Aba Chat (referência: print WhatsApp + ficha lateral)

### A1 · Modelo fixo LFM3
- `config.py`: `ollama_chat_modelo` passa a default `"lfm3"` — o chat abre já
  falando com ela, sem precisar escolher.
- Se a lfm3 **não estiver instalada**: o seletor mostra "Baixar lfm3" e a
  ponte chama `POST /api/pull` do Ollama (streaming de progresso, mesmo
  padrão do `Baixador` do Parakeet) — barra de % na ilha até ficar pronta.
- Seletor de modelo continua existindo, mas recolhido ("trocar modelo" na
  ficha) — a lfm3 é a cara do chat.
- `falar_resposta` já prioriza `lfm3-omni` para a voz — fica coerente.

### A2 · Remodelação visual (layout de 2 colunas, como o print)
- **Coluna esquerda — a conversa**:
  - Bolhas profissionais: você à direita (ciano), Jorge à esquerda (dourado)
    com avatar + nome + hora em cada grupo de mensagens.
  - Indicador de digitação: bolha do Jorge com **3 pontinhos animados**
    (substitui o "…" de hoje).
  - Markdown nas respostas: **negrito**, listas e `blocos de código` com
    botão copiar — o chat deixa de ser texto puro.
  - Separador de dia quando a conversa cruza meia-noite.
  - Mantém: animação de fala (vibra + Jorge pulsando + bolha crescendo no
    streaming) e o toggle **"Ler respostas"**.
- **Coluna direita — a "Ficha"** (o cartão Patrícia do print, versão nossa):
  - Avatar do Jorge + nome + chip de status (pronto / pensando / falando).
  - **Barra de contexto usado** (`histórico ÷ MAX_HISTORICO`) — igual à
    barrinha "100%" do print, mas útil de verdade.
  - Campos: modelo (lfm3), voz (lfm3-omni/sistema), nº de mensagens.
  - Lista "atividade da sessão" (quantas perguntas, voz usada, análises).
  - Botões: **Exportar conversa** (.md), **Limpar**, "trocar modelo".
- Responsivo: em ilha estreita a ficha colapsa num painel deslizante.

### A3 · Enviar com Enter
- `Enter` envia; `Shift+Enter` quebra linha (hoje exige Ctrl+Enter).
- Textarea cresce até 4 linhas sozinho; placeholder atualizado.

### A4 · A IA cria arquivos → baixar no PC
- Protocolo na persona do Jorge: quando gerar arquivo, responde com bloco
  ```` ```arquivo:nome.ext ````.
- O chat detecta o bloco e renderiza um **cartão de anexo** (nome, extensão,
  tamanho) com botão **Baixar**.
- Slot novo na ponte: `salvar_arquivo(nome, conteudo)` → grava em
  `~/Downloads/Pestinha/` (cria a pasta) e emite confirmação com o caminho.
- Permissão nova `ia_arquivos` (interruptor nos Controles) — desligada, o
  botão some. Sem dependência nova: `QFileDialog`/`os` já existem; o pull do
  modelo usa o HTTP que o `ollama_local` já tem.

### A5 · Arrumar o "Falar"
- Reproduzir o fluxo atual (botão Falar → `ouvir()` → Parakeet →
  `transcrito` → caixa → resposta falada) e corrigir o que estiver quebrado.
- Estados claros: `Falar` → `Ouvindo…` (botão acende, vibra mostra o micro)
  → transcreve → envia; segundo clique cancela.
- Se o Parakeet faltar: o banner de download já existe — garantir que o
  progresso aparece e o botão volta quando pronto.
- Resposta falada: `veioDeVoz` já existe — garantir que pergunta por voz
  sempre recebe resposta por voz.

---

## Frente B — Aba Diagramas (criar solto + puxar fio, estilo n8n)

**Hoje**: fluxo vertical linear; nó novo só nasce pelo "+" no cabo, já
encaixado na sequência. O modelo é `{id, tipo, campos, ramas?}` — posições
são calculadas, não guardadas.

**Pedido**: mesma execução, mas criação livre — faço a caixa onde quiser e
depois puxo o fio para conectar (como o print do "Follow-up Automático").

### B1 · Nós soltos (caixas livres)
- Paleta lateral com os tipos (como a coluna esquerda do print): arrasta um
  tipo para o canvas → nasce um **nó solto** na posição solta (`x,y`
  próprios, cinza-tracejado = "ainda não conectado").
- Duplo clique no vazio também cria solto (menu rápido de tipos ali mesmo).
- Nó solto: arrasta livre, apaga com Delete/menu; **não executa** até ser
  conectado — badge "solto" explica.

### B2 · Puxar o fio (conectar por arrasto)
- Cada nó ganha **porta de saída** (bolinha na borda inferior/lateral).
- Arrastar da porta → fio curvo bezier segue o cursor (estilo n8n).
- Soltar **num nó solto** → ele entra na sequência logo após a origem (ou no
  ramo Sim/Não, se a origem for um "Si…" — a porta certa decide o ramo).
- Soltar **no vazio** → menu rápido: cria o nó ali e já conecta.
- Soltar **num cabo** entre dois nós → insere o solto naquele ponto.
- Fios existentes continuam clicáveis ("+" nos cabos segue funcionando como
  atalho).

### B3 · Modelo de dados + persistência
- `flujo` continua sequência de `{id, tipo, campos, ramas}` — a semântica de
  execução não muda.
- Novo campo `soltos: [{id, tipo, campos, x, y}]` no JSON salvo
  (`web_diagrama.json`) — nós não conectados persistem onde você os deixou.
- Migração: JSON antigo sem `soltos` abre normal (lista vazia).

### B4 · Acabamento
- Nó solto encaixa no auto-layout ao conectar (a mágica de hoje continua:
  tudo se realinha).
- "Si…" solto: ao conectar, as duas portas (Sim/Não) já aparecem.
- `es-pista` (barra de dicas) atualizada: "arraste um tipo para criar ·
  puxe da bolinha para ligar".

---

## Ordem sugerida e riscos

1. **A3 Enter** + **A1 lfm3 fixo** — rápidos, destravam o uso diário.
2. **A5 voz** — diagnosticar primeiro, corrigir depois (risco: depende do
   Parakeet baixado; é runtime, não compile-time).
3. **A2 remodelação** — a mais visual; mexe `.chat` no CSS + estrutura das
   bolhas; risco baixo (só a vista chat).
4. **A4 arquivos** — protocolo + cartão + slot; risco baixo, opt-in.
5. **B1–B4 diagrama** — a mais delicada: toca `eslabon.js` (1298 linhas, a
   peça mais complexa do projeto). Mitigação: tudo novo (paleta, soltos,
   fio fantasma) vive em funções novas; a máquina de execução e o layout
   sequencial **não são reescritos**.

## Pontos a confirmar

Decididos na revisão:

- **Modelo fixo**: `lfm3-omni` (texto + voz no mesmo modelo).
- **Ficha lateral**: do Jorge/modelo — status, modelo, voz, contexto usado,
  exportar, limpar.
- **Arquivos da IA**: **pasta fixa + diálogo** — Baixar salva direto em
  `~/Downloads/Pestinha/`; "Salvar como…" abre diálogo para desviar.
- **Diagrama (Frente B)**: **executar com semântica linear** — nó solto
  entra na sequência ao conectar (opção (a)). A variante "grafo livre" fica
  registrada em `docs/POSSIVEIS_ATUALIZACOES.md` (item F1).
- **Liberação**: usuário liberou a execução completa (A + B-linear).

---

## Status: implementado (2026-11-17)

- **A1** `lfm3-omni` fixa: `config.ollama_chat_modelo`, seletor travado
  (só indica), chip "Baixar lfm3-omni" com progresso via `/api/pull`
  (`OllamaLocal.pull_async` → `ponte.modelo_pull`).
- **A2** Chat em 2 colunas: conversa com avatar/meta/markdown + ficha do
  Jorge (status, modelo, voz, contexto %, atividade, exportar/limpar).
- **A3** Enter envia, Shift+Enter quebra linha.
- **A4** Protocolo ` ```arquivo:nome.ext``` ` → cartão de anexo com
  "Baixar" (`~/Downloads/Pestinha/`, nome desduplicado) e "Salvar como…"
  (QFileDialog). Permissão `ia_arquivos` (padrão: ligada).
- **A5** "Falar": parar a gravação agora transcreve o capturado (antes
  descartava); transcrição durante resposta fica na caixa e é enviada ao
  final; estados visuais de gravando/transcrevendo.
- **B1–B4** Eslabon: paleta lateral, caixas soltas `(x,y)` com selo
  "solto", portas de saída (2 no Si…), fio bezier animado, soltar no
  vazio/passo/cabo abre o menu de tipos já ligado à origem, arrastar
  solta com imã no fluxo, `soltos` persistidos em `web_diagrama.json`.
  Semântica de execução linear preservada.
- Teste: `tests/test_narrador.py` — insight agora sai com `origem: jorge`.
