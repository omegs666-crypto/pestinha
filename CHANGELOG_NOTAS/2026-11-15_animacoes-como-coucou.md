# 2026-11-15 — Animações da ilha com os valores do Coucou (adaptadas ao Pestinha)

## Escopo escolhido
- Estilo visual e animações/transições, adaptados ao nosso tema (Núcleo, Bryan/Jorge).
- Não copiamos personagem, ícones nem sons do Coucou: têm licença própria do autor.

## O que mudou (`pestinha/ui/web/ilha.js`, `ilha.css`)
- **Abrir:** mola com resposta de 0,5 s e amortecimento de 0,72 (valores de `core/anim.ts` do Coucou),
  implementada com as constantes K = ω² e C = 2ζω.
- **Fechar:** curva cúbica de 340 ms, com a mesma curva (.45, 0, .2, 1), sem balanço.
- **Botões (`.pilula`):** transição com o mesmo ritmo do Coucou (0,2 s, overshoot suave).

## Testes
- `tests/test_web_island.py` passa (20 testes); suíte completa com 540 testes e pyflakes limpo.

## Limitações
- Ajustei só os valores de movimento. Não reescrevi a estrutura de cards nem as cores.
- Conferi a suíte e a sintaxe; a sensação de movimento precisa ser avaliada com o mouse.
