# Braços gesticulam por emoção

## Pedido
A gesticulação estava tímida, e o usuário queria gestos característicos por
emoção: feliz faz "cut cut" (cutucadas), bravo gesticula com raiva. Pediu
também para subir o git antes — feito (13 commits, `12a229d..fdeb129`).

## O que mudou

### `pestinha/body/bracos.py`
- `passo(falando, boca, emocao)`: novo parâmetro `emocao` (padrão
  "observando", compatível com chamadas antigas).
- **`EMOCAO_ENERGIA`**: multiplica amplitude e chance de impulsos na fala
  (bravo 1.5, feliz 1.3, triste 0.4, dormindo 0.1...).
- **`_repouso(emocao, t)`**: cada emoção tem gesto próprio no repouso:
  - feliz → "cut cut": cutucada rápida para o ar, braços alternados
    (janela de 30% por meio-ciclo a 1.6 Hz)
  - bravo → punhos fechados (+6px para dentro) tremendo a 32 rad/s
  - triste → braços caídos +9px, respiração lenta
  - dormindo → largados +11px, quase parados
  - assustado → para cima e abertos, tremidinha fina
  - curioso → um braço aponta e troca de lado devagar
  - dramatico → varreduras amplas em oposição
  - observando/contente → respiração (contente com amplitude maior)
- Amplitude da fala subiu de 10 para 14 e `IMPULSO_P` de 0.05 para 0.08 —
  a gesticulação estava difícil de perceber.
- Todas as constantes comentadas na seção 3 para ajuste.

### `pestinha/app.py`
- O tick passa a `emotion` atual para `st.bracos.passo(...)`.

### `pestinha/ui/web/ilha.js`
- `BRACO_CFG` ganhou as mesmas constantes e a tabela `energia` por emoção.
- O repouso do mascote espelha `_repouso` (o `emocao` já chega pela ponte
  via `mascote.definirEmocao`).

## Verificação
- Capturas Qt: feliz (braço esquerdo na cutucada), bravo (punhos colados
  e elevados), triste (braços caídos) — poses distintas e legíveis.
- `node --check` limpo, pyflakes limpo, suíte completa: 542 pass, 5 skip.

## Limitações
- O mascote usa `performance.now()` em segundos agora (era por-ms); a
  frequência dos gestos ficou idêntica à do pet Qt.
- Os impulsos de pico de fala seguem aleatórios — ligar o envelope de
  áudio real aos braços é uma etapa futura possível.
