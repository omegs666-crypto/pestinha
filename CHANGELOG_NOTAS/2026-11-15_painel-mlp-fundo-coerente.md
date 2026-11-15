# 2026-11-15 — Painel do Laboratório MLP: fundo opaco e coerência visual

## Problema
- O Laboratório MLP era um painel flutuante sem fundo: o jogo e o site apareciam por trás dos controles.
  Os outros painéis (monitor neural, protesto) pintam um cartão escuro arredondado; este não pintava.
- Os rótulos e textos usavam tamanhos e famílias de fonte soltos, diferentes do resto.
- Não havia título: o painel começava direto nos desenhos.

## Mudanças (`pestinha/ui/lab_mlp.py`)
- `LabMLP.paintEvent` pinta o cartão escuro arredondado (`tema.fundo_arredondado`, raio 16), igual ao monitor.
- Cabeçalho "Laboratório MLP" com subtítulo da arquitetura, no mesmo tipo de título do tema.
- Todos os rótulos usam a família `tema.FONTE`.

## Testes
- `test_painel_tem_fundo_opaco_escuro_como_os_outros`: o miolo é opaco e escuro; o canto fica vazado.

## Limitações
- Não revisei o contraste dos painéis de Diagramas e Monitor neural nesta rodada; o tema comum já é o mesmo.
