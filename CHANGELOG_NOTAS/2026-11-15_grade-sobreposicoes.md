# 2026-11-15 — Grade: textos sobrepostos pelas animações

## Causas encontradas (reproduzidas com arraste real na grade)
- **Arrasto preso:** se o botão era solto fora da área visível da ilha (a janela tem máscara de clique),
  o soltar se perdia. O widget ficava "em arrasto": o contorno de encaixe (a barra ciano) e a rejilla
  continuavam aparecendo e os widgets vizinhos ficavam sobrepostos às letras.
- **Número do anel:** o "43%" passava da borda do arco quando o widget era menor (tamanho fixo em px).
- **Vazamento na transição:** o conteúdo saía da caixa do widget enquanto ele mudava de tamanho.
- **Alça:** o tirador de redimensionar encostava no texto da última linha.

## O que mudou
- `moxen/parrilla/parrilla.js`: um movimento com o botão solto (`buttons === 0`) encerra o arrasto.
- `moxen/parrilla/parrilla.css`: o número do anel usa a escala do widget (`cqmin`), o arco ficou mais
  fino (9 px); `.pa-w` corta o conteúdo que excede a caixa; `.pa-cuerpo-w` reserva espaço para a alça.

## Testes
- `test_grade_termina_arrasto_quando_o_soltar_se_perde`: arrasto preso é encerrado no próximo movimento.
- Renderização conferida em repouso, arrastando e logo após soltar.

## Limitações
- O reflexo da barra ciano observado no print foi atribuído ao arrasto preso (pela reprodução e pela
  máscara da janela); não consegui reproduzir o mesmo frame exato com o mouse físico.
