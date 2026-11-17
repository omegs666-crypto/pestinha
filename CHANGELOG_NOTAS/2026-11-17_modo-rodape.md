# 2026-11-17 — Modo rodapé: a mini-faixa "escondida" do Coucou

## Pedido

O Coucou tem um modo "escondido" que não some de verdade: vira uma faixa bem
pequena colada no rodapé da tela. Implementar o mesmo na ilha.

## Como funciona

Terceiro modo da ilha, além de `topo` e `livre`:

- **Entrar**: no modo livre, arraste a ilha para perto da borda de baixo da tela
  (24 px da área disponível, acima da barra de tarefas) e solte — ela encaixa
  no rodapé, centralizada, e **encolhe** numa mini-faixa de 250×32.
- **Na mini-faixa**: Bryan, orbe e Jorge encolhidos lado a lado; data e hora
  somem; o balão do narrador continua funcionando (alarga a faixa quando fala).
- **Abrir**: clicar no orbe/balão abre a ilha inteira **ancorada na base** —
  ela cresce para cima como um dock.
- **Sair**: segure a faixa e **puxe para cima** — ela desgruda e vira livre
  (espelho do gesto do topo, que pede puxada para baixo).
- **Posição persiste** em `web_posicao.json` (`modo: "rodape"`), como os outros.

## Mudanças

- **`web_island.py`**: `posicao_rodape()` (base da `availableGeometry`, acima da
  barra de tarefas); `_encaixar_rodape()`; `ao_soltar` detecta o encaixe de baixo;
  `mover_por` desliza na horizontal nos modos ancorados (`topo`+`rodape`);
  `desgrudar` compensa a âncora (o núcleo sai da base da janela para o topo,
  ficando sob o cursor); `aplicar_regiao` recola a base quando a região muda;
  persistência aceita `"rodape"`; ao restaurar posição salva, `ponte.modo`
  recebe o modo correto (antes voltava "topo" mesmo em livre — bug).
- **`ilha.js`**: `TAM.rodape` (250×32); `aplicarModo` agora recebe a string do
  modo (topo/livre/rodape) com classe `.rodape`; `informarRegiao` reporta a
  região na **base** da janela quando em rodapé; `tamanhoAtual` usa a mini-faixa
  recolhida; o gesto de desgrudar usa `puxada = modoTopo ? ty : -ty` (para cima
  no rodapé); cantos arredondados só em cima (`r r 0 0`), espelho do topo.
- **`ilha.css`**: `.nucleo.rodape` ancorada em `bottom: 0`; regras
  `.rodape:not(.aberto)` encolhem barra (32 px), mascote (34×24), orbe (22),
  Jorge (22×25) e escondem data/hora.
- **`index.html`**: cache-buster `?v=2026-11-17a`.

## Testes

- `test_web_island.py`: 29 passam.
- Captura validada: faixa no rodapé da janela com Bryan | orbe | Jorge | balão.

## Não feito (pedido separado)

"Dinâmica do HUD completo mais controlável / menos separado" — fase posterior.
