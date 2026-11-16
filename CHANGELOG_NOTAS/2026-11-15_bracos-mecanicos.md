# 2026-11-15 — Braços mecânicos por persona (protótipo do usuário); Bryan é o primeiro

## Origem
- Protótipo enviado pelo usuário: quatro molas independentes (X e Y de cada braço),
  ondas harmônicas gesticulando enquanto fala, flutuação de respiração em repouso e
  cápsulas escuras com contorno neon nas laterais.

## O que mudou
- `pestinha/body/bracos.py` (novo): `Bracos` com a mesma física, usando a `Mola`
  existente; `passo(falando, boca)` segue o contrato da `Boca` — a abertura da boca
  aumenta a amplitude dos gestos.
- `pestinha/body/pet_state.py`: `st.bracos` nasce junto do `st.boca`.
- `pestinha/body/desenho_rosto.py`: `Aparencia.bracos` (cor do contorno; `None` = sem
  braços), `aparencia_de` aceita `"bracos": true` (cor = moldura) ou `"#rrggbb"`, e
  `draw_face` desenha as cápsulas por trás do corpo. Ancoragem ±72 (o ±84 do
  protótipo cortava 8 px fora da janela de 200 px).
- `pestinha/body/pet.py` e `app.py`: os braços são desenhados e as molas avançam
  junto da boca, com a mesma fonte de "falando" (a Voz).
- `pets/bryan.json`: `"aparencia": {"bracos": true}` — o Bryan ganha os braços.
- Ilha WebEngine: a ponte envia a cor dos braços; o mascote em canvas desenha os
  mesmos braços com as mesmas molas (o canvas alargou para 64×44 para caber).
- `tests/test_aparencia.py`: Bryan com braços + validação do novo campo.

## Verificação
- Render Qt: braços nas laterais em repouso e gesticulando na fala, sem corte.
- Suíte: 542 testes, pyflakes e sintaxe JS limpos.

## Limitações
- No mascote da ilha, "falando" é o streaming do chat (o mesmo que mexe a boca).
- Os braços só aparecem quando o pet tem `bracos` na aparência; Jorge continua sem.
