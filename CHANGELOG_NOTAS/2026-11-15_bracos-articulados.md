# Braços articulados — elo ombro→cotovelo→mão (adeus "dois pontos")

## Problema relatado
O usuário via apenas "2 pontos simulando braços", estáticos e parecendo uma
sobrancelha. Causa: o mascote da ilha desenha o corpo em escala 0.28, então
a cápsula de 32×20 virava ~9×5 px e a respiração de 2 unidades virava meio
pixel — movimento invisível e silhueta ilegível.

## O que mudou

### Desenho (Qt + ilha): braço articulado em vez de cápsula solta
- `desenho_rosto.py::_bracos`: ombro fixo na lateral do corpo (escondido sob
  a casca, braços desenham antes dela), membro em curva quadrática
  ombro→cotovelo→mão em duas passadas (contorno neon largo + metal fino),
  e a mão cápsula no fim com rotação pendular e squash & stretch.
- `ilha.js`: mesmo desenho no canvas do mascote; multiplicador `exag: 1.6`
  no deslocamento da mão para o gesto ser legível na escala 0.28.
- Âncora da mão ±64 (antes ±72): com o elo preso, a mão pode ficar mais
  perto sem perder o balanço — e não raspa a borda de 200 px no impulso.

### Movimento sempre visível
- `bracos.py`: `IDLE_AMP_Y` de 2→4 e nova `IDLE_SWAY` (deriva lateral lenta
  senoidal): mesmo "parado", o braço nunca congela.
- `ilha.js`: `idleAmp` 2→4, `idleSway` 1.8 (espelha o Python).

## Verificação
- Capturas Qt: elo visível saindo da lateral, mão levantada no feliz,
  punhos colados no bravo.
- Capturas da pílula real (QWebEngineView): braços legíveis como braços —
  triste caído, assustado levantado e aberto, feliz/bravo com o cotovelo
  dobrado. A emoção flui pela ponte (`emocao_chave`).
- `node --check` limpo, pyflakes limpo, suíte: 542 pass, 5 skip.

## Limitações
- O gesto "cut cut" do feliz e o tremor do bravo são cíclicos — num frame
  parado a pose muda; avaliar o movimento pede ver o app ao vivo.
- `exag` só amplifica a posição da mão no mascote (não a rotação/squash).
