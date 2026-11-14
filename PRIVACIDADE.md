# Privacidade do Pestinha

O Pestinha roda só no seu computador. Ele não envia nada para a internet.

O chat local e a conversa por voz também usam serviços locais: o chat conecta
somente a `127.0.0.1:11434` e o reconhecimento/síntese usam o mecanismo de voz
do sistema ou um comando local. Nenhum áudio é enviado a serviços externos.

## O que ele lê

- O **nome** do programa em primeiro plano (por exemplo `code.exe`). Nunca o título nem o conteúdo da janela.
- Quanto tempo você está sem usar teclado ou mouse, e se o teclado ou o mouse foram usados agora.
- A posição do cursor, para saber se ele encostou na bolinha, se você está em cima do pet (carinho,
  cutucar) ou perto dele no cantinho do castigo.
- Se uma janela cobre a tela inteira (para não aparecer em jogos ou apresentações).
- A posição e o tamanho das janelas abertas, para ele poder pousar nas barras de título.
- O áudio que sai do computador (loopback), **somente depois que você clica em "Iniciar áudio"** na aba
  Música da ilha. Ele só calcula níveis e espectro para o visualizador: nada é gravado, guardado ou enviado.
- O microfone **somente enquanto você clica em "Falar"** na aba Chat local.
  No Windows, a transcrição usa o mecanismo `System.Speech` em português
  (`pt-BR`), dura até 12 segundos e não é gravada em arquivo.

Ele **não** lê o conteúdo nem o título de nenhuma janela, página, documento ou conversa.

## Chat local e voz

- Modelos são listados em `http://127.0.0.1:11434/v1/models`; prompts e respostas
  usam o serviço Ollama local em `127.0.0.1`. A integração ignora proxies do
  ambiente e recusa redirecionamentos para outros endereços.
- Se a variável `OLLAMA_API_KEY` existir, seu valor é enviado apenas ao servidor
  de loopback. A chave não é gravada nas permissões nem nos logs.
- A conversa e o texto transcrito ficam **somente na memória durante a sessão**.
  O botão **Analisar resultados** compartilha métricas resumidas e alguns logs
  recentes com o modelo local somente depois do seu clique.
- As respostas podem ser lidas em voz alta localmente quando você ativa
  **Ler respostas**. No Windows, a síntese usa `System.Speech`; no macOS/Linux,
  usa o sintetizador local disponível (`say`/`spd-say`). Entrada por microfone
  está disponível nesta implementação no Windows.

## O que ele grava

Tudo fica na pasta de dados, mostrada na tela de configurações. Ela é `memory/` ao lado do programa ou, no
executável do Windows, `%LOCALAPPDATA%\Pestinha` (a menos que já exista uma `memory/` ao lado dele). Abaixo,
`memory/` significa essa pasta. Desinstalar o programa não apaga esses dados.

Do app e seu, direto em `memory/`:

| Arquivo | Conteúdo |
|---|---|
| `permissions.json` | As opções que você escolheu |
| `timeline.csv` | Uma linha por minuto: hora, categoria de programa, trocas de janela, ocioso. Só com "Registrar minha rotina" ligado, que vem desligado. O pet ainda não usa esse histórico |
| `panels.json` | Posição dos painéis, do notebook e da placa |
| `web_layout.json` | Disposição dos widgets do aba Layout da ilha (só ids, tipos e posições) |
| `web_diagrama.json` | Fluxos de interação desenhados na aba Diagramas da ilha (diagrama livre) |
| `logs/pestinha.log` | Mensagens do programa e erros inesperados (sem conteúdo de janelas) |

De cada personagem, em `memory/pets/<pet>/` (um personagem não lê a memória do outro):

| Arquivo | Conteúdo |
|---|---|
| `nervous.json` | Estado da rede neural (habituação e aprendizado) |
| `episodes.jsonl`, `preferences.json` | Resultado de cada travessura e preferências aprendidas |
| `conditioning.json` | O que ele aprendeu a antecipar |
| `drives.json` | Energia, estimulação e carência |
| `protest.json`, `sad_protest.json` | Insatisfação e tristeza |
| `castigo.json` | Fugas do cantinho, rancor e receio |
| `convivencia.json` | Contagens do que você faz com ele (cutucadas, carinhos, dispensas, arremessos) e quais falas você respondeu. Não guarda texto seu nem conteúdo de janelas |
| `reacoes.json` | Reações que você configura na aba Diagramas (gatilho, falas e ações) e se as falas com IA local estão ligadas |
| `.migrado` | Só existe se a memória veio da versão antiga: quando migrou e o hash de cada arquivo |

Quem usou uma versão antiga (arquivos soltos em `memory/`) tem a memória migrada sozinha na primeira
abertura. Os originais não são apagados: ficam em `memory/legado/<pet>/`. Se a migração não puder ser
concluída (por exemplo, um arquivo já existe com outro conteúdo), nada é sobrescrito, ele continua usando
os arquivos antigos e avisa no ícone da bandeja.

## Como apagar

- Na tela de configurações, **Apagar histórico** apaga a rotina (`timeline.csv`), inclusive o minuto que
  ainda estava na memória.
- **Apagar todos os dados do Pestinha** apaga a pasta `memory/` inteira, com a memória de todos os personagens (pede confirmação, desliga o início com o Windows e fecha o programa). Se algum arquivo não puder ser apagado, ele avisa quais foram antes de fechar.
- Você também pode apagar a pasta `memory/` manualmente, com o programa fechado.

## Fora da pasta de dados

- **Abrir ao entrar no Windows** (desligado por padrão) grava uma entrada em
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, só para o seu usuário.
- Um arquivo de trava na pasta temporária do sistema impede abrir duas cópias. Não contém dados seus além do
  número do processo e do nome do computador.
- **Segundo cérebro (Obsidian)** (desligado por padrão): se você ligar e escolher a pasta do seu vault, o pet
  escreve em Markdown, dentro de `Pestinha/<pet>/`, o diário do dia (horário + categoria do evento, como
  "cutucada" ou "entrou no cantinho"), um resumo do que ele aprendeu e a ficha dele. Ele só escreve —
  nunca lê nada do vault — e nunca grava nome de programa nem título de janela. Para apagar, basta apagar
  a pasta `Pestinha/` dentro do vault; "Apagar todos os dados" não toca nela, porque ela é sua.

## Controle

- Cada permissão pode ser desligada na tela de configurações; desligar uma permissão também recolhe o que
  já estava na tela.
- O atalho **Ctrl + Alt + Shift + B** desliga tudo na hora, e ele continua desligado até você religar.
