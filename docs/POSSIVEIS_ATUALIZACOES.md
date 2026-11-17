# Possíveis atualizações e recomendações

Backlog de ideias para o Pestinha. Quando não houver tarefa ativa, pegar daqui —
ordem sugerida na seção "Ordem recomendada". Cada item tem: impacto, esforço e o
que precisa já existir. Riscar/mover para "Feito" conforme for saindo.

---

## A. Aba Cérebro (grafo da memória)

| # | Ideia | Impacto | Esforço | Notas |
|---|-------|---------|---------|-------|
| A1 | **Linha do tempo**: scrubber embaixo mostrando o cérebro como era em outro dia/hora (episódios e pontos têm timestamps) | Alto | Médio | Precisa guardar histórico dos pontos (hoje só o score atual) |
| A2 | **Modo foco com camadas**: clique foca vizinhos de 1º grau; scroll no foco expande para 2º grau | Médio | Baixo | O foco de 1º grau já existe |
| A3 | **Prender nós**: segurar nó 1 s fixa ele ali; layout persistido via `ponte.salvar/carregar` | Médio | Baixo | Infra de persistência da ponte já existe |
| A4 | **Mini-grafo no card da Home**: versão de ~8 nós no card do pet — o cérebro pulsando em miniatura | Alto | Médio | Reusa o mesmo JSON do `grafo()` |
| A5 | **Pulso de atividade neural**: quando `brain.step` dispara pools (CHEER, ALERT…), o nó relacionado pisca | Alto | Médio | Ligar `motor_activity()`/`pool_rates()` a um sinal da ponte |
| A6 | **Sonambulismo do grafo**: durante o sono, conceitos-sonho vagam lentamente e trocam "pensamentos" (arestas fantasmas piscando) | Médio | Baixo | O modo sonho já existe; é só animação |
| A7 | **Palavras do chat**: termos frequentes das conversas viram nós de conceito — o cérebro ganha vocabulário | Médio | Médio | Contar termos do histórico de mensagens |
| A8 | **Região sombria**: `castigo`/`protest` viram um canto escuro do cérebro — rancor como nó vermelho pulsando | Médio | Baixo | Dados já existem em `app.castigo`/`app.protest` |
| A9 | **Som ambiente**: zumbido suave por nó ativo, pitch pela valência (toggle) | Baixo | Médio | Reusa envelope/áudio existente |
| A10 | **Grafo 3D**: WebGL, o cérebro como constelação navegável | Alto wow | Alto | Deixar por último; o 2D já conta a história |

## B. Memória e inteligência

| # | Ideia | Impacto | Esforço | Notas |
|---|-------|---------|---------|-------|
| B1 | **Perguntar ao cérebro**: campo na aba — "por que você fez isso?" → a LLM local responde usando o grafo como contexto (RAG caseiro) | Muito alto | Médio | Já existe cliente Ollama; o grafo vira prompt |
| B2 | **Episódios de verdade**: o `episodes.jsonl` não existe ainda — ligar `mischief_ctl` às interações para a memória episódica começar a se encher | Alto | Médio | Sem isso, ações/contextos ficam ralos no grafo |
| B3 | **Exportar para o Obsidian**: o grafo vira `[[wikilinks]]` no Segundo Cérebro — `memoria/2026-11-16-bilhete.md` com `[[feliz]]`, `[[work]]` | Alto | Médio | `segundo_cerebro.py` já escreve MD; falta a camada de links |
| B4 | **Nota-índice** (`00-Bryan.md`) regenerada como hub do vault | Médio | Baixo | Depende de B3 |
| B5 | **Importar do vault**: notas do usuário com `#bryan` que ele "lê" e vira memória (opt-in) | Médio | Médio | Cuidado com privacidade: ler só a pasta Pestinha |
| B6 | **Esquecimento real**: memórias nunca reacessadas migram para arquivo frio antes de sair | Médio | Médio | Hoje o poda é só por quantidade |
| B7 | **Dois cérebros**: com dois pets, os dois grafos lado a lado — compara o que cada um aprendeu | Alto | Alto | Precisa do sistema multi-pet funcionando de ponta a ponta |

## C. Persona, braços e expressão

| # | Ideia | Impacto | Esforço | Notas |
|---|-------|---------|---------|-------|
| C1 | **Envelope de áudio nos braços**: os picos de gesto seguem o volume real da fala, não impulsos aleatórios | Alto | Médio | O `vibra` já tem envelope da resposta |
| C2 | **Braços reagem ao cursor**: mãozinha aponta/segue o mouse quando ele passa perto | Alto | Baixo | O gesto "curioso" já levanta um braço |
| C3 | **Gestos compostos**: sequências — coçar a cabeça, bocejar, aplaudir — como reações raras e longas | Médio | Médio | A camada de reação transitória já existe |
| C4 | **Jorge com braços**: dar os braços ao outro persona, com física própria (mais calmo? mais elástico?) | Médio | Baixo | É só `"aparencia": {"bracos": true}` no JSON |
| C5 | **Aparência no grafo**: o nó pet no cérebro usa o rosto real do pet (mini-canvas) em vez de bolinha | Médio | Médio | Reusa `desenho_rosto` no canvas |

## D. Ilha e modo um-persona-só

| # | Ideia | Impacto | Esforço | Notas |
|---|-------|---------|---------|-------|
| D1 | **Cama na ilha**: quando ele volta cansado, o mascote dorme numa caminha visível na pílula | Médio | Baixo | Só desenho; o estado já existe |
| D2 | **Resistência à arrancada**: se ele está dormindo/descansando, o mascote resiste fisicamente ao arrasto (mola no cursor) antes de ceder | Alto | Baixo | Reforça a narrativa "ele não quer sair" |
| D3 | **Ele volta sozinho de saudade**: fora da ilha por muito tempo sem interação, ele sente saudade e volta por conta própria (sem estar cansado) | Alto | Baixo | Reusa o voo de retorno |
| D4 | **Passeio autônomo**: livre na tela, ele explora sozinho (ir para o canto, olhar janelas) em vez de ficar parado | Muito alto | Alto | Tem `behavior.mission` — expandir roteiro de exploração |
| D5 | **Animação de saída melhorada**: ao ser puxado, transição elástica com squash na borda da ilha | Médio | Baixo | Polimento do gesto já existente |

## E. Qualidade de vida do projeto

| # | Ideia | Impacto | Esforço | Notas |
|---|-------|---------|---------|-------|
| E1 | **Painel de debug dos drives**: gráfico temporal de energia/estímulo/carinho já existe — adicionar emoção como cor de fundo | Médio | Baixo | O `grafico` já desenha 3 séries |
| E2 | **Snapshot da memória**: botão "fotografar cérebro" que salva PNG do grafo em `memory/` | Baixo | Baixo | `canvas.toDataURL` + `ponte.salvar` |
| E3 | **Teste E2E do gesto de tirar da ilha**: automação PySide6 que arrasta o mascote e confere `_solo_livre` | Médio | Médio | O harness de captura já prova o caminho |
| E4 | **Limpeza de `.corrompido`**: rotina que arquiva/apaga os backups de JSON corrompido antigos | Baixo | Baixo | Vários arquivos `.corrompido` acumulados |
| E5 | **Fix `AttributeError 'bool' object has no attribute 'strip'`**: erro recorrente nos logs, origem não localizada | Médio | Baixo | Investigar próximo debug de log |

---

## Feito

- Grafo da memória estilo Obsidian (aba Cérebro): nós, arestas com valência, física.
- Filtros por tipo, modo foco, heat de recência.
- Nó "você" + contagens da convivência + pontos como lembranças.
- Sonhos: consolidação de episódios em conceitos durante o sono.
- Cutucar o cérebro (duplo clique → ele comenta o nó).
- Deriva constante + pulso da emoção atual.
- Cache-buster nos assets da ilha.

## Ordem recomendada

1. **B2** (episódios de verdade) — alimenta todo o resto.
2. **C1** (envelope de áudio nos braços) — barato, muito visível.
3. **D2/D3** (resistência + saudade) — aprofunda a narrativa do modo solo.
4. **B1** (perguntar ao cérebro) — o "uau" técnico: grafo + LLM local.
5. **A4** (mini-grafo na Home) — o cérebro visível o tempo todo.
6. **B3** (exportar pro Obsidian) — conecta com o mundo real.
