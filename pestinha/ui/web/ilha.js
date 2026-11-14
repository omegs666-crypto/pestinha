/* Ilha em HTML: controla as abas, a expansão por hover/clique e a ponte com o backend Python.
   O trabalho pesado (Ollama, áudio, persistência) fica em workers no lado Python. */
(function () {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const ilha = $('#ilha');
  const ESPERA_RECOLHER_MS = 700;
  const MAX_HISTORICO = 20;
  const MAX_CONTEXTO_LOGS = 12;
  const PROMPT_SISTEMA = 'Você é o assistente técnico deste dashboard. Analise os seguintes dados do sistema e dê um diagnóstico rápido: ';

  let ponte = null, estado = {}, aberta = false, fixada = false, timerSair = null, timerTroca = null;
  let audioAtivo = false, bandas = new Array(24).fill(0), rms = 0, pico = 0;
  let historico = [], modelos = [], respondendo = false, bolhaAtual = null, textoAtual = '';

  // ----- expansão -----
  function definirAberta(valor) {
    if (valor === aberta) return;
    aberta = valor;
    clearTimeout(timerTroca);
    if (valor) {
      ilha.dataset.estado = 'aberta';
    } else {
      timerTroca = setTimeout(() => { ilha.dataset.estado = 'compacta'; }, 280);
    }
    if (ponte) ponte.expandir(valor);
  }

  $('#compacta').addEventListener('mouseenter', () => { clearTimeout(timerSair); definirAberta(true); });
  $('#compacta').addEventListener('click', () => definirAberta(true));
  ilha.addEventListener('mouseenter', () => clearTimeout(timerSair));
  ilha.addEventListener('mouseleave', () => {
    if (fixada || !aberta) return;
    clearTimeout(timerSair);
    timerSair = setTimeout(() => definirAberta(false), ESPERA_RECOLHER_MS);
  });
  $('#fixar').addEventListener('click', () => {
    fixada = !fixada;
    $('#fixar').classList.toggle('ativo', fixada);
  });
  $('#fechar').addEventListener('click', () => { fixada = false; definirAberta(false); });

  // ----- abas e quadros (Moxen carregam só quando abertos) -----
  function ativarAba(nome) {
    document.querySelectorAll('[data-aba]').forEach(b => b.classList.toggle('ativa', b.dataset.aba === nome));
    document.querySelectorAll('[data-secao]').forEach(s => s.classList.toggle('oculta', s.dataset.secao !== nome));
    const quadro = document.querySelector(`[data-secao="${nome}"] iframe`);
    if (quadro && !quadro.src) {
      quadro.addEventListener('load', () => enviarInicio(quadro), { once: true });
      quadro.src = quadro.dataset.src;
    }
    if (nome === 'chat' && !modelos.length && ponte) ponte.listar_modelos();
    if (nome === 'musica') desenharEspectro();
  }
  document.querySelectorAll('[data-aba]').forEach(b => b.addEventListener('click', () => ativarAba(b.dataset.aba)));

  function enviar(quadro, dados) {
    if (quadro && quadro.contentWindow) quadro.contentWindow.postMessage(dados, '*');
  }

  function enviarInicio(quadro) {
    if (!ponte) return;
    const tipo = quadro.dataset.quadro;
    if (tipo === 'parrilla') {
      ponte.carregar('layout', t => enviar(quadro, { tipo: 'init', layout: t ? JSON.parse(t) : null }));
    } else if (tipo === 'eslabon') {
      ponte.carregar('diagrama', t => { const d = t ? JSON.parse(t) : {}; enviar(quadro, { tipo: 'init', flujo: d.flujo || null }); });
    }
    enviarMetricas();
  }

  // Quadros recebem mensagens: salvar layout/diagrama e ações do painel.
  window.addEventListener('message', ev => {
    const d = ev.data || {};
    const quadro = [...document.querySelectorAll('iframe')].find(f => f.contentWindow === ev.source);
    if (!quadro || !ponte) return;
    if (d.tipo === 'salvar') {
      clearTimeout(quadro._salvar);
      quadro._salvar = setTimeout(() => ponte.salvar(d.nome, d.dados), 350);
    } else if (d.tipo === 'acao') {
      ponte.acao(d.nome, !!d.valor);
    }
  });

  // ----- métricas e áudio para os quadros -----
  function enviarMetricas() {
    const e = estado;
    const dados = {
      energia: `${e.energia ?? 0}%`, atividade: `${e.atividade ?? 0}%`, estimulo: e.estimulacao ?? 0,
      energia_pct: `${e.energia ?? 0}%`, insatisfacao_pct: `${e.insatisfacao ?? 0}%`, atividade_pct: `${e.atividade ?? 0}%`,
      estimulo_pct: `${e.estimulacao ?? 0}%`, logs: e.logs || [],
    };
    document.querySelectorAll('iframe[data-quadro="parrilla"]').forEach(f => enviar(f, { tipo: 'metricas', dados }));
  }

  function enviarNiveis() {
    document.querySelectorAll('iframe[data-quadro="centro"]').forEach(f =>
      enviar(f, { tipo: 'niveis', bandas, ativo: audioAtivo, taxa: 48000 }));
  }

  // ----- estado do backend -----
  function aplicarEstado(e) {
    estado = e || {};
    $('#nome').textContent = estado.pet || 'Pestinha';
    $('#emocao').textContent = estado.emocao || '—';
    $('#ponto').classList.toggle('pausado', !!estado.pausado);
    enviarMetricas();
  }

  function relogio() {
    const agora = new Date();
    $('#relogio').textContent = agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  }
  setInterval(relogio, 1000);
  relogio();

  // ----- espectro (canvas, redesenhado no quadro de animação) -----
  const canvas = $('#espectro');
  const ctx = canvas.getContext('2d');
  let quadroPendente = false;

  function desenharEspectro() {
    if (quadroPendente) return;
    quadroPendente = true;
    requestAnimationFrame(() => {
      quadroPendente = false;
      if (!$('[data-secao="musica"]') || $('[data-secao="musica"]').classList.contains('oculta')) return;
      const largura = canvas.clientWidth, altura = canvas.clientHeight;
      if (canvas.width !== largura * devicePixelRatio) {
        canvas.width = largura * devicePixelRatio;
        canvas.height = altura * devicePixelRatio;
      }
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      ctx.clearRect(0, 0, largura, altura);
      const n = bandas.length, gap = 4, barra = (largura - gap * (n - 1)) / n;
      const grad = ctx.createLinearGradient(0, altura, 0, 0);
      grad.addColorStop(0, '#3b82f6'); grad.addColorStop(1, '#22d3ee');
      ctx.fillStyle = grad;
      bandas.forEach((v, i) => {
        const h = Math.max(3, v * (altura - 16));
        const x = i * (barra + gap), y = altura - h - 8;
        ctx.beginPath();
        ctx.roundRect(x, y, barra, h, 4);
        ctx.fill();
      });
      $('#rms').textContent = rms.toFixed(3);
      $('#pico').textContent = pico.toFixed(3);
    });
  }

  function aoReceberNiveis(d) {
    bandas = Array.isArray(d.bandas) ? d.bandas : bandas;
    rms = Number(d.rms) || 0;
    pico = Number(d.pico) || 0;
    enviarNiveis();
    if (!$('[data-secao="musica"]').classList.contains('oculta')) desenharEspectro();
  }

  $('#musica-botao').addEventListener('click', () => { if (ponte) ponte.audio(!audioAtivo); });

  function aoEstadoAudio(texto) {
    if (texto === 'ativo' || texto === 'parado') {
      audioAtivo = texto === 'ativo';
      $('#musica-estado').textContent = audioAtivo ? 'Captura ao vivo · loopback do sistema' : 'Captura parada';
      $('#musica-botao').textContent = audioAtivo ? 'Parar áudio' : 'Iniciar áudio';
      if (!audioAtivo) { bandas = new Array(24).fill(0); rms = 0; pico = 0; desenharEspectro(); }
      enviarNiveis();
    } else {
      audioAtivo = false;
      $('#musica-estado').textContent = texto;
      $('#musica-botao').textContent = 'Iniciar áudio';
    }
  }

  // ----- chat local -----
  const mensagens = $('#mensagens');
  const entrada = $('#entrada');

  // Avisos de conexão ficam visíveis até o Ollama voltar; os demais somem sozinhos.
  function mostrarErro(texto, persistente = false) {
    const caixa = $('#erro');
    caixa.textContent = texto;
    caixa.hidden = false;
    clearTimeout(caixa._t);
    if (!persistente) caixa._t = setTimeout(() => { caixa.hidden = true; }, 7000);
  }

  function bolha(papel, texto) {
    const el = document.createElement('div');
    el.className = 'bolha ' + papel;
    el.textContent = texto;
    mensagens.appendChild(el);
    mensagens.scrollTop = mensagens.scrollHeight;
    return el;
  }

  function vozDoModelo(modelo) {
    return modelos.find(m => /tts|kokoro|piper|speech|f5-|chattts/i.test(m)) || modelo;
  }

  function setOcupado(valor) {
    respondendo = valor;
    $('#enviar').disabled = valor;
    $('#analisar').disabled = valor;
    $('#parar').hidden = !valor;
  }

  function enviarChat(texto, exibido) {
    const modelo = $('#modelo').value;
    if (!ponte || respondendo) return;
    if (!modelo) { mostrarErro('Nenhum modelo local selecionado. Atualize a lista com o Ollama aberto.'); return; }
    bolha('usuario', exibido || texto);
    historico.push({ role: 'user', content: texto });
    historico = historico.slice(-MAX_HISTORICO);
    bolhaAtual = bolha('assistente', '…');
    textoAtual = '';
    setOcupado(true);
    ponte.enviar_chat(modelo, JSON.stringify(historico));
  }

  function enviarPelaCaixa() {
    const texto = entrada.value.trim();
    if (!texto) return;
    entrada.value = '';
    enviarChat(texto);
  }

  $('#enviar').addEventListener('click', enviarPelaCaixa);
  entrada.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); enviarPelaCaixa(); } });
  $('#parar').addEventListener('click', () => { if (ponte) ponte.cancelar_chat(); });
  $('#atualizar').addEventListener('click', () => { if (ponte) ponte.listar_modelos(); });
  $('#analisar').addEventListener('click', () => {
    const contexto = { metricas: { energia: estado.energia, estimulacao: estado.estimulacao, insatisfacao: estado.insatisfacao, atividade: estado.atividade, emocao: estado.emocao, pausado: estado.pausado }, logs_recentes: (estado.logs || []).slice(-MAX_CONTEXTO_LOGS) };
    enviarChat(PROMPT_SISTEMA + JSON.stringify(contexto, null, 1), 'Analisar resultados do projeto');
  });
  $('#ouvir').addEventListener('click', () => { if (ponte) ponte.ouvir(); });
  $('#modelo').addEventListener('change', e => localStorage.setItem('pestinha.modelo', e.target.value));
  $('#ler').addEventListener('change', e => { if (e.target.checked) mostrarErro('Leitura em voz alta ativa: a resposta será falada com o modelo local.'); });

  function aoModelos(lista) {
    modelos = Array.isArray(lista) ? lista : [];
    const sel = $('#modelo'), salvo = localStorage.getItem('pestinha.modelo');
    sel.innerHTML = '';
    modelos.forEach(m => { const o = document.createElement('option'); o.value = m; o.textContent = m; sel.appendChild(o); });
    if (salvo && modelos.includes(salvo)) sel.value = salvo;
    sel.disabled = !modelos.length;
    if (modelos.length) $('#erro').hidden = true;
    else mostrarErro('Nenhum modelo instalado encontrado no Ollama local.', true);
  }

  function aoToken(t) {
    if (!bolhaAtual) return;
    textoAtual += t;
    bolhaAtual.textContent = textoAtual;
    mensagens.scrollTop = mensagens.scrollHeight;
  }

  function aoFim() {
    if (bolhaAtual && textoAtual) {
      historico.push({ role: 'assistant', content: textoAtual });
      historico = historico.slice(-MAX_HISTORICO);
      if ($('#ler').checked && ponte) ponte.falar_resposta(vozDoModelo($('#modelo').value), textoAtual);
    } else if (bolhaAtual && !textoAtual) {
      bolhaAtual.remove();
    }
    bolhaAtual = null;
    setOcupado(false);
  }

  function aoErro(texto) {
    mostrarErro(texto, /desconectad/i.test(texto));
    if (respondendo && bolhaAtual && !textoAtual) { bolhaAtual.remove(); bolhaAtual = null; }
  }

  // ----- ligação com o backend (QWebChannel) -----
  if (window.QWebChannel && window.qt) {
    new QWebChannel(qt.webChannelTransport, canal => {
      ponte = canal.objects.ponte;
      ponte.estado.connect(s => aplicarEstado(JSON.parse(s)));
      ponte.niveis.connect(s => aoReceberNiveis(JSON.parse(s)));
      ponte.audio_estado.connect(aoEstadoAudio);
      ponte.modelos.connect(s => aoModelos(JSON.parse(s)));
      ponte.token.connect(aoToken);
      ponte.chat_fim.connect(aoFim);
      ponte.erro.connect(aoErro);
      ponte.transcrito.connect(texto => { entrada.value = texto; enviarPelaCaixa(); });
      ponte.voz_estado.connect(estadoVoz => { $('#ouvir').textContent = estadoVoz === 'ouvindo' ? 'Parar' : 'Falar'; });
      ponte.obter_estado(s => aplicarEstado(JSON.parse(s)));
      ponte.listar_modelos();
    });
  } else {
    mostrarErro('Ponte com o Python indisponível.');
  }

  ativarAba('painel');
})();
