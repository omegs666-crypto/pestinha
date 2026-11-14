# Plano de melhoria — Ilha interativa (estilo Coucou)

**Arquivo alvo:** `pestinha/ui/ilha.py`
**Referência:** `coucou-main/windows/src/island/` (fsm.ts, agents.ts, views.ts)
**Data:** 2026-11-08

---

## 1. O que a ilha é hoje

A ilha tem **2 painéis** na mesma janela:

| Painel | O que mostra | Como abre |
|---|---|---|
| **Comprimido** | Rostinho do pet + nome da emoção | sempre visível no topo-centro |
| **Visão geral** | Resumo do estado + 6 pills clicáveis | clique no comprimido |

Pills atuais: Monitor neural, Painel de protesto, Laboratório MLP, Cantinho do castigo, Travessura agora, Voz ligar/desligar.

Ela some junto com o pet (`sessao.py`), não rouba foco, e recolhe ~0,9 s depois que o mouse sai.

---

## 2. Problemas encontrados na revisão do código

### Bugs / comportamento quebrado

**B1 — O "espreitar" pisca.**
`enterEvent`/`leaveEvent` estão no widget raiz, mas o mouse passa sobre os filhos (rostinho, label, botões). O Qt entrega enter/leave de forma inconsistente → a ilha cresce e encolhe rapidinho.
*Correção:* `setMouseTracking(True)` + `eventFilter` nos filhos, ou mover a lógica para o evento do filho.

**B2 — Timer trabalha à toa.**
`_timer_atualiza` roda a cada 500 ms **mesmo com a ilha escondida** e mesmo com o pet pausado/inativo. Gasta CPU e atualiza widgets invisíveis — exatamente o tipo de bug de "estado inativo" que o `docs/CONTEXTO_REGRESSAO.md` manda evitar.
*Correção:* pausar o timer em `hideEvent`, religar em `showEvent`; e respeitar o estado da sessão.

**B3 — Acessos que podem quebrar o app.**
`self.app.perms["voz"]`, `app.drives.energy`, `app.protest.stage`, `app.cerebro2.ligado()` são acessados direto. Se uma permissão ou atributo faltar → `KeyError`/`AttributeError` e o app inteiro cai dentro do timer.
*Correção:* `.get()` e `getattr` com valor padrão.

**B4 — Tamanho fixo vaza em telas pequenas.**
`GRANDE = (430, 250)` fixo. Em monitor pequeno, escala 125/150% ou segunda tela estreita, a visão geral sai da tela.
*Correção:* calcular a partir da área disponível em `app.bounds()`.

### Falta de funcionalidade (o que o Coucou tem e a ilha não)

**F1 — Não dá pra mover a ilha.**
Hoje clicar sempre abre/fecha. O Coucou deixa o painel ser arrastado. Os outros painéis do Pestinha (`monitor.py`, `panel.py`, `lab_mlp.py`) já usam `world/arrastavel.py` com arraste + posição salva em `memory/panels.json`. A ilha é a única sem isso.

**F2 — Posição não persiste.**
Toda vez que abre, volta pro topo-centro. Se o usuário gostou dela ao lado do relógio, perde.

**F3 — Sem "fixar" (pin).**
No Coucou existe estado `pinned`: o painel fica aberto mesmo com o mouse fora. Aqui é impossível manter a visão geral aberta.

**F4 — Pills não mostram estado.**
O usuário não sabe se o "Monitor neural" já está aberto ou não. No Coucou cada pill reflete o estado da integração.

**F5 — Sem animação.**
Expandir/recolher é um `resize()` seco — salta de 150px pra 430px de uma vez. O Coucou anima.

**F6 — Pills não fecham a ilha.**
Clicar numa pill abre o painel flutuante, mas a ilha continua aberta cobrindo a tela.

---

## 3. Plano de melhoria proposto

### Fase 1 — Correções (não muda nada visual)

| # | Mudança | Arquivo |
|---|---|---|
| 1.1 | Timer só roda com a ilha visível | `ilha.py` |
| 1.2 | `.get()`/`getattr` em todos os acessos do resumo | `ilha.py` |
| 1.3 | Hover estável via `setMouseTracking` + `eventFilter` | `ilha.py` |
| 1.4 | `GRANDE` calculado pela tela disponível | `ilha.py` |

### Fase 2 — Interação completa (o essencial do Coucou)

| # | Mudança | Detalhe |
|---|---|---|
| 2.1 | **Arrastar a ilha** | Pressionar + mover > 4 px = arraste (não clique); soltar salva posição em `memory/panels.json` (chave `"ilha"`) usando `load_positions`/`save_position`/`posicao_acessivel` de `world/arrastavel.py` |
| 2.2 | **Botão fixar (pin)** | 📌 na visão geral; fixada não recolhe no `leaveEvent` |
| 2.3 | **Pills com estado** | Mostram `●` se o painel correspondente está aberto (`app.floats`); pill de voz mostra ligada/desligada |
| 2.4 | **Pill fecha a ilha** | Após abrir um painel pela pill, a ilha recolhe sozinha |

### Fase 3 — Acabamento visual

| # | Mudança |
|---|---|
| 3.1 | Animação suave de expandir/recolher (`QPropertyAnimation`), sem travar a UI |
| 3.2 | Transição do "espreitar" também animada |

### Fase 4 — Testes e documentação

| # | Mudança |
|---|---|
| 4.1 | `tests/test_ilha.py`: abrir/recolher/toggle, pin, arraste com limiar, posição salva e restaurada, timer pausado quando oculta |
| 4.2 | Rodar pyflakes + pytest |
| 4.3 | Changelog em `CHANGELOG_NOTAS/` |

---

## 4. O que **não** muda

- Design system: mesmas cores (`BG`, `BORDA`, `VERDE`, `TEXTO`, `FRACO`), fontes e estilo dos painéis existentes.
- Privacidade: a ilha só lê o que o pet já lê (`pet_state`, `perms`, `floats`) — nenhum dado novo, nenhuma rede.
- Permissões: continua opt-in (`perms["ilha"]`), some junto com o pet.
- Git: nenhuma alteração.

---

## 5. Riscos

| Risco | Como resolver |
|---|---|
| Arraste confundido com clique | Limiar de 4 px de movimento antes de contar como arraste |
| Posição salva fora da tela | Usar `posicao_acessivel()` na restauração |
| Animação + peek brigando pelo tamanho | Um único método `_set_tamanho(alvo)` centraliza tudo |
| Timer de atualização + animação | Timer existente (500 ms) já é suficiente; animação é por evento |

---

## 6. Como decidir

Marque abaixo o que entra na próxima implementação:

- [ ] **Fase 1** — só correções (recomendado sempre)
- [ ] **Fase 2** — arraste + pin + pills com estado (o "Coucou completo")
- [ ] **Fase 3** — animações
- [ ] **Fase 4** — testes + changelog (recomendado sempre)

> Sugestão: **Fases 1 + 2 + 4** já deixam a ilha no nível do Coucou sem risco visual. A Fase 3 é cosmética e pode ficar pra depois.
