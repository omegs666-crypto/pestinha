# 2026-11-15 — Laboratório MLP funcional

## O que estava estático
- Um único exemplo fixo (`X_DEMO`/`Y_DEMO`) e nenhuma entrada do usuário.
- Os neurônios usavam `_ativ`, que só existia depois de um treino: antes disso, o desenho era vazio.
- O treino rodava 500 épocas e só então atualizava a tela; o botão ficava desabilitado e não havia progresso.
- A curva de perda não tinha referências e a rede nunca era recalculada com as entradas.

## O que mudou (`pestinha/ui/lab_mlp.py`)
- **Entradas e alvos em sliders** (x1–x6, y1–y2). A rede responde a cada mudança (`forward`): os neurônios
  de entrada, ocultos e de saída acendem com as ativações reais; a saída aparece com o alvo ao lado.
- **Treino em segundo plano com progresso:** o worker emite o estado a cada 5 épocas; pesos, perda e
  neurônios se atualizam enquanto a rede aprende.
- **Pausar** guarda o ponto alcançado (e Treinar continua dele). **Reiniciar pesos** volta à rede inicial
  (só quando não há treino rodando).
- **Curva de perda** com valor atual e máximo/mínimo.
- `core/mlp.py` não mudou: o painel usa `forward`, `backward`, `mse` e a cache do forward.

## Testes
- `tests/test_lab_mlp.py` (5): a saída reage à entrada; treino emite progresso e reduz a perda; pausa mantém
  o ponto; reiniciar volta aos pesos iniciais; pesos com forma errada são recusados.
- `tests/test_paineis.py`: removido o timer de atualização (o painel agora atualiza pelos sinais do treino)
  e o teste de treino passou a checar o estado Pausar/Treinar durante o treino.
- Verificado com treino real pela thread pool: 500 épocas, perda 0,1621 → 0,000043, botões voltam ao estado normal.

## Limitações
- Os alvos são escolhidos a mão; a rede não aprende com dados do pet (isso seria uma etapa à parte).
- Textos secundários do painel usam a cor de texto do tema; contraste ainda pode ser ajustado.
