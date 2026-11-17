# 2026-11-16 — Dois Cérebros, Fase 1: Jorge é a cara da LLM

## O que foi feito

Primeira fase do plano `docs/PLANO_DOIS_CEREBROS.md`: **Jorge vira a mente do
Pestinha** — quem fala por tudo que vem da LLM, enquanto o Bryan segue sendo o
cérebro emocional (corpo, drives, memória).

## Decisão do usuário

Opção B: persona **"confiante e engraçada, mas responde de verdade"** —
`pets/jorge/persona_mente.txt` é a versão útil (a `persona.txt` sátira original
fica intacta para o modo pet, se um dia o Jorge virar personagem de corpo).

## Mudanças

- **`app.py`**: `_carregar_mente()` — lê `pets/jorge.json` (nome + aparência) e
  `persona_mente.txt` (fallback `persona.txt`); nunca quebra o app.
- **`config.py`**: `pet_mente: "jorge"` e `mente_llm: True` (toggle).
- **`web_bridge.py`**:
  - `enviar_chat` injeta o system do Jorge no servidor (`Você é Jorge, a mente
    do Pestinha…` + persona) — o JS não duplica nem conhece a persona.
  - Insights do narrador ganham `origem: "jorge"` (balão mostra "JORGE").
  - Slot `mente_dados()` (nome + aparência) e chaves `mente`/`mente_llm` no snapshot.
  - `acao("mente")` no interruptor dos Controles.
- **`index.html`**: chave "Jorge responde pela IA" nos Interruptores; badge
  `#jorgito-wrap` no topo do chat.
- **`ilha.css`**: `.jorgito-wrap`, `.pensando` (pulso dourado) e
  `.bolha.assistente[data-autor]` (tag JORGE na resposta).
- **`ilha.js`**: módulo `jorgito` — mini-mascote 34 px com a aparência do Jorge
  (casca dourada, tela escura, olhos dourados piscando, gravata vermelha);
  pulsa quando a LLM está respondendo/processando; tag do autor nas respostas;
  origem "JORGE" no balão.
- **`tests/test_web_island.py`**: 2 testes novos (system do Jorge injetado;
  toggle desligado = chat cru).

## Fases seguintes (backlog)

2. Presença: Jorge "visitando" o desktop como janela fantasma.
3. Grafo com dois hubs (teia do Jorge ligada à do Bryan).
4. Diálogo entre eles (Jorge comenta o Bryan, Bryan reage ao Jorge).

## Testes

- `test_web_island.py`: 29 passam (incluindo os 2 novos da mente).
- Captura validada: badge dourado do Jorge no topo do chat + tag JORGE na bolha.
