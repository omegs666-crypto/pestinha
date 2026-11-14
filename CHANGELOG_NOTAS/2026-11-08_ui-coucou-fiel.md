# 2026-11-08 — UI fiel ao Coucou: cápsula preta + pills + cartões

O usuário pediu para copiar a interface do Coucou de verdade. Foi estudado
`coucou-main/windows/src/style.css` (3651 linhas) e o visual foi replicado.

## Referência copiada (style.css do Coucou)

| Elemento Coucou | Valor | Onde foi aplicado |
|---|---|---|
| Ilha | `#000`, `border-radius: 0 0 14px 14px`, `top: 0` | `ilha.py`: cápsula preta colada na borda superior, cantos só embaixo |
| Compacto | mini-Mochi + relógio central | `ilha.py`: Rostinho + `HH:MM` + emoção pequena |
| Cartões | `#141518`, raio 20px, hairline `rgba(255,255,255,0.035)` | cartão de status + cartão de pills na visão geral |
| Pills | `#0e0f11`, `border-radius: 999px`, `rgba(255,255,255,0.14)`, label `600 10px dim-3` | grade 2×3 de pills na visão geral |
| Pill ativa | texto claro + borda mais forte | propriedade Qt `ativo` + stylesheet |
| Header | tabs 30×22 + ações à direita | nome do pet + "Fixar" + "✕" |
| Countdown | barra 2px `rgba(255,255,255,0.35)` no rodapé | `BarraContagem` |
| Paleta | ink `#f5f6f8`, dim `#9398a1`, dim-3 `#6b7079`, sem acento verde | `tema.py` reescrito inteiro |
| Botões | cápsula 999px; primário branco/preto | `tema.qss_botao()` |

## Arquivos

- `pestinha/ui/tema.py` — reescrito com a paleta Coucou (INK/DIM/CARD/CARD_FLAT,
  GREEN `#22c55e`, RED `#f4505e`, AMBER `#f5a524` etc.) e helpers fiéis.
- `pestinha/ui/ilha.py` — reescrito no formato Coucou: cápsula preta no topo,
  compacto com relógio, visão geral com header + 2 cartões + grade de pills.
- Painéis pintados (`monitor.py`, `panel.py`, `lab_mlp.py`) herdam a paleta
  nova automaticamente via `tema.*`.

## Verificação
- `pyflakes` limpo; `test_ilha.py`/`test_paineis.py` passando.
