# 2026-11-15 — Grade de widgets: layout, alinhamento e tema do Núcleo

## Problemas encontrados
- A grade usava o tema cinza/azul do Moxen e fontes (Onest, Azeret Mono) que não existem no PC: os
  números caíam numa serifada e o texto não combinava com a ilha.
- Dentro da ilha (≈970 px úteis), a grade caía no modo estreito: widgets em faixa única, a paleta
  embaixo e os botões esticados.
- O título do widget começava ~30 px depois do conteúdo (a alça ocupava a esquerda).
- A área tracejada de espaço livre aparecia o tempo todo.
- O anel "Estímulo" tinha o texto sobre a borda; o "Logs" vazio tinha a bolinha que empurrava o texto.
- Fundo transparente num iframe aparece branco no WebEngine: o documento da grade precisa de fundo sólido.

## O que mudou
- **Tema `?tema=oscuro`** (`moxen/parrilla/parrilla.css`): paleta do Núcleo (vidro grafite, ciano
  #45e6ff, violeta #7c6bff), fontes Segoe UI Variable, sem cartão e sem sombras dentro do painel.
- **Layout:** breakpoint estreito de 980 px → 760 px; paleta com 250 px de largura, para a área de
  widgets ter 12 colunas dentro da ilha (≥ 640 px).
- **Alinhamento:** o título do widget começa na mesma margem do conteúdo; a alça e o "×" foram para
  a direita; a alça some em widgets de até 200 px.
- **Widgets iniciais** ocupam a largura da ilha (energia 4, atividade 5, estímulo 3 × 3, logs 6 × 3).
- **Interação:** a área tracejada só aparece enquanto se arrasta; hover com contorno ciano; botões
  primário/secundário no tema da ilha; barras de scroll finas.
- Cores fixas restantes (logs e legenda do anel) trocadas pela paleta do Núcleo.

## Limitações
- A grade ainda usa o Moxen como base (código com licença do Moxen; alterações permitidas pela
  licença, redistribuição não). Os textos de licença continuam em `moxen/parrilla/LICENCIA.txt`.
- Arrastar e redimensionar foram validados por código e pela renderização, não com o mouse físico.
