# 2026-11-08 — UI/UX estilo Coucou: interações visuais novas

Plano de referência: `docs/PLANO_UIUX_COCOU.md` (fases A e B, itens de maior impacto).

## O que mudou

### Ilha (`pestinha/ui/ilha.py`)
- **Barra de contagem de recolhimento** (`BarraContagem`): barrinha verde fina no
  rodapé da ilha que mostra quanto tempo falta para ela recolher sozinha —
  igual à countdown bar do Coucou. Liga só quando o recolhimento automático
  está armado; some quando o mouse volta, fixa ou recolhe.
- **Saudação ao abrir**: a visão geral acena "👋" por ~1,3 s ao expandir.
- Refatorado o agendamento do recolher para `_agendar_recolher()` /
  `_cancelar_recolher()` / `_tick_barra()` — um só lugar controla timer + barra.

### Pet (`pestinha/body/pet.py`)
- **Duplo clique = carinho**: novo sinal `double_clicked`; dois cliques rápidos
  fecham os olhinhos de felicidade na hora.
- **Corações no carinho**: enquanto você faz carícia no pet, corações ♥ sobem
  devagar dele (desenho determinístico no tempo, sem custo de física).

### Interação (`pestinha/controle/interacao.py`)
- `on_double_click()`: carinho instantâneo — `mark_caress`, emoção "contente",
  estímulo/contato da homeostase (`caress`), memória e segundo cérebro.
  Respeita `_congelado()` (pausa/esconder/pânico não aprendem).

### App (`pestinha/app.py`)
- Liga `pet.double_clicked` → `on_double_click`.

## Verificação
- `pyflakes` limpo em `pestinha`, `tests`, `main.py`, `ferramentas`.
- `tests/test_ilha.py` + `test_paineis.py` + `test_app.py` + `test_carinho.py`: 24 passaram.
- Suíte completa rodada após a mudança (ver resultado no terminal).

## Não implementado (ficou no plano)
- Headers nos painéis flutuantes, sons, partículas além dos corações, atalhos
  de teclado globais, delays configuráveis na UI, abertura por hover.
