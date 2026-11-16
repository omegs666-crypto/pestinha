# Mão na frente do persona + modo "um persona só"

## 1. Mão na frente
- `desenho_rosto.py`: `_bracos` dividido em `_bracos_membros` (ombro->cotovelo, desenhado
  ANTES da casca — o ombro continua escondido sob o corpo) e `_bracos_maos` (cápsula da mão,
  desenhada DEPOIS do rosto — a mão passa por cima do corpo nos gestos que sobem, como o carinho).
- `ilha.js`: mesma divisão — membros antes do corpo, mãos depois dos acessórios.

## 2. Modo "um persona só" (`ilha_solo`)
- `config.py`: nova permissão `ilha_solo` (padrão desligado) + texto na tela inicial.
- `index.html`/`ilha.js`: chave "Um persona só (mora na ilha)" na aba Controles.
- `web_bridge.py`: ação "solo" alterna a perm; sinal `solo_livre`; slot `mascote_liberar`;
  snapshot ganha `solo`, `solo_livre` e `emocao_chave` vira "dormindo" enquanto ele descansa
  (energia < WAKE_ABOVE).
- `app.py`:
  - `liberar_da_ilha()`: chamado quando você puxa o mascote para baixo (>60 px); o pet cai
    na tela a partir da posição da ilha. Cansado demais, ele recusa ("ainda tô cansado…").
  - `_solo_tick()` no think: fora de casa a energia gasta 8x mais rápido (SOLO_GASTO);
    abaixo de SOLO_CANSADO (0.4) ele anuncia "tô cansado… vou descansar na ilha" e volta voando.
  - Voo de volta no `frame()`: kinemático (body.held), ease-out até o centro da ilha;
    na chegada o pet some e o mascote reaparece com pulinho (gesto "voltou").
  - Descansando na ilha, `drives.update` conta como sono leve: a energia recarrega.
  - `_solo_perms()` no `apply_perms`: ligar o modo com ele na tela = ele volta voando;
    desligar = ele volta a ficar livre na tela normalmente.
- `sessao.py` (`update_visibility`): pet visível só se `_solo_livre` no modo solo;
  a ilha fica visível mesmo com o pet escondido dentro dela.

## Verificação
- pyflakes e node --check limpos; 31 testes focados passando; 3 testes novos
  (slot mascote_liberar, snapshot solo/solo_livre, ação "solo").
- SEM commit/push.
