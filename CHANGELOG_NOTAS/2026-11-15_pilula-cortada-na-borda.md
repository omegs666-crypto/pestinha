# 2026-11-15 — Pílula cortada na borda da tela (menu flutuante "bugado")

## Causa
- `limitar_posicao` usava `PILULA_W = 380` fixo, mas a pílula alarga para até ~940 px quando o
  balão do narrador aparece. Com o balão aberto, ela podia ficar ~300 px para fora da borda
  direita: na tela aparecia só uma faixa escura com o orbe (o print do usuário). A posição
  salva `x=1520` comprovava o caso.
- `PILULA_W`, `PILULA_H` e `MARGEM_VISIVEL` foram removidos.

## Correção (`ui/web_island.py`)
- `limitar_posicao` agora recebe a `regiao` real que a página informa para a máscara de clique
  e garante que ela fique inteira dentro da tela (a janela transparente pode sair, o conteúdo não).
- `aplicar_regiao` guarda a região atual e, quando ela cresce (balão), reposiciona a janela na hora.
- Posição salva fora da tela também é corrigida na abertura.

## Testes
- `test_posicao_da_pilula_fica_dentro_da_tela` reescrito para a região;
  `test_posicao_limita_regiao_larga_do_balao` cobre o caso real medido (976 px de máscara).

## Correção 2 — a causa real do recorte (janela 100x30)
- Reproduzido na tela real: com `memory/web_posicao.json` existente, a janela abria com **100x30 px**
  em vez de 1040x620. `_posicionar` só chamava `move()` nesse caminho e nunca definia o tamanho
  (o `setGeometry` com o tamanho cheio só existia no caminho sem posição salva).
  Resultado: um retângulo escuro com só o orbe visível — o print do usuário.
- Correção: `setFixedSize(*JANELA)` antes de posicionar, em qualquer caminho.
- Verificado no harness real: janela 1040x620, máscara 1036x442 com a posição salva do usuário.
- Teste: `test_posicao_salva_mantem_o_tamanho_cheio_da_janela` (falha sem a correção).
