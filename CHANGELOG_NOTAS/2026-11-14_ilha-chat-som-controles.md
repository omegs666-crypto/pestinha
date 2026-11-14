# 2026-11-14 — Ilha: chat, pílula, som e controles

## O que mudou

### Chat: seletor de modelo próprio
- O `<select>` nativo abria uma janela do sistema, que ficava fora da ilha: ao passar o mouse nela,
  a ilha recolhia e o menu sumia. Agora a escolha é uma lista dentro da própria ilha.
- A lista só fecha ao escolher um modelo ou ao clicar fora. Modelos de nuvem aparecem em âmbar
  com "(nuvem)".
- O `<select>` oculto continua sendo a fonte da verdade, então nada do envio mudou.

### Pílula (guia: primeiro commit)
- Abre com o mouse após 260 ms, como antes.
- Ao sair, uma barra fina na base encolhe mostrando o tempo até recolher. Entrar de novo cancela.
- **Fixar** mantém aberta; soltar o fixar com o mouse fora começa a contagem.
- Tempo de recolher de 1 a 10 s, ajustável em Controles (guardado no navegador da ilha).
- Clicar no balão de fala abre a ilha.
- Não recolhe enquanto a lista de modelos está aberta, o chat responde ou o campo tem foco.

### Vidro e desfoque
- Painéis mais opacos (fundo 93%, cartões 88%), com `backdrop-filter` nos cartões: o que está
  atrás deles dentro da ilha fica desfocado.
- **Limite:** não há desfoque do desktop atrás da ilha. Testei o acrílico do Windows
  (`SetWindowCompositionAttribute`): com WebEngine, a janela vira um retângulo escuro opaco e
  perde a máscara de clique. Não foi usado.

### Som do sistema (estilo Grabadora)
- Layout de gravador: estado com ponto que pulsa, medidor de LEDs, cronômetro grande, onda no canvas,
  botão central com anéis (vira um quadrado ao escutar), "Marcar" (tecla M ou clique na onda) e
  "Limpar".
- Painel lateral **Momentos**: cada marca com horário e pico. Some quando você limpa.
- A onda, o espectro radial e o campo de pontos continuam. O áudio segue só analisado, nunca gravado.

### Controles (nativo; Centro Moxen removido)
- **Pet agora**: emoção e barras de energia, estímulo e insatisfação.
- **Interruptores** (ligados ao backend): pausar, voz, travessuras, modo avião e narrador.
- **Janela**: tempo de recolher, Fixar e atalhos para Monitor neural, Laboratório MLP e Painel de protesto.
- Removidos: `pestinha/ui/web/moxen/centro/` e a referência no `LICENCAS.md`. O Grabadora serviu só
  de referência de layout; o código foi escrito do zero.

## Arquivos
- Alterados: `pestinha/ui/web/index.html`, `ilha.js`, `ilha.css`, `LICENCAS.md`,
  `tests/test_web_island.py` (2 quadros em vez de 3).
- Removidos: `pestinha/ui/web/moxen/centro/` (4 arquivos).

## Testes
- Suíte completa: **503 passed, 5 skipped**. Pyflakes limpo. `node --check` no JS.
- Capturas da interface renderizada: lista de modelos (com um de nuvem), aba Som com marcas e
  cronômetro, aba Controles, e barra de contagem para recolher. Escolha de modelo verificada por
  script: o valor muda e a lista fecha.

## Limitações
- O hover real com o mouse não foi automatizado; a contagem foi verificada pelo método de
  depuração (`nucleoDebug.agendar`).
- Sem desfoque real do desktop (ver acima).
