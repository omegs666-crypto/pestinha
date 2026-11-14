# 2026-11-14 — Convivência, reações configuráveis, áudio e leveza

## O que mudou

### Cérebro: o pet lembra e aprende com você
- **Memória por pet** (`memory/pets/<pet>/convivencia.json`): conta cutucadas, carinhos, travessuras
  dispensadas, arremessos, vezes que prendeu e fugas. Vira fato em texto para o Ollama.
- **Aprendizado de falas**: cada fala que aparece ganha ponto se você reagir em até 30 s (cutucar,
  carinho) e perde um pouco se for ignorada. A escolha da fala usa esse peso (`Voz.frase`).
- **Falas com IA local** (`pestinha/mind/convivencia.py`, `pedir_fala_ia` na ponte): a cada 75 s
  verifica se vale pedir uma fala ao Ollama, com no mínimo 4 min entre elas. Usa a persona do
  pet (`pets/<pet>/persona.txt`), exemplos das falas dele e o que ele lembra de você. Nunca escolhe
  modelo `:cloud`. Pode ser desligada na aba Diagramas.
- **Falas novas**: cerca de 16 a 18 arquivos por pet (emoções e eventos), incluindo `dispensa.txt`,
  que antes não existia. Bryan debochado e carente; Jorge coach trambiqueiro (sátira).
- Balões do pet na ilha, com nome do pet na origem, e voz quando ligada. Intervalo mínimo de 25 s
  entre balões espontâneos; regras configuradas não sofrem esse intervalo.

### Reações configuráveis (aba Diagramas)
- Cada reação: **gatilho** (emoção ou evento: preso, fuga, notebook, arremesso, dispensa) → **fala
  inicial** (tom e voz) → **espera** (5 a 120 s) → se você reagir: **fala + ação**; se não:
  **fala + ação**. Ações: balão, balão e voz, ficar feliz, nada.
- Editor em cartões (DOM, sem `innerHTML`) com diagrama de fluxo; salva sozinho e passa pela
  validação do Python (`normalizar_regras`): gatilho, ação, espera e tamanho são limitados.
- Arquivo: `memory/pets/<pet>/reacoes.json`. Já vem com dois exemplos.
- A aba **Diagramas livre** (Eslabón) continua disponível e só carrega quando é aberta.

### Áudio do sistema
- Suavização do espectro: sobe rápido, cai devagar, marcador de pico que desce devagar.
- Detecção de silêncio (1,5 s sem som): título e estúdio mostram "Silêncio".
- Reconexão automática: se a saída de som muda (fone, HDMI) ou o dispositivo falha, a captura
  tenta de novo com espera crescente (1 s até 10 s). Antes, um erro encerrava a captura.
- Estado "conectando" na interface (antes caía no ramo de erro).

### Controles (aba Centro)
- Paleta trocada para a do Núcleo: grafite espacial com ciano e violeta. Brilho, volume, luz de
  fundo, linha e rotação também saíram do laranja/rosa, e as faixas de demonstração do JS.

### Leveza
- Borda de luz do Núcleo agora gira por `transform` num pseudo-elemento (antes animava uma
  propriedade customizada com máscara, o que repintava a borda a cada quadro).
- Orbe a 30 fps quando a ilha está recolhida e sem balão.
- Estado da ponte: logs vão junto a cada 2 s (antes, a cada 0,5 s).
- Pet repinta a 30 fps quando está parado (no chão, sem andar, sem tremer, fora do notebook); em
  movimento continua a 60.
- Medido (regime estável, mesma máquina): WebEngine **21% → 14%** de CPU. O processo principal
  ficou em ~38–40% e o perfil mostra que o custo maior é repintura nativa das janelas translúcidas,
  não a lógica (o Python ocupa ~18% do tempo do quadro). Reduzir mais exige mudar a forma de
  desenhar o pet (cache de imagem); não foi feito agora.

## Correções encontradas pelos testes
- Teste de "apagar tudo" falhou: os eventos novos gravavam a memória depois da limpeza. Agora a
  memória só é gravada pelo `save()` central, que respeita `wiping`.
- Falas com duas opções: a regra "não repetir a última" anulava o peso. Só vale com mais de duas.
- `Convivencia.salvar` não grava mais sozinha a cada evento (antes criava a pasta na hora).

## Arquivos
- Novos: `pestinha/mind/convivencia.py`, `pets/bryan/persona.txt`, `pets/jorge/persona.txt`,
  `pets/*/falas/dispensa.txt`, `tests/test_convivencia.py`.
- Alterados: `app.py`, `controle/interacao.py`, `controle/sessao.py`, `mind/voz.py`,
  `sense/audio.py`, `ui/web_bridge.py`, `ui/web_island.py`, `ui/ilha.py`, `body/pet.py`,
  `paths.py`, `ui/web/ilha.js|css|html`, `ui/web/moxen/centro/centro.css|js`, `PRIVACIDADE.md`,
  `tests/test_web_island.py`, falas de Bryan e Jorge.

## Testes
- `tests/test_convivencia.py` (32 testes): validação das reações, sim/não e espera, memória e
  persistência, pesos das falas, prompt do Ollama, conteúdo de todos os pets, suavização e silêncio
  do áudio.
- Suíte completa: **503 passed, 5 skipped**. Pyflakes limpo. JavaScript válido (`node --check`).
- Ollama real (qwen2.5:3b, modelo local escolhido automaticamente): falas de IA em 0,2 a 1,5 s, curtas.
- Interface renderizada: editor de reações, criação de reação salva no Python, aba Controles na
  nova paleta, balão com origem "BRYAN".

## Limitações
- Falas de IA com modelo pequeno às vezes saem estranhas (ex.: "quiseram mais!"). A persona e os
  exemplos ajudam; modelos maiores tendem a sair melhor.
- A rede neural pulsada (LIF) continua aprendendo por condicionamento. Esta etapa adiciona
  aprendizado por engajamento nas falas e por reações, não um novo modelo de rede.
- Desfoque real do desktop atrás do vidro segue indisponível (ver changelog do Núcleo).
