# Braços orgânicos — sistema massa-mola (squash & stretch)

## Pedido
Os braços do Bryan estavam com movimento simples: quatro molas de posição X/Y
seguindo ondas. O usuário pediu animação orgânica baseada em Spring Mass System,
com rigidez (stiffness) e amortecimento (damping) ajustáveis, peso, inércia e
elasticidade (squash and stretch), dois estados (repouso com respiração senoidal
e gesticulação reagindo a impulsos/picos) e código comentado para ajuste futuro.

## O que mudou

### `pestinha/body/bracos.py` — reescrito
- Cada braço agora tem **quatro molas independentes**: posição X, posição Y,
  **rotação pendular** (graus) e **squash & stretch** (escala em torno de 1.0).
- **Rotação** não tem alvo próprio: seu target é alimentado pela velocidade do
  eixo X (`ganhoRot`), o que dá inclinação pendular natural ao se mover.
- **Squash** é alimentado pela energia de movimento (|vel.x| + |vel.y| ×
  `ganhoSq`, teto `sqMax`): quanto mais rápido o braço, mais ele deforma.
- **Impulsos de velocidade** (não de alvo) nos picos de gesto: a mola recebe um
  empurrão e a física resolve o arco — inércia de verdade, não teletransporte.
- **Repouso**: ondas senoidais com fases diferentes entre os braços
  (`idleFase`), para nunca balançarem em espelho.
- Todas as constantes ficam no dicionário `CFG`, com comentários explicando
  como ajustar rigidez (peso) e amortecimento (quica/seco).

### `pestinha/body/desenho_rosto.py`
- `Braco` ganhou campos `rot` e `squash`; seção de renderização comentada.
- Desenho em cadeia: translate (posição) → rotate (pêndulo, graus) →
  scale (squash vertical, já que o gesto dominante é no Y) → cápsula.
- A cápsula assimétrica original foi preservada (`lado*8-16` reproduz
  -24/-8) e a rotação/escala giram em torno do ponto de ancoragem.

### `pestinha/ui/web/ilha.js`
- Portado o mesmo modelo: `bracoB(lado)` com as 4 molas e `fisica()` que
  acopla rotação e squash às velocidades.
- `BRACO_CFG` espelha o `CFG` do Python, com comentários de ajuste.
- `ctx.rotate` recebe radianos (conversão `* PI/180` — Qt usa graus).

## Constantes para ajuste (`CFG` em bracos.py / `BRACO_CFG` em ilha.js)
- `rigPos`/`amoPos`: peso e atrito da posição (alto = braço duro/pesado).
- `rigRot`/`amoRot`: pêndulo da rotação (rigidez baixa = mole, oscila antes).
- `rigSq`/`amoSq`: velocidade e elasticidade do squash.
- `ganhoRot`/`ganhoSq`/`sqMax`: quanto rotação e deformação respondem.
- `idleAmp`/`idleFreq`/`idleFase`: amplitude, velocidade e assimetria da respiração.
- `falaAmp`/`ganhoBoca`: amplitude dos gestos e influência da boca.
- `impulsoP`/`impulsoX`/`impulsoY`/`impulsoAlcance`: frequência e força dos picos.

## Verificação
- Captura Qt: braços em posições/inclinações independentes, direito deformado
  por impulso manual (rot ~0.2°, squash 1.03–1.06, Y -10 e +5.4).
- `node --check` limpo; pyflakes limpo; suíte completa: 542 pass, 5 skip.

## Limitações
- O mascote usa `performance.now()` — a fase das ondas muda com a taxa de FPS,
  igual ao protótipo do usuário (não é dt fixo).
- Os impulsos de pico de fala são aleatórios (probabilidade por frame); ainda
  não há envelope de áudio real alimentando os gestos no mascote.
- Squash/estiramento é sutil em 200×200 px; aumente `ganhoSq`/`sqMax` para
  exagerar o efeito cartoon.
