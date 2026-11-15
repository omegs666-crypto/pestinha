# 2026-11-15 — Vibração do áudio no chat local

## O que foi feito
- Copiei a linguagem visual da aba "Som do sistema" para o chat: onda em barras, medidor de LEDs e
  cronômetro (`ui/web/index.html`, `ui/web/ilha.css`, `ui/web/ilha.js` → `vibra`).
- A onda rola da direita para a esquerda. Cada token da resposta da LLM dá um pulso; enquanto a
  resposta é escrita, mostra "Escrevendo a resposta…".
- Quando o modelo fala (voz do LLM), a onda segue o volume real da fala: o Python calcula o envelope
  do WAV (`sense/envelope.py`) antes de tocar e envia à interface (`ponte.envelope`).
- Só desenha enquanto o chat está visível; fora dele não consome quadros.

## Testes
- `tests/test_envelope.py` (4): envelope acompanha o volume, mistura canais, aceita 8 bits, rejeita o
  que não é WAV, silêncio dá zeros.
- Captura real: onda, LEDs, cronômetro e estado "Falando · voz do modelo" conferidos na tela.

## Limitações
- A voz do sistema (fallback) não tem WAV, então não gera envelope; a onda fica só com os pulsos dos tokens.
- A sincronização tem um atraso de até ~0,3 s, porque o áudio começa no PowerShell depois do envelope.
