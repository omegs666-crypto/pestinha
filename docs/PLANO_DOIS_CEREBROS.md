# Plano — Dois Cérebros: Bryan (emoção) + Jorge (mente/LLM)

## Interpretação do pedido

Hoje o projeto tem **um** personagem que faz tudo: o mesmo pet tem corpo,
emoções, memória e responde no chat. A proposta é dividir em **dois cérebros
com papéis distintos**:

- **Bryan = o cérebro emocional (amigável)** — continua como está: corpo na
  tela, braços, drives, memória episódica, grafo do cérebro, travessuras.
  Ele *sente*. Não "sabe" — ele reage.
- **Jorge = o cérebro racional (a mente)** — vira a **cara de tudo que vem da
  LLM local**: chat, insights do narrador, falas de IA, "perguntar ao cérebro".
  Ele *sabe* — é o pet que raciocina, explica e conversa com você.

Metáfora do produto: **o coração e a mente**. Bryan sente; Jorge explica.
Quando os dois interagem (Jorge comenta o estado do Bryan, Bryan reage às
respostas do Jorge), o projeto ganha uma dinâmica que nenhum desktop pet tem.

## O que já existe que serve de base

- `pets/jorge.json` + `pets/jorge/persona.txt` — temperamento, aparência
  (dourado + gravata) e persona "coach trambiqueiro confiante" já definidos.
- `prompt_fala(nome, persona, ...)` já recebe persona por parâmetro — trocar
  o autor da fala é barato.
- A ilha já tem `origem` nas falas ("pet", "ollama", "sistema") — "jorge" é
  mais uma origem.
- O grafo do cérebro já suporta tipos novos de nó — "mente" é mais um hub.
- `Voz` e `ChatVoice` — a voz da resposta pode ter pitch/rate próprios.

## Fases

### Fase 1 — Jorge como a cara da LLM *(barato, começa aqui)*

1. **Config**: `perms["pet_corpo"]` (bryan, hoje `pet`) + `perms["pet_mente"]`
   (jorge). Toggle "Jorge responde no chat" (perm `mente_llm`, padrão ligado).
2. **Chat**: mensagens da IA passam a vir "do Jorge" — nome e avatar dele
   (mini-canvas com a aparência dourada + gravata, reusando `desenho_rosto`).
   O system prompt vira: *"Você é Jorge, a mente do Pestinha — coach confiante,
   jargão de startup, mas responde de verdade."*
3. **Insights do narrador**: falas geradas pelo Ollama ganham origem "jorge" —
   "Jorge comentou: …".
4. **Voz**: a resposta da IA sai com voz própria (pitch/rate diferentes do
   Bryan — a `Voz` já parametriza por conteúdo).
5. **Ajuste fino da persona**: o `persona.txt` do Jorge é sátira pura
   ("nunca dá conselho de verdade"). Para o papel de mente, convém uma versão
   "confiante e engraçada, mas útil" — `persona_mente.txt` separada para não
   perder a piada original no modo pet.

### Fase 2 — Presença visual do Jorge na ilha

6. **Mini-mascote do Jorge** no canto do chat/ilha: aparece quando a LLM está
   processando (halo "pensando"), some ao terminar. Sem cérebro LIF — só a
   aparência e o estado pensando/falando.
7. *(Opcional, depois)* **Jorge visita o desktop**: segunda janela pet
   "fantasma" que surge para falar a resposta e some — sem drives, sem memória,
   só a casca e a boca mexendo.

### Fase 3 — O grafo com dois cérebros

8. A aba Cérebro ganha **segundo hub**: `mente:Jorge` — nós dele são temas do
   chat, insights gerados, modelo ativo, contagens de resposta. Arestas ligam
   às coisas do Bryan que ele comentou ("Jorge falou sobre Bryan estar triste").
   Visão: duas teias com uma ponte "eles conversam".

### Fase 4 — Diálogo entre eles (a mágica)

9. **Jorge comenta o Bryan**: quando o narrador observa o estado, a fala vem
   do Jorge reagindo *ao Bryan* ("o Bryan tá tenso hoje, quer que eu analise?").
10. **Bryan reage ao Jorge**: resposta do Jorge no chat → Bryan faz um emote
    (acena, revira os olhos, aplaude).
11. **Eles conversam**: evento raro de 2-3 falas alternadas no balão —
    origem alternando "bryan"/"jorge".

## Decisões de design

- **Memória separada**: Jorge tem `convivencia`/`pontos` próprios? Sugestão:
  *não* — Jorge acessa o cérebro do Bryan (é a mente *dele*, afinal). Ele lê
  a memória compartilhada, mas não sente.
- **O Jorge não tem corpo emocional**: sem drives, sem episódios, sem castigo.
  Ele é um sistema de fala com persona — deliberadamente "cérebro sem corpo".
- **Multi-pet simultâneo**: fora do escopo das fases 1-3 (a Fase 2 item 7
  abre a porta, mas como janela simples, não como segundo pet completo).

## Arquivos tocados (previsão)

- `pestinha/config.py` — `pet_mente`, `mente_llm`.
- `pestinha/ui/web_bridge.py` — `origem="jorge"`, mini-mascote, grafo com 2 hubs.
- `pestinha/ui/web/ilha.js|css|index.html` — avatar no chat, toggle, hub mente.
- `pestinha/mind/convivencia.py` — `prompt_fala` com nome/persona da mente.
- `pestinha/mind/narrador.py` — falas de insight atribuídas ao Jorge.
- `pets/jorge/persona_mente.txt` — a versão "útil" da persona.
- `pestinha/app.py` — carrega o segundo pet_def (aparência + persona da mente).

## Riscos / perguntas abertas

- A persona sátira do Jorge **pode atrapalhar respostas sérias** — por isso a
  versão `persona_mente.txt`. Ou você prefere manter 100% a piada?
- Duas vozes: o `voz.py` precisa conferir se aceita pitch por persona (senão
  entra um `voz_jorge` simples).
- Custo: falas do Jorge no narrador usam Ollama — respeitar `INTERVALO_FALA_IA`
  para não poluir.
