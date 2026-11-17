# 2026-11-17 — Aba Widgets: design hero + 5 widgets novos + paleta completa

## Pedido

Focar na aba Widgets (a grade `moxen/parrilla`): design com letra grande ao
lado de letra miúda, desenho atrás de desenho, informação fixa — e mais
funções, anexos e gráficos, mantendo o que existe e tudo modificável.

## Design (o pedido visual)

- **Letra grande × letra miúda**: título hero "Painel `DO PESTINHA`" (small
  caps ao lado), relógio com hora gigante e segundos miúdos, humor dele em
  display de 34 px sobre metadados de 12 px.
- **Desenho atrás de desenho**: marca d'água de grafo neural (`pa-marca-agua`,
  SVG com nós e arestas a 7% de opacidade) atrás do card — soma aos dois halos
  e ao grão que já existiam.
- **Informação fixa**: faixa `.pa-fixo` no cabeçalho — hora, humor e energia
  dele ao vivo, sempre visíveis independente dos widgets na grade.

## Widgets novos (todos arrastáveis, redimensionáveis e removíveis)

| Tipo | O que faz |
|---|---|
| `relogio` | Hora gigante + segundos + data por extenso; humor/energia embaixo |
| `emocao` | "Humor dele" em display grande + chips de estado (pausado, pensando, carinho, jorge) |
| `acoes` | **Funções**: botões Pausar, Voz, Um persona, Jorge, Travessuras, Modo avião — cada um manda `ponte.acao` e **acende quando ligado** (`data-on` + estado ao vivo) |
| `nota` | **Anexo editável**: papel preso com `contenteditable`; o texto viaja dentro do item do layout e **salva junto com a disposição** (nada novo no backend) |
| `pulso` | **Gráfico vivo**: sparkline dupla (energia + atividade neural) alimentada por histórico local das métricas, área + 2 linhas |

E a paleta agora oferece **todos** os tipos (antes só 3): + anel, barras,
calor, lista de tarefas e cifra, cada um com ícone e tamanho próprio.

## Mudanças

- **`ilha.js`** `enviarMetricas`: envia o estado completo — `emocao`, `pet`,
  `mente`, números puros (`*_n`) para sparklines e chaves de estado
  (`pausado`, `processando`, `voz`, `travessuras`, `solo`, `mente_llm`,
  `offline`, `carinho`) para o `data-on`.
- **`parrilla/index.html`**: marca d'água + `.pa-fixo` no header; tick global
  do relógio (`data-relogio`/`data-relseg`/`data-reldata`); handler estendido
  com `data-on` (acende por estado) e `data-spark`/`data-spark-area`
  (histórico → path SVG).
- **`parrilla.js`**: `t.html(it)` recebe o item (nota renderiza o texto dela);
  `preparaNota` (edição com debounce → `cambio()`); `preparaAcoes` (posta
  `acao` ao pai); paleta padrão com os 13 tipos; ícones e tamanhos para todos.
- **`parrilla.css`**: estilos dos 5 widgets + hero + faixa fixa + marca
  d'água; paleta com scroll (`max-height: 430px`).

## Testes

- `node --check` nos dois JS.
- Captura validada: header hero, faixa fixa ao vivo, paleta com widgets novos.
