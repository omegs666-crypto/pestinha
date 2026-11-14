# Plano de UI/UX — "bem interativo" no estilo Coucou

**Escopo:** todo o sistema visual/interativo do Pestinha — pet, ilha, painéis flutuantes, menus e feedback.
**Referência:** `coucou-main/windows/src/` — `island/fsm.ts`, `island/shortcuts.ts`, `island/agents.ts`, `mochi/engine.ts`, `pill/main.ts`, `views/`.
**Data:** 2026-11-08

---

## 1. O que o Coucou faz de UI/UX (o que vamos copiar)

| Recurso Coucou | Como funciona |
|---|---|
| **FSM de 4 estados** | `hidden → petit → home → coucou`. Cada transição tem delay próprio e configurável |
| **Peek progressivo** | mouse perto abre um pouco; mouse em cima abre tudo; mouse sai fecha em ~0,6–15 s |
| **Barra de contagem** | a ilha desenha uma barrinha mostrando quanto tempo falta pra recolher |
| **Pin de alerta** | notificação importante fica aberta mesmo com o mouse fora |
| **Saudação animada** | estado `coucou`: animação de boas-vindas ao abrir |
| **Atalhos de teclado globais** | teclas rápidas abrem a ilha, trocam de pill, mandam o mascote passear |
| **Pills vivas** | cada pill mostra status em tempo real (ex.: "3 mensagens não lidas") |
| **Mochi arrastável** | o pet em si pode ser arrastado pelo desktop com física |
| **Feedback tátil/visual** | hover states, micro-animações, transições suaves em tudo |

## 2. O que o Pestinha já tem

- Pet clicável, arrastável, com carício, cutucada, bilhetes, cantinho, protesto
- Menu de contexto (botão direito) com várias ações
- Ilha interativa (acabamos de melhorar: arraste, pin, pills com estado, animação)
- Painéis flutuantes arrastáveis com posição salva
- Emoções visuais no rosto, boca animada durante fala

## 3. O que falta (o plano)

### Fase A — Ilha ainda mais viva (complementa o que já fizemos)

| # | Melhoria | Detalhe |
|---|---|---|
| A1 | **Barra de contagem de recolhimento** | Quando a ilha aberta vai recolher sozinha, desenhar uma barrinha fina embaixo mostrando o tempo restante (como o Coucou) |
| A2 | **Delays configuráveis** | Configurações: "tempo pra espreitar", "tempo pra recolher" (como `homeToPetitDelay`/`petitToHiddenDelay` do Coucou) |
| A3 | **Abertura por hover (opcional)** | Configuração "abrir no hover": passar o mouse já abre a visão geral direto, sem clique |
| A4 | **Saudação ao abrir** | Quando a ilha abre, o rostinho faz uma animação rápida (piscada/excitação) por ~600 ms |
| A5 | **Pills com status ao vivo** | Ex.: pill "Protesto" mostra o estágio atual; "Cantinho" mostra "ligado/desligado"; "Voz" já mostra; adicionar emoji de estado |

### Fase B — Pet mais interativo (o "Mochi" do Pestinha)

| # | Melhoria | Detalhe |
|---|---|---|
| B1 | **Arrastar com física** | Arrastar o pet e soltar → ele "pousa" com quique/squash (já existe física? verificar `core/physics.py`) |
| B2 | **Reações ao hover** | Mouse parado em cima do pet por 2 s → ele olha pra você / fica curioso |
| B3 | **Duplo clique** | Ação especial (ex.: fazer carinho ou mandar uma travessura) |
| B4 | **Arrastar e soltar em janela** | Soltar o pet em cima de um app → ele "pousa" naquele app (já existe `pousar_janelas`? verificar) |
| B5 | **Bilhete flutuante** | Pet deixa um recadinho flutuando perto dele por alguns segundos (usa `recs`/`cartazes` existentes) |

### Fase C — Painéis flutuantes mais ricos

| # | Melhoria | Detalhe |
|---|---|---|
| C1 | **Header com título + fechar** | Painéis hoje são `FloatingWidget` sem chrome; adicionar barra fina com título e botão ✕ |
| C2 | **Animação de abrir/fechar** | Fade + slide suave ao invés de aparecer do nada |
| C3 | **Três pontos / menu** | Botão "⋯" em cada painel com ações (fixar, sempre visível, etc.) |
| C4 | **Pills das integrações com dados** | Monitor neural mostra emoção atual; Laboratório MLP mostra último erro; etc. |

### Fase D — Feedback e micro-interações

| # | Melhoria | Detalhe |
|---|---|---|
| D1 | **Som de hover/clique** | Somzinho sutil ao clicar na ilha (opcional, desligável) — usar `winsound` ou arquivo `.wav` local |
| D2 | **Partículas de carinho** | Quando você acaricia o pet, coraçõezinhos/partículas sobem (Qt `QPainter` simples) |
| D3 | **Transição de emoção** | Quando a emoção muda, o rosto faz uma transição suave (lerp) em vez de trocar seco |
| D4 | **Brilho no hover dos botões** | Todos os `QPushButton` custom já têm hover; padronizar em todos os painéis |

### Fase E — Atalhos de teclado (opcional, último)

| # | Melhoria | Detalhe |
|---|---|---|
| E1 | **Atalho global pra ilha** | Ex.: `Ctrl+Alt+P` abre/fecha a ilha (precisa de hook global — `pynput` ou similar; verificar se já tem) |
| E2 | **Atalhos dentro da ilha** | `1-6` clicam nas pills, `Esc` fecha |

---

## 4. O que **não** muda

- **Privacidade:** nenhuma melhoria envia dados pra fora; sons são arquivos locais, atalhos só leem input local.
- **Design system:** mesmas cores, fontes e estilo dos painéis atuais.
- **Permissões:** tudo novo fica atrás de `perms` (opt-in) ou é só visual.
- **Git:** nenhuma alteração.

## 5. Priorização sugerida

| Prioridade | Itens | Por quê |
|---|---|---|
| **Alta** | A1, A4, B2, B5, C1, C2 | Impacto visual imediato, baixo risco |
| **Média** | A2, A3, A5, B1, B3, C3, D3 | Melhoram muito a sensação de "vivo" |
| **Baixa** | B4, C4, D1, D2, E1, E2 | Nice-to-have ou dependem de libs novas |

## 6. Estimativa de esforço

| Fase | Complexidade | Depende de |
|---|---|---|
| A | Baixa | nada novo |
| B | Média | verificar física e `pousar_janelas` |
| C | Baixa-Média | `FloatingWidget`/`arrastavel.py` |
| D | Média | assets de som/partículas |
| E | Alta | lib de hotkey global |

## 7. Como decidir

Marque o que entra na próxima rodada:

- [ ] **Fase A** — ilha mais viva (barra, delays, saudação, pills com dados)
- [ ] **Fase B** — pet mais interativo (física, hover, duplo clique, bilhetes)
- [ ] **Fase C** — painéis com header e animações
- [ ] **Fase D** — sons, partículas, transições de emoção
- [ ] **Fase E** — atalhos de teclado

> Sugestão: **A + B + C** já deixam o Pestinha com a mesma "sensação" do Coucou. D e E são incrementais.
