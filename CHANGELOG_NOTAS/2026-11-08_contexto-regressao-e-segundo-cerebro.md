# 2026-11-08 — Contexto de regressão + Segundo cérebro (Obsidian)

## O que mudou

### 1. `docs/CONTEXTO_REGRESSAO.md` (novo)
Arquivo de contexto de regressão para ler antes/depois de mexer no código e evitar repetir
bugs já vistos. Consolida as 5 auditorias de `docs/auditorias/` em **15 padrões de bug**
(P1 tempo real vs. ciclo, P2 estado durante pausa/escondido/pânico, P3 prazos, P4 visibilidade,
P5 estado salvo/schema, P6 cópia vs. referência, P7 ação pendente, P8 recurso desligado ativo,
P9 arquivo ilegível, P10 rótulos, P11 física/geometria, P12 falha de disco, P13 posse do usuário,
P14 identidade de episódio, P15 controle fora da sessão), cada um com sintoma, como evitar e
teste guardião. Inclui a tabela dos invariantes do fuzzer (I01–I30), o mapa "mexeu em X → rode Y"
e um checklist de fechamento. Registrado também em `docs/README.md`.

### 2. Segundo cérebro: integração com Obsidian (nova funcionalidade, opt-in)
O pet escreve em Markdown num vault do Obsidian escolhido pelo usuário:

- **`<vault>/Pestinha/<pet>/diario/AAAA-MM-DD.md`** — diário do dia: cutucadas, carinho
  (início/fim), arremessos, travessuras dispensadas, notebook arrancado, entradas/saídas do
  cantinho, fugas, sentar/levantar do notebook, sono, mudanças de estágio do protesto e da
  tristeza. Limite de `SEGUNDO_CELEBRO_MAX_LINHAS` (500) por dia.
- **`<vault>/Pestinha/<pet>/aprendizado.md`** — o que ele aprendeu: pesos da regra de três
  fatores, forças do condicionamento, fugas/rancor/receio do cantinho e homeostase.
  Reescrito só quando o conteúdo muda.
- **`<vault>/Pestinha/<pet>/perfil.md`** — ficha do pet com a emoção atual.

## Arquivos

| Arquivo | Mudança |
|---|---|
| `docs/CONTEXTO_REGRESSAO.md` | novo: catálogo de padrões de bug |
| `docs/README.md` | entrada nova na tabela de documentos |
| `pestinha/mind/segundo_cerebro.py` | novo: controlador do segundo cérebro |
| `pestinha/store.py` | novo `write_text()`: escrita de texto atômica (temp + os.replace) |
| `pestinha/config.py` | `segundo_celebro` (False) e `segundo_celebro_pasta` ("") em `DEFAULT_PERMISSIONS`; grupo "Segundo cérebro" em `PERMISSION_GROUPS` |
| `pestinha/ajustes.py` | `SEGUNDO_CELEBRO_MAX_LINHAS` + `_LIMITES` |
| `pestinha/app.py` | cria `self.cerebro2`; registra carinho/protesto/tristeza; `_segundo_cerebro_estados()` detecta bordas de preso/sentado/sono/fuga; importa `STAGE_NAMES` |
| `pestinha/controle/interacao.py` | eventos de cutucada, arremesso, dispensa e notebook arrancado |
| `pestinha/controle/sessao.py` | `_salvar_segundo_cerebro()` no ciclo de gravação de 30 s |
| `pestinha/ui/ui.py` | grupo "Segundo cérebro" com botão "Escolher pasta…" (QFileDialog); botão só habilita com o toggle ligado |
| `tests/test_segundo_celebro.py` | novo: 17 testes (escrita, desligado, pasta inválida, privacidade, UI, integração no app, pausa) |
| `PRIVACIDADE.md` | seção do segundo cérebro em "Fora da pasta de dados" |
| `pestinha/mind/README.md`, `tests/README.md` | regenerados por `ferramentas/gerar_readmes.py` |

## Decisões

- **Opt-in, desligado por padrão**: nada é escrito até ligar a permissão E escolher a pasta.
- **Só escreve**: o app nunca lê o vault; só cria/edita dentro de `Pestinha/<pet>/`.
- **Privacidade**: diário usa só categorias de evento e hora, como a `timeline.csv` — nunca
  nome de programa nem título de janela. "Apagar todos os dados" não apaga o vault (é do usuário).
- **Falha silenciosa**: pasta sem permissão/aviso de erro loga uma vez por sessão e não derruba.
- **`pet_id_valido`**: o id do pet vira nome de pasta só depois de validado — nada de escrever fora.
- **Buffer no ciclo de 30 s**: os eventos do diário entram na gravação periódica existente
  (`app.save`), sem timer novo e sem custo por evento.

## Verificação

- `python -m pytest -q`: 392 passam, 5 pulados; **3 falhas ambientais pré-existentes**
  (`test_modo_teste_mostra_os_paineis`, `test_painel_arrastado_salva_a_posicao`,
  `test_painel_nao_entra_na_lista_de_pouso`) — passam isoladas; a suíte falha neles porque
  `is_fullscreen()` consulta a janela real em primeiro plano do desktop (algo em tela cheia
  durante a execução longa). Não é regressão desta mudança.
- `python -m pyflakes pestinha tests main.py ferramentas conftest.py`: limpo.
- 17/17 testes novos do segundo cérebro passam.
