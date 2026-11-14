# Auditoria QA — estabilidade da ilha, chat local e backend

## Escopo e método

Foi usada a análise local do Coucou em
`coucou-main/docs/ANALISE-COMPLETA.md` como referência de arquitetura e
comportamento. Nenhum arquivo-fonte do Coucou foi copiado; as correções abaixo
foram implementadas no Pestinha, preservando PySide6 e o backend existente.

Verificações executadas:

- Pyflakes no projeto (`pestinha`, `tests`, `main.py`, `ferramentas` e
  `conftest.py`).
- Suíte completa com Qt offscreen.
- Testes específicos de streaming/cancelamento, dimensões de MLP, raster do
  monitor, timers dos painéis e gravação concorrente do log.

## Bugs encontrados e correções

### 1. Chat local podia sair do loopback

`requests` respeitava proxies definidos no ambiente e seguia redirects por
padrão. Um serviço local redirecionado poderia expor o prompt/contexto.

**Correção:** a sessão Ollama desativa proxies do ambiente, recusa redirects e
fixa o destino em `127.0.0.1:11434`. O teste verifica essas condições.

### 2. Workers de chat sem cancelamento efetivo

Um stream bloqueado podia continuar ao esconder/fechar a ilha ou ao encerrar o
app; um pool de threads também poderia aguardar indefinidamente.

**Correção:** tasks daemon limitadas a duas simultâneas, evento de cancelamento,
fechamento do response ativo, timeout de leitura de 30 s e encerramento com
espera limitada a 750 ms. A ilha cancela o chat ao ser escondida/fechada e o
app cancela os workers antes de sair.

### 3. Streaming e histórico sem limites suficientes

Respostas longas podiam acumular texto, sinais Qt e blocos no documento do chat.

**Correção:** fragments são agrupados (32 caracteres ou 40 ms), respostas têm
limite de 16.000 caracteres, cada mensagem/contexto é limitado, o histórico
mantém no máximo 20 mensagens e o transcript visual no máximo 800 blocos.
Dados de log usados como contexto são limitados por linha e quantidade.

### 4. Gráfico/monitor vulneráveis a arrays inválidos

`np.stack` do raster e indexação de camadas poderiam falhar com dimensão ou
tipo inesperado. MLP aceitava entradas e alvos incompatíveis até a operação
matricial falhar.

**Correção:** MLP valida shapes 6D/N×6 e N×2, pesos, finitude, taxa e épocas;
interrompe treino entre épocas e impede publicar pesos não finitos. Monitor
valida vetores/rasters antes do `stack` e mostra fallback em caso de estado
inválido. O gráfico da MLP valida pesos, ativações e perdas.

### 5. Treino MLP executava na thread de interface

As 500 épocas do botão do Laboratório MLP rodavam síncronas no evento Qt.

**Correção:** treino agora usa uma cópia isolada da rede em worker; os pesos e
ativações só são publicados na thread UI após validação. O treino cancela entre
épocas e não permite dois treinos concorrentes.

### 6. Timers atualizavam painéis ocultos

Monitor neural, protesto e MLP mantinham timers ativos mesmo escondidos.

**Correção:** timers ligam em `showEvent` e param em `hideEvent`; no
encerramento, `FloatManager` interrompe workers e oculta os painéis.

### 7. Log concorrente e linhas em branco no Windows

Threads de voz/app podiam gravar simultaneamente; escrever `os.linesep` em
arquivo texto Windows passava pela conversão de newline e podia gerar linhas
vazias duplicadas (`CRCRLF`).

**Correção:** lock independente protege configuração e gravação do arquivo;
gravação usa `\n` para a conversão nativa única do modo texto. O buffer em
memória continua limitado a 120 entradas.

## Limite arquitetural identificado

O ciclo `PestinhaApp.think()` ainda é chamado pelo `QTimer` da thread Qt e
integra sentidos, rede neural, controladores e efeitos em widgets. Movê-lo
inteiro para um worker sem separar esses efeitos criaria corridas e acesso
inválido a `QWidget`. Esta auditoria isolou chamadas Ollama e treino MLP, mas
uma migração completa do cérebro pulsado requer uma fronteira de serviço e
snapshots/sinais próprios; não foi declarada como concluída.

## Verificação final

- `python -m pyflakes pestinha tests main.py ferramentas conftest.py`: sem
  apontamentos.
- `python -m pytest -q`: **445 passaram, 5 skipped**.
- A suíte emitiu um warning do ambiente atual: `requests 2.31.0` com
  `urllib3 2.6.1` e `chardet 7.4.3`; a integração não fez chamadas reais ao
  Ollama. `requirements.txt` agora exige `requests>=2.32.3` e `chardet<6` para
  evitar essa combinação; o ambiente instalado não foi atualizado por rede
  durante a auditoria.
