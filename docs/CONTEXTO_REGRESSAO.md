# Contexto de regressão — bugs que já aconteceram

> **Para que serve:** ler antes de mexer no código e conferir depois de mudar. Os bugs
> deste projeto se repetem por **padrão**, não por azar: cada padrão abaixo já produziu
> vários bugs. Se a sua mudança toca num padrão, confira a seção dele.
>
> **Bug novo?** Ele entra aqui e ganha um teste em `tests/`. Bug de regressão que
> voltou? A seção do padrão precisa de um exemplo a mais — e provavelmente de um
> invariante novo no fuzzer (`ferramentas/fuzz_pestinha.py`).

## Como rodar a regressão

```bash
python -m pytest -q                                              # suíte inteira (Qt offscreen)
python -m pyflakes pestinha tests main.py ferramentas conftest.py
python -B ferramentas/fuzz_pestinha.py 150 80                    # 150 sessões x 80 ações, 0 violações
```

- Os testes não abrem janelas (`conftest.py` liga o offscreen) e nunca tocam a sua `memory/`.
- Mexeu na rede ou nos limiares? Rode `python ferramentas/gerar_doc_rede.py`.
- Criou/mudou módulos? Rode `python ferramentas/gerar_readmes.py`.

---

## Padrões de bug (o que mais voltou)

### P1 — Tempo real vs. ciclo fixo

**Por que acontece:** os ciclos do Qt são de 16/100/250/500 ms, mas atrasos reais acontecem.
Código que acumula ou decai por "ciclo" em vez de integrar o `dt` real fica inconsistente
com o resto (prazos e sensores usam `time.monotonic`).

**Sintoma típico:** efeito acelera/atrasado, aprendizado mais rápido ou mais lento que o
projetado, janela de evento medida errada.

**Como evitar:** tudo que acumula/decai recebe `dt` e integra por ele; medições usam
`time.monotonic()` real. Em `think`, o tempo já é integrado em passos de até 100 ms.

**Casos:** BUGS_30_RODADA #15–21 (tom motor, emoção, protesto, tristeza, aprendizado,
rotina, euforia — todos por ciclo em vez de tempo; detecção de aproximação do cursor
dividia por 0,1 s fixo) e AUDITORIA_30_BUGS BUG-25 (atraso de callback perdia dinâmica).
Guardião: `tests/test_30_bugs.py`, `tests/test_auditoria_30.py`.

### P2 — Estado muda durante pausa / escondido / desligado / pânico

**Por que acontece:** a política de sessão (`_congelado`, `update_visibility`) fica em
`controle/sessao.py`, mas handlers de interação, timers próprios e janelas criadas
depois podem não passar por ela.

**Sintoma típico:** cutucada muda o estado pausado; fogos continuam animando pausado;
corpo fica preso no ar depois do pânico no meio do arraste.

**Como evitar:** qualquer caminho novo que mexe em estado (rede, homeostase, objetos,
posição) precisa responder a `_congelado()` / `paused` / `hidden` / `ativo`. Timer
independente (como o dos fogos) precisa de pausa/retomada próprias ligadas à sessão.

**Casos:** ANALISE_TECNICA #1 e #5; BUGS_30_RODADA #03, #04, #05, #27, #28, #29;
AUDITORIA_30_BUGS BUG-01, BUG-05, BUG-06, BUG-16.
Guardião: `tests/test_30_bugs.py`, `tests/test_auditoria_30.py`, `tests/test_cantinho_cenarios.py`.

### P3 — Prazos e janelas temporais

**Por que acontece:** deadlines guardam `monotonic` absoluto; a pausa desloca os prazos
conhecidos mas esquece referências laterais (última ação, início do episódio, pedido).

**Sintoma típico:** episódio "vence" durante a pausa e resolve como fracasso; castigo
de 1 s vira inválido porque a pausa de 100 s consumiu a janela de punição; pedido de
trabalho expira e vira recusa injusta.

**Como evitar:** ao criar um prazo novo, verifique se ele precisa entrar no `deslocar`
da retomada e se "tempo desde X" usa a mesma base que foi deslocada.

**Casos:** BUGS_30_RODADA #07, #08, #27, #28; AUDITORIA_30_BUGS BUG-08;
BUGS_NOVO_CASTIGO #3.
Guardião: `tests/test_30_bugs.py`, `tests/test_castigo_bugs_rede.py`, `tests/test_castigo_real.py`.

### P4 — Visibilidade dessincronizada

**Por que acontece:** `setVisible(True)` chamado na criação do objeto não consulta a
visibilidade da sessão; e "esconder" varre o que existe, mas o que é criado depois
reaparece.

**Sintoma típico:** placa/cartaz/notebook visível com o pet escondido ou desligado;
painel aberto à mão pisca e some (o varredor fecha no quadro seguinte).

**Como evitar:** todo objeto de cena cria escondido e só aparece via `update_visibility`
ou guardando a visibilidade desejada e aplicando na criação. Painel aberto à mão deve
ser lembrado como "quer ficar aberto".

**Casos:** BUGS_30_RODADA #01, #02, #06; AUDITORIA_30_BUGS BUG-04, BUG-27.
Guardião: `tests/test_30_bugs.py`, `tests/test_paineis.py`.

### P5 — Estado salvo sem validação / schema

**Por que acontece:** `read_json` tolera arquivo ilegível, mas JSON **válido com
conteúdo errado** (tipo, domínio, NaN, shape) passava direto para o objeto.

**Sintoma típico:** app não abre (TypeError/ValueError na inicialização), NaN entra na
rede, metade do estado aplicada antes da falha.

**Como evitar:** todo `load` valida tipo + domínio + finitude + shape **em temporários**
e só publica depois de validar tudo (tudo-ou-nada). NaN/infinito são recusados na
leitura e na escrita (`store.py` já faz; o modelo precisa fazer o resto). Todo estado
salvo novo precisa de teste com dados inválidos.

**Casos:** ANALISE_TECNICA #2, #3, #4; AUDITORIA_30_BUGS BUG-18 a BUG-24.
Guardião: `tests/test_robustez.py`, `tests/test_robustez_v2.py`, `tests/test_auditoria_30.py`,
`tests/test_migracao.py`.

### P6 — Cópia vs. referência / fonte duplicada

**Por que acontece:** diálogo edita a mesma referência que o app lê depois (a transição
compara errado), ou guarda uma cópia que dessincroniza de eventos externos; ou uma
constante existe em dois lugares.

**Sintoma típico:** escolha do usuário descartada; pânico revertido por mexer numa
opção qualquer da janela aberta; limiar ajustado não tem efeito (a outra fonte manda).

**Como evitar:** a UI emite a mudança, o app compara com o estado anterior — ninguém
trabalha sobre a cópia do outro; constante tem uma fonte só (`ajustes.py`).

**Casos:** BUGS_30_RODADA #13, #14, #23; AUDITORIA_30_BUGS BUG-01; ANALISE_TECNICA #7.
Guardião: `tests/test_30_bugs.py`, `tests/test_robustez_v2.py`.

### P7 — Ação pendente dispara tarde ou não dispara

**Por que acontece:** pedido do menu grava um "quer fazer" que nenhum consumidor usa
(ou usa tarde demais); ou a intenção é consumida antes do evento que a completaria.

**Sintoma típico:** "travessura agora" não faz nada ou apronta muito depois; soltar no
ar não entra no castigo porque a soltura foi consumida antes do pouso.

**Como evitar:** pedido explícito tem vida curta (o do menu vale 10 s) e um consumidor
claro; intenção que depende de um segundo evento persiste até ele chegar.

**Casos:** BUGS_30_RODADA #08; AUDITORIA_30_BUGS BUG-10; TESTE_100_CANTINHO #002.
Guardião: `tests/test_30_bugs.py`, `tests/test_cantinho_cenarios.py`.

### P8 — Recurso desligado segue ativo / estimulando

**Por que acontece:** a permissão é checada para criar coisas novas, mas o que já está
em andamento (efeito, canal sensorial, acumulador) continua.

**Sintoma típico:** bolinha guardada segue alimentando `TOY_NEAR`; fogos desligados
terminam a animação; rotina desligada segue acumulando o minuto.

**Como evitar:** ao desligar uma permissão, revogar também o efeito em andamento e
zerar os canais/rastreadores que dependem do objeto.

**Casos:** BUGS_30_RODADA #04, #05; AUDITORIA_30_BUGS BUG-07, BUG-09, BUG-11, BUG-28.
Guardião: `tests/test_30_bugs.py`, `tests/test_auditoria_30.py`.

### P9 — Arquivo / imagem ilegível

**Por que acontece:** conteúdo lido é usado sem checar se decodifica/interpreta.

**Sintoma típico:** imagem corrompida vira objeto invisível na tela; bytes UTF-8
inválidos derrubam a leitura de episódios inteira; janela que some no meio da leitura
levanta exceção.

**Como evitar:** carregar/validar antes de instanciar o objeto; leitura por linha
descarta a ruim em vez de derrubar o arquivo; adaptadores de plataforma tratam o
elemento que some entre duas chamadas.

**Casos:** BUGS_30_RODADA #22; AUDITORIA_30_BUGS BUG-22, BUG-30.
Guardião: `tests/test_30_bugs.py`, `tests/test_robustez.py`, `tests/test_plataforma.py`.

### P10 — Rótulos e nomes desatualizados

**Por que acontece:** canal/motor novo sem rótulo em `ui/rotulos.py`; texto de
apresentação que ficou do nome antigo; resumo que esquece um tipo de conteúdo.

**Sintoma típico:** monitor mostra nome interno em vez de português; bandeja/notificação
com nome errado; resumo de assets não conta memes de trabalho nem bilhetes tristes.

**Como evitar:** canal/motor novo → rótulo novo; conteúdo novo → resumo novo.

**Casos:** BUGS_30_RODADA #12, #25, #26.
Guardião: `tests/test_30_bugs.py`, `tests/test_escolha_pet.py`.

### P11 — Física e geometria de borda

**Por que acontece:** colisão com centro dentro do retângulo, escolha de plataforma
pela ordem da lista em vez da ordem do trajeto, área ancorada no chão em vez de seguir
a referência, olhar calculado contra a zona em vez da parede.

**Sintoma típico:** bolinha fica dentro do objeto; pet atravessa a janela de cima e
pousa na de baixo; área de castigo fica no chão com a placa no alto; raiva olha para
a parede errada.

**Como evitar:** projeção de penetração em todos os ramos; escolher a primeira
superfície cruzada no trajeto; âncoras relativas à referência (base da placa, parede
mais próxima).

**Casos:** BUGS_30_RODADA #30; AUDITORIA_30_BUGS BUG-14, BUG-15; TESTE_100_CANTINHO #030, #037.
Guardião: `tests/test_30_bugs.py`, `tests/test_nucleo.py`, `tests/test_cantinho_cenarios.py`.

### P12 — Falha de disco interrompe fluxo essencial

**Por que acontece:** save/persistência no caminho crítico de pânico, saída ou
apagar dados.

**Sintoma típico:** pânico não esconde o pet porque a gravação falhou; `quit` não
alcança `QApplication.quit` porque um save deu OSError; "apagar tudo" recria `memory/`
com o log.

**Como evitar:** desligamento visual e limpeza rodam mesmo com disco falhando; a
persistência é tentada em bloco separado; antes de apagar, suspende-se toda gravação
incluindo o log; falha é reportada, não tratada como sucesso.

**Casos:** AUDITORIA_30_BUGS BUG-02, BUG-03; ANALISE_TECNICA #6; BUGS_30_RODADA #10.
Guardião: `tests/test_auditoria_30.py`, `tests/test_robustez_v2.py`.

### P13 — Posse do usuário ignorada

**Por que acontece:** comportamento autônomo age sobre um objeto que a pessoa está
segurando; release de qualquer botão encerra arraste do outro.

**Sintoma típico:** pet chuta a bolinha na mão do usuário; soltar o botão direito
cancela o arraste do esquerdo.

**Como evitar:** checar `held`/`dragging` antes de agir; o arraste só termina no
release do botão que o começou.

**Casos:** BUGS_30_RODADA #11; AUDITORIA_30_BUGS BUG-12, BUG-13.
Guardião: `tests/test_30_bugs.py`, `tests/test_auditoria_30.py`, `tests/test_bolinha.py`.

### P14 — Identidade de episódio e efeitos tardios

**Por que acontece:** punir "o último episódio" casa com o primeiro aberto do mesmo
contexto; recompensa negativa continua depois da saída; fuga pendente atravessa a
recaptura.

**Sintoma típico:** castigo pune a travessura errada; sono "desaprende" a punição;
soltar não encerra a penalidade; entrar de novo no canto traz uma fuga fantasma.

**Como evitar:** episódio tem `id` e resolve exatamente ele; punição é evento com fim
explícito; entrada nova cancela tentativas anteriores (e a interrompida conta como
fuga errada → receio).

**Casos:** BUGS_NOVO_CASTIGO #1, #2, #4, #5.
Guardião: `tests/test_castigo_bugs_rede.py`, `tests/test_castigo_integracao.py`.

### P15 — Controle fora da política de sessão

**Por que acontece:** timers próprios (efeitos, janelas) e canais de decisão com nomes
parecidos escapam ao congelamento ou misturam efeitos.

**Sintoma típico:** efeito anima com a sessão pausada; antecipação de cutucada ajuda
a fuga porque os dois usavam o mesmo `ANTICIPATE`.

**Como evitar:** timer próprio ganha pausa/retomada ligadas à sessão; pista com
significado próprio ganha canal próprio (`ANTECIPA_PLACA`).

**Casos:** AUDITORIA_30_BUGS BUG-06; BUGS_NOVO_CASTIGO "observação de arquitetura".
Guardião: `tests/test_auditoria_30.py`, `tests/test_castigo_bugs_rede.py`,
`tests/test_cantinho_rede.py`.

---

## Invariantes do fuzzer (I01–I30)

Rodados a cada passo de `ferramentas/fuzz_pestinha.py`. Ao acrescentar um comportamento,
pense em qual invariante ele deveria ganhar.

| # | Regra | Grupo |
|---:|---|---|
| I01 | `pet_state.castigo` == `castigo.dentro` | cantinho |
| I02 | preso ⇒ cantinho ativo | cantinho |
| I03–I12 | desligado/escondido ⇒ nada visível (pet, objetos, placa, notebook, painéis, fogos, cartazes, bolinha, papel, cartaz do castigo) | visibilidade |
| I13 | corpo sempre com coordenadas finitas | física |
| I14 | corpo dentro da área (com folga) | física |
| I15 | nunca sentado e preso ao mesmo tempo | cantinho |
| I16 | destino de fuga só com fuga em andamento | cantinho |
| I17 | sinais da rede finitos em [0, 1] | rede |
| I18 | homeostase em [0, 1] | homeostase |
| I19 | pesos da rede e taxas dos pools finitos | rede |
| I20 | bolinha guardada/desligada ⇒ invisível | visibilidade |
| I21 | preso ⇒ sem cartaz de protesto/tristeza | cantinho |
| I22 | travessuras desligadas ⇒ nenhum objeto | permissões |
| I23 | fogos desligados ⇒ sem fogos | permissões |
| I24 | sinal de arraste só quando segurado | interação |
| I25 | altura da tampa do notebook só quando sentado | notebook |
| I26 | cartaz do castigo só quando preso | cantinho |
| I27 | notebook escondido ⇒ não senta | notebook |
| I28 | missão "deliver" aponta para objeto que existe | travessuras |
| I29 | pausado ⇒ a rede não avança | sessão |
| I30 | (ver `ferramentas/fuzz_pestinha.py`) | sessão |

---

## Mapa "se mexer em X, rode Y"

| Arquivo / pasta | Rode além do `pytest -q` |
|---|---|
| `pestinha/ajustes.py` | fuzzer completo + `gerar_doc_rede.py` (limiares) |
| `pestinha/core/nervous_system.py` | `test_nucleo`, `test_cantinho_rede` + `gerar_doc_rede.py` + fuzzer |
| `pestinha/core/conditioning.py` | `test_condicionamento` + cantinho |
| `pestinha/core/episodic.py` | `test_nucleo` + `test_castigo_bugs_rede` |
| `pestinha/mind/castigo_ctl.py` | **todos** os `test_castigo*` e `test_cantinho*` |
| `pestinha/mind/mischief_ctl.py` | `test_30_bugs` + `test_auditoria_30` + fuzzer |
| `pestinha/store.py`, `migracao.py` | `test_robustez*`, `test_migracao` |
| `pestinha/plataforma/*` | `test_plataforma` + teste manual no SO real |
| `pets/*.json`, `pets/*/` | `test_jorge`, `test_escolha_pet`, `test_conteudo` |
| `pestinha/ui/rotulos.py` | `test_30_bugs` + `test_paineis` |
| `pestinha/controle/sessao.py` | `test_app`, `test_cantinho_cenarios`, fuzzer |
| `pestinha/sense/timeline.py` | `test_app` + revisar PRIVACIDADE.md |
| `assets/comum/*` | `test_conteudo`, `test_30_bugs` |
| `ferramentas/fuzz_pestinha.py` | rodar 150×80 e documentar violação nova aqui |

---

## Checklist antes de dar por pronto

- [ ] Acumulador/decaimento usa `dt` real, nunca passo fixo (P1)
- [ ] Pausa, esconder, desligar e pânico não mudam estado (P2) — inclusive timers próprios (P15)
- [ ] Prazo novo entra no deslocamento da retomada; referências laterais também (P3)
- [ ] Objeto criado escondido; visibilidade passa por `update_visibility` (P4)
- [ ] Estado salvo valida tudo em temporários antes de aplicar; teste com dados inválidos (P5)
- [ ] Nenhuma cópia dessincronizada de configuração; constante numa fonte só (P6)
- [ ] Pedido pendente tem vida curta e um consumidor (P7)
- [ ] Permissão desligada revoga efeito em andamento e zera canais dependentes (P8)
- [ ] Arquivo/imagem validados antes de instanciar (P9)
- [ ] Canal/motor/conteúdo novo tem rótulo e entra no resumo (P10)
- [ ] Geometria: penetração em todos os ramos; primeira superfície no trajeto; âncora na referência (P11)
- [ ] Falha de disco não impede desligar/sair/apagar (P12)
- [ ] Ação autônoma respeita `held`/`dragging`; release só do botão certo (P13)
- [ ] Episódio resolvido por identidade; efeito tardio tem fim explícito; entrada cancela tentativa anterior (P14)
- [ ] Canal novo com significado próprio (não reusa canal para desfecho diferente) (P15)
- [ ] `pytest -q` + `pyflakes` verdes; fuzzer 150×80 se mexeu em comportamento
- [ ] Bug encontrado entrou neste arquivo com o padrão e ganhou teste

---

## Índice de relatórios

| Relatório | Bugs | Teste guardião |
|---|---:|---|
| [ANALISE_TECNICA.md](auditorias/ANALISE_TECNICA.md) | 8 falhas (pânico incompleto, carga parcial, NaN, schemas, pausa, apagar dados, rotina, condicionamento) | `test_robustez_v2.py` |
| [AUDITORIA_30_BUGS.md](auditorias/AUDITORIA_30_BUGS.md) | 30 (controle, dados, ciclo de vida, física, adaptadores) | `test_auditoria_30.py` |
| [TESTE_100_CANTINHO.md](auditorias/TESTE_100_CANTINHO.md) | 100 cenários do cantinho | `test_cantinho_cenarios.py` |
| [BUGS_NOVO_CASTIGO.md](auditorias/BUGS_NOVO_CASTIGO.md) | 5 (rede e cantinho) | `test_castigo_bugs_rede.py` |
| [BUGS_30_RODADA.md](auditorias/BUGS_30_RODADA.md) | 30 (fuzzing + revisão) | `test_30_bugs.py` |
