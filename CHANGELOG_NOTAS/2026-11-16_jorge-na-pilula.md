# 2026-11-16 — Jorge mora na pílula (dorme, acorda quando chamado)

## Pedido

- Colocar na consciência do Jorge que ele é brasileiro (pt-BR).
- Jorge também visível na ilha — um de cada lado — dormindo; só acorda quando
  chamado e quando vai responder.

## Mudanças

- **`pets/jorge/persona_mente.txt`**: identidade brasileira explícita —
  "Você é brasileiro, fala português do Brasil naturalmente" (antes era só
  instrução de idioma de saída).
- **`index.html`**: canvas `#jorge-ilha` na barra, à **direita do orbe** —
  Bryan (mascote) à esquerda, Jorge à direita, os dois lados da mente
  flanqueando o núcleo neural. Cache-buster `?v=2026-11-16c`.
- **`ilha.css`**: `#jorge-ilha` 40×44 px; dorme com `opacity .45`; acordado
  ganha `drop-shadow` dourado (transição .6 s).
- **`ilha.js`**: módulo `jorgeIlha` — cara do `pets/jorge.json` (casca dourada,
  tela escura, olhos dourados, gravata vermelha):
  - **Dormindo**: olhos em arcos fechados, respiração (bob senoidal) e três
    "z" subindo e sumindo em loop.
  - **Acordando**: pálpebra abre com easing (`abertura` 0→1); brilho dourado.
  - **Acorda quando**: mensagem enviada no chat (`enviarChat` → `acordar`),
    LLM processando/streamando (`estado.processando`/`respondendo`), narrador
    pensando, e qualquer balão com origem "jorge".
  - **Clique nele** = chamar: acorda 6 s, abre a ilha na aba Chat e solta
    "acordei… manda, chefe." no balão com tag JORGE.
  - `pointerdown` com `stopPropagation` (não arma o arraste da ilha).
  - Visível só quando `mente_llm` está ligado; desenhado no mesmo throttle
    de 30 fps ocioso / 60 fps ativo do orbe.
  - Exposto em `nucleoDebug.jorgeIlha` para testes/capturas.

- **`ilha.js` (braços)**: Jorge ganhou braços mecânicos na pílula — mesma
  leitura do mascote (membro com contorno dourado + metal escuro por dentro,
  ombro sob a casca, mão-luva por cima do rosto). Poses:
  - **Dormindo**: braços largados nas laterais, acompanhando a respiração.
  - **Acordado**: levantam até a altura do peito com balanço leve.
  - **Respondendo**: gesticulam alternados, explicando.
  - Interpolação suave (lerp por frame); sem física de mola — escala pequena.

## Testes

- `test_web_island.py`: 29 passam.
- Captura validada: pílula mostra Bryan | orbe | Jorge dormindo (olhos fechados,
  "z" subindo, braços caídos com as mãos-luva visíveis).
