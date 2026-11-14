# 2026-11-14 — Núcleo: identidade visual própria, orbe vivo e narrador

## Direção de arte

A ilha deixou de imitar o Coucou. A nova identidade se chama **Núcleo**:

- **Vidro grafite espacial**, com fundo translúcido e brilhos internos nas cores do humor.
- **Borda de luz que respira**: um gradiente cônico que gira devagar no estado calmo, acelera
  ao pensar ou processar e pisca em âmbar/vermelho no alerta.
- **Acentos que mudam com o humor**: ciano/violeta (calmo), verde/azul (processando),
  violeta/rosa (pensando), âmbar/vermelho (alerta), grafite (pausado). Com o som ligado, a cor
  segue o timbre do que toca: graves puxam para violeta e âmbar, agudos para ciano.
- **Layout de celular**: ao abrir, um trilho de cards em estilo widget, que pode ser arrastado
  com inércia, com dock de ícones que crescem como lupa.

A referência (imagem e vídeo de uma ilha em vidro) e o Moxen *Grabadora* serviram só como
inspiração. Nenhum código, layout ou mascote foi copiado.

## Orbe neural (`#orbe`, canvas)

Bolha que muda de forma, com partículas em órbita, halo e ondas de energia:

| Humor | Comportamento |
|---|---|
| calmo | respiração lenta, poucas partículas |
| processando | gira rápido e emite ondas (atividade neural alta ou treino do MLP) |
| pensando | anel tracejado girando (chat ou narrador esperando o Ollama) |
| alerta | pulsos rápidos âmbar/vermelho (erro ou fala de alerta) |
| som | deforma com o espectro e solta ondas nos picos |
| pausado | quase parado, em grafite |

O orbe se inclina na direção do cursor. Um clique solta uma onda e abre ou recolhe a interface.

## Movimento

- O corpo abre, recolhe e alarga com uma **mola física** (rigidez e amortecimento), não com
  curvas fixas. Abrir balança um pouco; fechar é mais firme.
- A janela passou a ter **tamanho fixo e transparente**: a página informa o retângulo
  visível, e `setMask` deixa o clique passar no resto. Assim nada é redimensionado a cada
  quadro. Testado: fora da máscara, o clique vai para a janela de baixo.
- Os cards inclinam em 3D e têm um brilho que segue o cursor. As vistas entram com mola.

## Narrador

- `pestinha/mind/narrador.py`: regras locais instantâneas (pausa, energia baixa,
  insatisfação subindo, início e fim de processamento, troca de emoção), com intervalo mínimo
  de 12 s e sem repetir a mesma regra antes de 90 s.
- **Insight do Ollama** a cada 2 min com a ilha visível, ou pelo botão "Me conta agora". Usa um
  cliente Ollama separado do chat, em worker. Os números viram fatos em texto (por exemplo
  "Energia: 22% (baixo)"), porque modelos pequenos erram com JSON cru.
- **Escolha do modelo**: nunca um modelo de nuvem (`:cloud`). Prefere os leves (`3b`, `mini`...)
  e evita os de raciocínio longo (`deepseek-r1`). Testado com o Ollama real: escolheu `qwen2.5:3b`.
- As falas aparecem num **balão que alarga a pílula** e ficam registradas no card Narrador.

## Cards do início

Pet (emoção, anel de energia, métricas, pausar e voz), Som do sistema (sol que respira, onda
fluindo, medidor de LEDs, play), Foco (timer de 5 a 90 min com aviso ao terminar), Tempo real
(energia, estímulo e atividade, 60 s) e Narrador (últimas falas).

## Outras vistas (dock)

- **Estúdio de som**: espectro radial espelhado em volta de um núcleo, fita de onda, campo de
  pontos que foge do mouse e marcas (clique ou tecla M) que correm junto com a fita.
- Controles (Centro), Grade (Parrilla, agora no tema escuro), Diagramas (Eslabón, tema
  escuro), Chat local, Monitor neural e Laboratório MLP.

## Privacidade

- O chat marca modelos `:cloud` como "(nuvem)" e mostra um aviso quando um deles é escolhido:
  as mensagens saem do PC. O seletor começa num modelo local.

## Correções encontradas pelos testes

- `limpar_frase` tirava as aspas antes de remover o bloco `<think>` e deixava uma aspa sobrando.
- Canvas só acompanhava a largura do elemento: os orbes viravam elipses. Agora acompanha os dois eixos.
- As ondas do orbe saíam do canvas e desenhavam um quadrado; agora somem antes da borda.

## Testes

- `tests/test_narrador.py` (novo, 8 testes): regras e intervalos, modelo nunca de nuvem, limpeza
  da frase, prompt com fatos, insight sem usar o chat, modo avião, falha avisada uma vez e
  limites da região de clique.
- Narrador verificado com o Ollama real desta máquina.

## Limitações

- Não há desfoque real do desktop atrás do vidro (o Windows não aplica DWM blur em janelas
  WebEngine com transparência por pixel); o vidro é translúcido e escuro.
- O card Foco é só um timer: não pausa o pet nem bloqueia notificações.
