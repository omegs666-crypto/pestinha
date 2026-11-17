# PADRÃO DE UI — Pestinha

Referência viva do design system do Pestinha. **Qualquer tela nova deve seguir
este documento** — é o que mantém a ilha, os painéis e os personas com cara de
um produto só. Fonte da verdade: `pestinha/ui/web/ilha.css` + `ilha.js`.

---

## 1. Identidade

> **Vidro grafite espacial.** Uma cápsula escura flutuando, com uma borda de
> luz que gira e respira, e acentos de cor que mudam com o humor do sistema.
> Tudo é arredondado, translúcido, flutuante — nada de cantos retos, nada de
> bordas sólidas, nada de fundo opaco.

Três ideias que definem o visual:

1. **O núcleo respira** — a ilha inteira parece viva (borda cônica girando,
   pulsos, física de mola em tudo que se move).
2. **A cor é estado** — ciano = calmo, verde = processando, violeta = pensando,
   âmbar = alerta, cinza = pausado. Nunca use cor "de enfeite".
3. **Dois lados da mente** — Bryan (emoção, ciano/verde) à esquerda do orbe,
   Jorge (razão, dourado) à direita. Cada persona tem sua cor assinatura.

---

## 2. Tokens (`:root` em `ilha.css`)

### Cores base

| Token | Valor | Uso |
|---|---|---|
| `--a1` | `#45e6ff` | acento principal — **muda com o humor** |
| `--a2` | `#7c6bff` | acento secundário — idem |
| `--vidro` | `rgba(4,5,8,.96)` | fundo da cápsula |
| `--vidro-2` | `rgba(20,23,36,.88)` | painéis internos |
| `--fio` | `rgba(255,255,255,.07)` | bordas internas (inset hairline) |
| `--texto` | `#eef1f8` | texto principal |
| `--suave` | `#a3a9ba` | texto secundário |
| `--apagado` | `#6b7186` | texto terciário / desabilitado |
| `--perigo` | `#ff5a6e` | erros, destrutivo |
| `--ambar` | `#ffb547` | avisos |
| `--verde` | `#4dffb0` | sucesso, "ligado" |

**Regra:** nunca hardcodar cor de acento — usar `var(--a1)`/`var(--a2)` para
que o elemento acompanhe o humor. `color-mix(in srgb, var(--a1) 22%, transparent)`
é o padrão para versões translúcidas do acento.

### Paleta de humores (espelhada em `ilha.js` → `HUMORES`)

| Humor | `--a1` | `--a2` | Significa |
|---|---|---|---|
| `calmo` | `#45e6ff` | `#7c6bff` | repouso |
| `processando` | `#4dffb0` | `#45a3ff` | trabalho em curso |
| `pensando` | `#b07bff` | `#ff6bd6` | LLM raciocinando |
| `alerta` | `#ffb547` | `#ff5a6e` | atenção / protesto |
| `pausado` | `#8a90a6` | `#4b5066` | sistema pausado |

### Tipografia

- **`--fonte`**: `"Segoe UI Variable Text"`, fallback `Segoe UI`/`system-ui` — texto.
- **`--fonte-num`**: `"Segoe UI Variable Display"` — números, hora, métricas.
- Corpo: `12px/1.4`, peso 500. Números com `font-variant-numeric: tabular-nums`.
- Escala usada: **10px** (rótulos/legendas, `letter-spacing .06–.14em`,
  muitas vezes `text-transform: uppercase`), **11px** (secundário),
  **12–12.5px** (corpo/bolhas), **38px** (número grande do card).

### Raios de borda (escala)

| Tamanho | Onde |
|---|---|
| `999px` | pílulas, toggles, chips, inputs arredondados |
| `22–24px` | cards, painéis `.ctl`, listas de grade |
| `18px` | bolhas de chat, iframes embutidos |
| `14px` | caixas `.chave`, `.vibra`, `.regra` |
| `10–12px` | botões da dock, itens de lista |
| `6px` | barras de progresso |

### Espaçamento

- Gaps internos: **6 / 8 / 10 / 12px** (escolha da escala, não valores soltos).
- Padding de painéis: **16px**. Padding da barra: **0 18px**.
- Chips pequenos: `3px 9px`; botões pílula: `5px 12px`.

### Sombras

- Elevação da cápsula: `0 18px 42px rgba(0,0,0,.55)`.
- Borda interna: `0 0 0 1px var(--fio) inset` — **sempre** inset, nunca `border`
  sólido em fundo escuro.
- Brilho de acento: `0 0 34px -10px color-mix(...)`.

---

## 3. Componentes

### Pílula (`.pilula`)
Botão padrão: `border: 1px solid rgba(255,255,255,.12)`, fundo
`rgba(255,255,255,.05)`, raio `999px`. Estado ligado usa `var(--a1)` no texto.
Chips de filtro são pílulas menores com `opacity .55` (acesa = 1).

### Chave (`.chave`)
Toggle de permissões: fileira de 14px de raio, trilho `38×22` com bolinha
`16px` branca. Liga = trilho em `var(--a1)`.

### Card (`.card`)
Raio `22px`, padding `16px`, fundo translúcido com brilho de acento radial.
Rótulo 10px uppercase + número grande 38px `--fonte-num`.

### Dock (`.dock`)
Coluna de 48px à esquerda; botões `30×30` raio 10; ativo = fundo
`rgba(255,255,255,.09)` + marcador lateral em `var(--a1)`; ícones SVG `16px`
stroke `1.8`. Item "ligado" (estado, não navegação) tinge o ícone de `var(--a1)`.

### Bolhas de chat (`.bolha`)
Raio `18px`, `max-width 78%`. Usuário = gradiente `a1→a2`. Assistente com
`data-autor` mostra a tag do autor (Jorge = dourado `#ffd166`, 9px uppercase).

### Balão (`.balao`)
Fala do narrador na pílula: origem colorida por `var(--a1)` + texto; abre/fecha
com `max-width` animado.

### Barras (`.barras`)
Trilho `6px` `rgba(255,255,255,.08)`, preenchimento com gradiente do acento.

---

## 4. Personas — cores assinatura

| Quem | Cor | Onde |
|---|---|---|
| **Bryan** | ciano `#45e6ff` / verde `#4dffb0` | mascote na pílula, pet no desktop |
| **Jorge** | dourado `#e2b13c` (casca), `#ffd166` (olhos/tag), `#b3261e` (gravata) | `jorge-ilha`, `jorgito`, tag JORGE |
| Núcleo/orbe | segue `HUMORES` | orbe, aura, borda da ilha |

Regra: dourado **só** é do Jorge — não usar `#e2b13c`/`#ffd166` para outros fins
(âmbar de aviso é `--ambar` `#ffb547`, diferente).

---

## 5. Canvas — convenções de desenho

- `ajustarCanvas(cv, w, h)` antes de desenhar (DPI); `ctx.setTransform(DPR(),…,0,0)`.
- Mãos **por cima** do rosto; membros por trás da casca; ombro sob a casca.
- Paleta do **Cérebro** (`ilha.js` → `CORES`): pet `#45e6ff`, emoção `#b07bff`,
  ação `#4dffb0`, contexto `#45a3ff`, drive `#ffb547`, pista `#ff6bd6`,
  episódio `#8a90a6`, você `#ff9edb`, conta `#ffd166`, sonho `#7c6bff`.
  Arestas: verde = valência positiva, vermelho = negativa, espessura = força.
- Métricas home (`grafico`): energia `#45e6ff`, estimulação `#b07bff`,
  atividade `#4dffb0` — sempre com `shadowBlur` do próprio acento.

---

## 6. Movimento

- **Easings**: entrada `cubic-bezier(.2,.9,.2,1.15)` (overshoot suave);
  transições comuns `.25–.6s ease`.
- **Física de mola** (`molaB rig/amo`) para tudo que parece vivo: braços, pulos.
- **FPS consciente**: ilha ociosa (recolhida, sem balão, sem resposta) desenha
  orbe + Jorge a **30 fps**; ativa/interativa a **60**. Elemento novo de canvas
  deve respeitar o mesmo throttle.
- **Vida constante**: nada fica 100% parado — deriva senoidal em nós do grafo,
  respiração nos personas, giro da aura. Amplitude pequena, sempre.
- "Zzz" e pulsos: alfa modulado por `sin(p·π)`, nunca `setInterval`.

---

## 7. Regras práticas (checklist para telas novas)

1. Fundo translúcido (`rgba(...,.8–.96)`), `backdrop`/gradientes radiais de acento.
2. Borda **inset** via `box-shadow`, nunca `border` sólido claro.
3. Raio dentro da escala (999 / 22–24 / 18 / 14 / 10–12 / 6).
4. Acentos via `var(--a1)`/`var(--a2)` — cor fixa só para identidade de persona
   ou semântica (perigo/âmbar/verde/dourado-Jorge).
5. Texto em pt-BR, tom do Pestinha (direto, com humor leve).
6. Sem biblioteca externa de UI — tudo é CSS + canvas nativo.
7. Todo elemento novo de canvas respeita o throttle ocioso 30/60 fps.
8. Assets versionados por `?v=AAAA-MM-DDx` no `index.html` — ao editar
   `ilha.css`/`ilha.js`, **incrementar o cache-buster**.
9. Preferir o real ao decorativo: animação deve refletir estado
   (humor, energia, sono) — efeito que não comunica nada é ruído.
