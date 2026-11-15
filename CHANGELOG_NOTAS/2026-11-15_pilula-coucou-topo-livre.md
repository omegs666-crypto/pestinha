# 2026-11-15 — Pílula no estilo do Coucou: encostada no topo, desgrudar e mascote

## O que mudou
- **Encostada no topo por padrão.** A cápsula preta fica colada na borda superior, centralizada,
  com cantos arredondados só embaixo (como a pílula do Coucou). `ui/web_island.py` (`posicao_topo`),
  `ui/web/ilha.css` (`.nucleo.topo`), `ui/web/ilha.js` (`aplicarModo`).
- **Desgrudar.** Puxar a barra para baixo (mais de 18 px, e mais para baixo que para o lado) solta a
  cápsula do topo: ela vira livre, com cantos completos e animação de soltura (`.soltando`).
  Antes de desgrudar, arrastar de lado não move nada.
- **Encaixar.** Livre e solta a até 24 px da borda de cima, ela volta a encostar no topo.
- **Modo salvo.** `memory/web_posicao.json` guarda `{"x","y","modo"}`. Arquivo antigo sem `modo`
  conta como livre (mantém a posição que você já tinha).
- **Mascote.** Rosto do pet desenhado em canvas (`#mascote`), porta fiel de `body/desenho_rosto.py`:
  moldura, tela, olhos pela emoção atual (`EYE_SHAPES`), piscada, olhar que segue o cursor, boca que
  se mexe enquanto o pet responde, gravata e óculos. Cores e formas vêm do Python pela ponte
  (`aparencia_pet`), sem duplicar a tabela. Clicar no rosto abre a ilha, como no orbe.
- **Orbe** continua ao lado do mascote, sem mudanças.
- **Visual:** o vidro da cápsula ficou preto (`--vidro`), como o Coucou.

## Ponte (`ui/web_bridge.py`)
- Sinais `desgrudou` e `modo_mudou`; slots `desgrudar`, `modo_inicial`, `aparencia_pet`.
- Snapshot ganha `emocao_chave` (a chave da emoção, usada pelo rosto).

## Testes
- Novos em `tests/test_web_island.py`: posição topo, desgrudar/encaixar, modo salvo, aparência
  e formas dos olhos pela ponte, emoção como chave.
- Teste de interação real (WebEngine, eventos de ponteiro na barra): topo → desgrudou (y 0 → 160)
  → encaixou de volta (y 0, modo topo gravado).

## Limitações
- O rosto em canvas é uma aproximação fiel, não idêntico em anti-aliasing. Ocupa 40×34 px.
- Os acessórios de óculos são desenhados, mas nenhum pet atual os usa.
- O mascote redesenha a 60 fps enquanto a página estiver aberta (canvas pequeno).
