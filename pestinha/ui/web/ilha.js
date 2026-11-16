/* Núcleo — motor da interface do Pestinha.
   · Molas físicas (não curvas fixas) para abrir, recolher e alargar o balão.
   · Orbe neural em canvas com humores: calmo, processando, pensando, alerta, som e pausado.
   · Narrador: balões curtos vindos das regras locais e do Ollama (pela ponte).
   · Cards no estilo widgets: arrastáveis com inércia, inclinação 3D e brilho que segue o cursor.
   Tudo o que é pesado (Ollama, áudio, persistência) roda em threads do lado Python. */
(function () {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const lim = (v, a, b) => Math.max(a, Math.min(b, v));
  const DPR = () => window.devicePixelRatio || 1;
  // o bitmap acompanha largura E altura do elemento; senão o desenho estica (orbes viram elipses)
  const ajustarCanvas = (c, w, h) => {
    const bw = Math.round(w * DPR()), bh = Math.round(h * DPR());
    if (c.width !== bw || c.height !== bh) { c.width = bw; c.height = bh; }
  };
  const nucleo = $('#nucleo');

  const TAM = {
    compacta: { w: 380, h: 46, r: 23 },
    home: { w: 1000, h: 480, r: 30 },
    grande: { w: 1000, h: 594, r: 30 },
  };
  const VISTAS_GRANDES = new Set(['som', 'painel', 'grade', 'fluxos', 'chat']);
  const HUMORES = {
    calmo: ['#45e6ff', '#7c6bff'],
    processando: ['#4dffb0', '#45a3ff'],
    pensando: ['#b07bff', '#ff6bd6'],
    alerta: ['#ffb547', '#ff5a6e'],
    pausado: ['#8a90a6', '#4b5066'],
  };
  const PROMPT_ANALISE = 'Você é o assistente técnico deste dashboard. Analise os seguintes dados do sistema e dê um diagnóstico rápido: ';
  const MAX_HISTORICO = 20;

  let ponte = null;
  let modoTopo = true;                    // encostada no topo da tela (false: livre, arrastável)
  const DESGRUDAR_PX = 14;                // puxar este tanto para baixo a solta do topo
  let estado = {};
  let aberta = false, fixada = false, vista = 'home';
  let timerAbrir = null, timerFechar = null;
  let audioAtivo = false, bandas = new Array(24).fill(0), rms = 0, pico = 0;
  let pensandoNarrador = false, alertaAte = 0;
  let historico = [], modelos = [], respondendo = false, bolhaAtual = null, textoAtual = '';

  /* ======================= mola física do corpo ======================= */
  const mola = { w: TAM.compacta.w, h: TAM.compacta.h, r: TAM.compacta.r, vw: 0, vh: 0, vr: 0, alvo: { ...TAM.compacta }, rodando: false };

  function aplicarForma() {
    nucleo.style.width = mola.w.toFixed(1) + 'px';
    nucleo.style.height = mola.h.toFixed(1) + 'px';
    const r = mola.r.toFixed(1) + 'px';
    nucleo.style.borderRadius = modoTopo ? `0 0 ${r} ${r}` : r;   // no topo, só as bordas de baixo são arredondadas
  }

  function aplicarModo(topo) {
    modoTopo = topo;
    nucleo.classList.toggle('topo', topo);
    nucleo.classList.toggle('livre', !topo);
    aplicarForma();
    informarRegiao(mola.w, mola.h);
  }

  function informarRegiao(w, h) {
    if (!ponte) return;
    const margem = 18, largura = document.documentElement.clientWidth;
    const x = (largura - w) / 2 - margem;
    ponte.definir_regiao(Math.round(x), 0, Math.round(w + margem * 2), Math.round(h + 6 + margem * 2));
  }

  // Valores do Coucou (island/island.ts + core/anim.ts): abrir é uma mola com resposta 0,5 s e amortecimento 0,72
  // (K = ω², C = 2ζω); fechar é uma curva cúbica de 340 ms (.45, 0, .2, 1), sem balanço.
  const MOLA_ABRIR = { K: (2 * Math.PI / .5) ** 2, C: 2 * .72 * (2 * Math.PI / .5) };
  const CURVA_FECHAR = { ms: 340, ease: bezier(.45, 0, .2, 1) };
  let tween = null;

  function bezier(x1, y1, x2, y2) {
    const cx = t => 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3;
    const cy = t => 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3;
    return x => {
      let lo = 0, hi = 1, t = x;
      for (let i = 0; i < 12; i++) { if (cx(t) < x) lo = t; else hi = t; t = (lo + hi) / 2; }
      return cy(t);
    };
  }

  function moverPara(alvo) {
    const encolhendo = alvo.h < mola.h - .5 && alvo.w < mola.w - .5;
    mola.alvo = { ...alvo };
    tween = encolhendo ? { de: { w: mola.w, h: mola.h, r: mola.r }, t0: performance.now() } : null;
    informarRegiao(Math.max(mola.w, alvo.w), Math.max(mola.h, alvo.h));   // cobre a forma durante o movimento
    if (!mola.rodando) { mola.rodando = true; requestAnimationFrame(passoMola); }
  }

  let ultimoMola = 0;
  function passoMola(t) {
    const dt = lim((t - (ultimoMola || t)) / 1000, 0, 1 / 30) || 1 / 60;
    ultimoMola = t;
    if (tween) {
      const p = Math.min(1, (t - tween.t0) / CURVA_FECHAR.ms), k = CURVA_FECHAR.ease(p);
      for (const q of ['w', 'h', 'r']) mola[q] = tween.de[q] + (mola.alvo[q] - tween.de[q]) * k;
      mola.vw = mola.vh = mola.vr = 0;
      aplicarForma();
      if (p < 1) { requestAnimationFrame(passoMola); return; }
      tween = null;
      Object.assign(mola, mola.alvo, { vw: 0, vh: 0, vr: 0 });
      mola.rodando = false; ultimoMola = 0;
      aplicarForma();
      informarRegiao(mola.w, mola.h);
      return;
    }
    const K = MOLA_ABRIR.K, C = MOLA_ABRIR.C;
    let parado = true;
    for (let s = 0; s < 4; s++) {
      for (const p of ['w', 'h', 'r']) {
        const v = 'v' + p;
        const a = -K * (mola[p] - mola.alvo[p]) - C * mola[v];
        mola[v] += a * dt / 4;
        mola[p] += mola[v] * dt / 4;
      }
    }
    for (const p of ['w', 'h', 'r']) {
      if (Math.abs(mola[p] - mola.alvo[p]) > .4 || Math.abs(mola['v' + p]) > .4) parado = false;
    }
    if (parado) {
      Object.assign(mola, mola.alvo, { vw: 0, vh: 0, vr: 0 });
      mola.rodando = false; ultimoMola = 0;
      aplicarForma();
      informarRegiao(mola.w, mola.h);
      return;
    }
    aplicarForma();
    requestAnimationFrame(passoMola);
  }

  function tamanhoAtual() {
    if (aberta) return VISTAS_GRANDES.has(vista) ? TAM.grande : TAM.home;
    const balao = $('#balao');
    if (balao.classList.contains('ativo')) {
      const extra = Math.min(560, balao.scrollWidth + 22);   // largura real do texto, mesmo durante a transição
      return { ...TAM.compacta, w: TAM.compacta.w + extra };
    }
    return TAM.compacta;
  }

  function abrir(valor) {
    if (valor === aberta) return;
    aberta = valor;
    nucleo.classList.toggle('aberto', valor);
    if (!valor) cancelarContagem();
    moverPara(tamanhoAtual());
    if (valor) setTimeout(redimensionarCanvases, 60);
  }

  // Recolher após sair: a barra fina encolhe mostrando o tempo que falta (guia: primeiro commit).
  // Entrar de novo cancela; Fixar mantém aberta; o tempo é ajustado em Controles.
  let recolherS = Number(localStorage.getItem('nucleo.recolherS')) || 3;
  const contagem = $('#contagem');
  let recolherEm = 0, contagemFrame = 0;
  function podeRecolher() {
    return aberta && !fixada && !respondendo && document.activeElement !== $('#entrada')
      && $('#modelo-lista').hidden;
  }
  function agendarRecolher() {
    if (!podeRecolher()) return;
    clearTimeout(timerFechar);
    recolherEm = performance.now() + recolherS * 1000;
    contagem.hidden = false;
    timerFechar = setTimeout(() => abrir(false), recolherS * 1000);
    desenharContagem();
  }
  function desenharContagem() {
    if (!recolherEm) return;
    const falta = lim((recolherEm - performance.now()) / (recolherS * 1000), 0, 1);
    contagem.style.transform = `scaleX(${falta.toFixed(3)})`;
    contagemFrame = requestAnimationFrame(desenharContagem);
  }
  function cancelarContagem() {
    clearTimeout(timerFechar);
    cancelAnimationFrame(contagemFrame);
    recolherEm = 0;
    contagem.hidden = true;
  }

  // hover abre com um pequeno atraso; sair começa a contagem para recolher
  // durante o arraste a janela anda sob o cursor: esses eventos de entrada/saída não contam
  let arrastando = false, fimArrasteT = 0;
  nucleo.addEventListener('mouseenter', () => {
    if (arrastando) return;
    cancelarContagem();
    if (!aberta) timerAbrir = setTimeout(() => abrir(true), 260);
  });
  nucleo.addEventListener('mouseleave', () => {
    clearTimeout(timerAbrir);
    if (!arrastando) agendarRecolher();
  });
  // Arrastar: segurar a barra, a alça da tira ou qualquer área vazia do painel move a ilha.
  // Encostada no topo ela desliza na horizontal; uma puxada clara para baixo a solta ("desgrudar").
  // Passou de 4 px vira arraste; o clique que vem logo depois é ignorado.
  let arraste = null, arrastou = false;
  const SEM_ARRASTE = 'button, input, select, textarea, label, a, canvas, iframe, [contenteditable], ' +
    '.trilho, .mensagens, .composer, .falas, .escolha-lista, .reacoes-lista, .regra, .gv-lista';
  nucleo.addEventListener('pointerdown', e => {
    if (e.button !== 0 || arraste || e.target.closest(SEM_ARRASTE)) return;
    arraste = { x: e.screenX, y: e.screenY, sx: e.screenX, sy: e.screenY };
    arrastou = false;
  });
  document.addEventListener('pointermove', e => {
    if (!arraste) return;
    const dx = e.screenX - arraste.x, dy = e.screenY - arraste.y;
    if (!arrastou && Math.hypot(e.screenX - arraste.sx, e.screenY - arraste.sy) < 4) return;
    if (!arrastou) { arrastando = true; clearTimeout(timerAbrir); cancelarContagem(); }
    arrastou = true;
    arraste.x = e.screenX; arraste.y = e.screenY;
    if (modoTopo) {
      // encostada no topo: desliza na horizontal; desgruda só com puxada clara para baixo (diagonal conta)
      const tx = e.screenX - arraste.sx, ty = e.screenY - arraste.sy;
      if (ty < DESGRUDAR_PX || ty < Math.abs(tx) * .6) {
        if (dx && ponte) ponte.arrastar(Math.round(dx), 0);
        return;
      }
      aplicarModo(false);
      if (ponte) ponte.desgrudar();
      nucleo.classList.add('soltando');
      setTimeout(() => nucleo.classList.remove('soltando'), 480);
    }
    if (dx || dy) { if (ponte) ponte.arrastar(Math.round(dx), Math.round(dy)); }
  });
  const soltar = () => {
    if (!arraste) return;
    if (arrastou && ponte) ponte.soltar();
    arraste = null;
    if (arrastou) { clearTimeout(fimArrasteT); fimArrasteT = setTimeout(() => { arrastando = false; }, 450); }
    setTimeout(() => { arrastou = false; }, 0);   // o clique que vem depois do arraste não conta
  };
  document.addEventListener('pointerup', soltar);
  document.addEventListener('pointercancel', soltar);
  $('#orbe').addEventListener('click', () => { if (arrastou) return; orbe.explodir(); abrir(!aberta); });
  $('#balao').addEventListener('click', () => { if (!arrastou) abrir(true); });
  function fixarAberta(valor) {
    fixada = valor;
    $('#fixar').classList.toggle('ligado', fixada);
    $('#ctl-fixar').classList.toggle('ligada', fixada);
    if (fixada) cancelarContagem();
    else if (aberta && !nucleo.matches(':hover')) agendarRecolher();
  }
  $('#fixar').addEventListener('click', () => fixarAberta(!fixada));
  $('#ctl-fixar').addEventListener('click', () => fixarAberta(!fixada));
  $('#recolher').addEventListener('click', () => { fixada = false; $('#fixar').classList.remove('ligado'); abrir(false); });
  const recolherSlider = $('#ctl-recolher');
  recolherSlider.value = recolherS;
  $('#ctl-recolher-v').textContent = recolherS + ' s';
  recolherSlider.addEventListener('input', () => {
    recolherS = Number(recolherSlider.value);
    localStorage.setItem('nucleo.recolherS', String(recolherS));
    $('#ctl-recolher-v').textContent = recolherS + ' s';
  });

  /* ======================= relógio ======================= */
  function relogio() {
    const d = new Date();
    $('#hora').textContent = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    $('#data').textContent = d.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' })
      .replace(/\./g, '').toUpperCase();
  }
  setInterval(relogio, 1000);
  relogio();

  /* ======================= cores vivas ======================= */
  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const cor = { a1: hex(HUMORES.calmo[0]), a2: hex(HUMORES.calmo[1]) };

  function hslParaRgb(h, s, l) {
    s /= 100; l /= 100;
    const k = n => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
    const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return [255 * f(0), 255 * f(8), 255 * f(4)];
  }

  function humorAtual() {
    if (performance.now() < alertaAte) return 'alerta';
    if (respondendo || pensandoNarrador) return 'pensando';
    if (estado.processando) return 'processando';
    if (audioAtivo && rms > .004) return 'som';
    if (estado.pausado) return 'pausado';
    return 'calmo';
  }

  function alvoDeCor(humor) {
    if (humor !== 'som') return HUMORES[humor].map(hex);
    // a cor do som: graves puxam para violeta/âmbar, agudos para ciano
    let soma = 0, peso = 0;
    bandas.forEach((v, i) => { soma += v * i; peso += v; });
    const centro = peso ? soma / peso / (bandas.length - 1) : .5;
    const h = 300 - centro * 130;
    return [hslParaRgb(h, 95, 62), hslParaRgb((h + 55) % 360, 90, 60)];
  }

  function atualizarCores() {
    const humor = humorAtual();
    nucleo.dataset.humor = humor;
    const [b1, b2] = alvoDeCor(humor);
    for (let i = 0; i < 3; i++) {
      cor.a1[i] += (b1[i] - cor.a1[i]) * .06;
      cor.a2[i] += (b2[i] - cor.a2[i]) * .06;
    }
    const css = c => `rgb(${c.map(Math.round).join(',')})`;
    document.documentElement.style.setProperty('--a1', css(cor.a1));
    document.documentElement.style.setProperty('--a2', css(cor.a2));
    document.documentElement.style.setProperty('--giro-s',
      humor === 'pensando' ? '2.4s' : humor === 'processando' ? '3.4s' : humor === 'som' ? (4.5 - rms * 30).toFixed(2) + 's' : '9s');
    return humor;
  }

  /* ======================= mascote: o rosto do pet, como body/desenho_rosto.py ======================= */
  // Mesmo desenho do pet (moldura, tela, olhos por emoção, piscada, olhar, boca, gravata e óculos).
  // As formas dos olhos e as cores vêm do Python (ponte.aparencia_pet), sem duplicar a tabela.
  const mascote = (() => {
    const c = $('#mascote'), ctx = c.getContext('2d');
    const W = 64, H = 44, K = .28;                 // corpo de 120x90 em escala + espaço para os braços
    const FORMA0 = { w: 30, h: 40, inner: .14, outer: 0, smile: 0, dy: 0 };
    let olhos = {}, cores = { moldura: '#63e56f', casca: '#101512', tela: '#171e19', olho: '#3ee877', brilho: '#c8ffd8' };
    let acess = {}, forma = { ...FORMA0 }, emocao = 'observando', boca = 0, t = 0, bracos = null;
    // ============================================================================
    // BRAÇOS - física massa-mola (mesma do body/bracos.py; AJUSTE OS PESOS AQUI)
    //   rigidez: força do retorno ao alvo (alta = braço pesado/duro)
    //   amortecimento: atrito por frame (perto de 1 = seco; baixo = quica, inércia)
    // ============================================================================
    const BRACO_CFG = {
      rigPos: .10, amoPos: .60,      // posição: resposta média, balanço moderado
      rigRot: .07, amoRot: .55,      // rotação: pêndulo mole, oscila antes de parar
      rigSq: .16, amoSq: .55,        // squash: deforma rápido, elasticidade quica
      ganhoRot: .9, ganhoSq: .06, sqMax: .35,
      idleAmp: 2, idleFreq: .003, idleFase: 1.3,
      falaAmp: 10, ganhoBoca: .3,
      impulsoP: .05, impulsoX: 3, impulsoY: 4, impulsoAlcance: 12,
    };
    const molaB = (rig, amo) => ({ v: 0, t: 0, vel: 0, rig, amo });
    const passoBra = m => { m.vel += (m.t - m.v) * m.rig; m.vel *= m.amo; m.v += m.vel; };
    const bracoB = lado => ({
      lado,
      x: molaB(BRACO_CFG.rigPos, BRACO_CFG.amoPos), y: molaB(BRACO_CFG.rigPos, BRACO_CFG.amoPos),
      rot: molaB(BRACO_CFG.rigRot, BRACO_CFG.amoRot), sq: molaB(BRACO_CFG.rigSq, BRACO_CFG.amoSq),
      fisica() {
        passoBra(this.x); passoBra(this.y); passoBra(this.rot); passoBra(this.sq);
        this.rot.t = -this.lado * this.x.vel * BRACO_CFG.ganhoRot;              // pêndulo: inclina com o movimento
        this.sq.t = 1 + Math.min(BRACO_CFG.sqMax, (Math.abs(this.x.vel) + Math.abs(this.y.vel)) * BRACO_CFG.ganhoSq);
      },
    });
    const bra = { esq: bracoB(-1), dir: bracoB(1) };
    let piscada = 0, proxPiscada = 2, gx = 0, gy = 0, pontX = -1e4, pontY = -1e4;
    c.width = W * DPR(); c.height = H * DPR();
    document.addEventListener('pointermove', e => { pontX = e.clientX; pontY = e.clientY; });

    function rr(x, y, w, h, r) {
      ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
    }

    function desenhar(dt) {
      t += dt;
      const destino = olhos[emocao] || olhos.observando || FORMA0, k = Math.min(1, dt * 9);
      for (const p of ['w', 'h', 'inner', 'outer', 'smile', 'dy']) forma[p] += (destino[p] - forma[p]) * k;
      proxPiscada -= dt;
      if (proxPiscada <= 0) { piscada = .14; proxPiscada = 2.5 + Math.random() * 3; }
      piscada = Math.max(0, piscada - dt);
      const pisco = piscada > 0 ? .05 : 1;
      const r = c.getBoundingClientRect();
      gx += (lim((pontX - (r.left + r.width / 2)) / 160, -1, 1) - gx) * Math.min(1, dt * 6);
      gy += (lim((pontY - (r.top + r.height / 2)) / 120, -1, 1) - gy) * Math.min(1, dt * 6);
      boca += ((respondendo ? 3 + 9 * Math.abs(Math.sin(t * 9)) : 0) - boca) * Math.min(1, dt * 14);

      ctx.setTransform(DPR(), 0, 0, DPR(), 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.translate(W / 2, H / 2); ctx.scale(K, K);
      ctx.lineJoin = 'round';
      if (bracos) {
        // estados: gesticula na fala (ondas assíncronas + impulsos de velocidade); em repouso, respira
        bra.esq.fisica(); bra.dir.fisica();
        const tm = performance.now(), C = BRACO_CFG;
        if (respondendo) {
          bra.esq.y.t = Math.sin(tm * .016) * C.falaAmp - boca * C.ganhoBoca;
          bra.dir.y.t = Math.cos(tm * .014) * C.falaAmp - boca * C.ganhoBoca;
          if (Math.random() < C.impulsoP) {                    // pico de gesto: impulso na velocidade (inércia)
            bra.esq.x.vel -= Math.random() * C.impulsoX; bra.dir.x.vel += Math.random() * C.impulsoX;
            bra.esq.y.vel -= Math.random() * C.impulsoY; bra.dir.y.vel -= Math.random() * C.impulsoY;
            bra.esq.x.t = -Math.random() * C.impulsoAlcance; bra.dir.x.t = Math.random() * C.impulsoAlcance;
          }
        } else {
          bra.esq.y.t = Math.sin(tm * C.idleFreq) * C.idleAmp;
          bra.dir.y.t = Math.sin(tm * C.idleFreq + C.idleFase) * C.idleAmp;      // fases diferentes: nunca em espelho
          bra.esq.x.t = bra.dir.x.t = 0;
        }
        // renderização: translate (posição) -> rotate (pêndulo) -> scale (squash & stretch no Y)
        ctx.fillStyle = '#1e222b'; ctx.strokeStyle = bracos; ctx.lineWidth = 5;
        for (const b of [bra.esq, bra.dir]) {
          ctx.save();
          ctx.translate(b.lado * 72 + b.x.v, 55 + b.y.v);
          ctx.rotate(b.rot.v * Math.PI / 180);
          ctx.scale(1 / b.sq.v, b.sq.v);
          rr(b.lado * 8 - 16, -10, 32, 20, 10); ctx.fill(); ctx.stroke();
          ctx.restore();
        }
      }
      ctx.fillStyle = cores.casca; ctx.strokeStyle = cores.moldura; ctx.lineWidth = 5;
      rr(-60, -45, 120, 90, 20); ctx.fill(); ctx.stroke();
      ctx.fillStyle = cores.tela; rr(-49, -34, 98, 68, 12); ctx.fill();

      for (const lado of [-1, 1]) {
        const w = forma.w;
        let h = forma.h * pisco;
        if (emocao === 'curioso' && lado === 1) h *= 1.15;
        h = Math.max(h, 3);
        const cx = lado * 24 + gx * 4, cy = forma.dy + gy * 3, topo = cy - h / 2;
        ctx.fillStyle = cores.olho; rr(cx - w / 2, topo, w, h, Math.min(w, h) * .38); ctx.fill();
        if (pisco > .5) {                                   // pálpebras e sorriso cortam o olho com a cor da tela
          const fora = cx + lado * w / 2, dentro = cx - lado * w / 2;
          ctx.fillStyle = cores.tela;
          ctx.beginPath(); ctx.moveTo(fora + lado * 4, topo - 40); ctx.lineTo(dentro - lado * 4, topo - 40);
          ctx.lineTo(dentro - lado * 4, topo + forma.inner * h); ctx.lineTo(fora + lado * 4, topo + forma.outer * h);
          ctx.closePath(); ctx.fill();
          if (forma.smile > .02) {
            const ch = h * forma.smile * 1.6;
            ctx.beginPath(); ctx.ellipse(cx, topo + h + ch * .05, w * .75, ch / 2, 0, 0, Math.PI * 2); ctx.fill();
          }
          if (h >= 8) {                                     // brilho, só com o olho aberto
            ctx.save(); rr(cx - w / 2, topo, w, h, Math.min(w, h) * .38); ctx.clip();
            ctx.fillStyle = cores.brilho;
            ctx.beginPath(); ctx.arc(cx - w * .18 + gx * 3, topo + h * (.24 + Math.max(forma.inner, forma.outer) * .6) + gy * 2, 3.6, 0, Math.PI * 2);
            ctx.fill(); ctx.restore();
          }
        }
      }

      ctx.strokeStyle = cores.olho; ctx.lineWidth = 2.5; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(-13, 22); ctx.quadraticCurveTo(0, 22 + boca, 13, 22);
      if (boca > 8) { ctx.closePath(); ctx.fillStyle = '#000'; ctx.fill(); }
      ctx.stroke();

      if (acess.oculos) {
        ctx.strokeStyle = acess.oculos; ctx.lineWidth = 2;
        for (const lado of [-1, 1]) { rr(lado * 24 - 21, -25, 42, 52, 10); ctx.stroke(); }
        ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(-3, -18); ctx.lineTo(3, -18); ctx.stroke();
      }
      if (acess.gravata) {
        ctx.fillStyle = acess.gravata; ctx.strokeStyle = acess.gravata; ctx.lineWidth = 1;
        ctx.fillRect(-4, 21, 8, 6);
        ctx.beginPath(); ctx.moveTo(-3, 26); ctx.lineTo(3, 26); ctx.lineTo(5.5, 38); ctx.lineTo(0, 42); ctx.lineTo(-5.5, 38);
        ctx.closePath(); ctx.fill();
      }
    }

    let ultimo = 0;
    function quadro(agora) {
      desenhar(Math.min(.05, (agora - (ultimo || agora)) / 1000));
      ultimo = agora;
      requestAnimationFrame(quadro);
    }
    requestAnimationFrame(quadro);
    c.addEventListener('click', () => { if (arrastou) return; abrir(!aberta); });

    return {
      configurar(d) {
        olhos = d.olhos || olhos;
        cores = { ...cores, ...(d.cores || {}) };
        acess = d.acessorios || {};
        bracos = d.bracos || null;
      },
      definirEmocao(nome) { emocao = nome || 'observando'; },
    };
  })();

  /* ======================= vibração do chat: onda da resposta (como a aba Som) ======================= */
  // Barras que rolam da direita para a esquerda. Cada token da resposta dá um pulso; a fala do modelo
  // (envelope do WAV, enviado pelo Python logo antes de tocar) desenha o volume real no tempo.
  const vibra = (() => {
    const c = $('#vibra-cv'), ctx = c.getContext('2d');
    const N = 56, POR_S = 24, leds = $('#vibra-leds');
    for (let i = 0; i < 12; i++) leds.appendChild(document.createElement('i'));
    const barras = new Float32Array(N);
    let env = null, t0 = 0, dur = 0, origem = '', pulso = 0, falando = false, ultimosLeds = -1, ultimoEstado = '';
    const fmt = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}.${Math.floor(s * 10) % 10}`;

    function falar(dados, nomeOrigem) {
      env = Array.isArray(dados.valores) && dados.valores.length ? dados.valores : null;
      dur = Number(dados.duracao) || 0;
      t0 = performance.now(); origem = nomeOrigem; falando = !!env;
    }
    function pulsar(v) { pulso = Math.min(1, pulso + v); }

    function desenhar(dt) {
      const agora = performance.now(), w = c.clientWidth, h = c.clientHeight;
      if (!w || !h) return;
      ajustarCanvas(c, w, h);
      ctx.setTransform(DPR(), 0, 0, DPR(), 0, 0);
      ctx.clearRect(0, 0, w, h);
      pulso *= Math.exp(-dt * 4);
      if (falando && agora - t0 > dur * 1000 + 250) falando = false;
      const gap = 2, bw = (w - gap * (N - 1)) / N;
      const c1 = `rgb(${cor.a1.map(Math.round)})`, c2 = `rgb(${cor.a2.map(Math.round)})`;
      const g = ctx.createLinearGradient(0, 0, w, 0);
      g.addColorStop(0, c2); g.addColorStop(1, c1);
      ctx.fillStyle = g;
      let soma = 0;
      for (let i = 0; i < N; i++) {
        let a = .05 + .03 * Math.sin(i * .5 + agora / 260);                            // ondulação parada
        a = Math.max(a, pulso * (.25 + .45 * Math.abs(Math.sin(i * .9 + agora / 140))));  // pulso dos tokens
        if (falando) {
          const p = (agora - t0) / 1000 * POR_S - (N - 1 - i) * .5;                     // a onda rola para a esquerda
          if (p >= 0 && p < env.length) a = Math.max(a, env[Math.floor(p)]);
        }
        barras[i] += (lim(a, 0, 1) - barras[i]) * Math.min(1, dt * 18);
        soma += barras[i];
        const bh = Math.max(2, barras[i] * (h - 22));
        ctx.fillRect(i * (bw + gap), (h - 20 - bh) / 2 + 4, bw, bh);
      }
      const nivel = Math.round(soma / N * 12);
      if (nivel !== ultimosLeds) {
        ultimosLeds = nivel;
        $$('i', leds).forEach((l, i) => { l.className = i < nivel ? ('on' + (i >= 9 ? ' quente' : '')) : ''; });
      }
      const estado = falando ? (origem === 'modelo' ? 'Falando · voz do modelo' : 'Falando · voz do sistema')
        : respondendo ? 'Escrevendo a resposta…' : 'Pronta';
      if (estado !== ultimoEstado) { ultimoEstado = estado; $('#vibra-estado').textContent = estado; }
      $('#vibra-tempo').textContent = fmt(falando ? Math.max(0, (agora - t0) / 1000) : 0);
    }
    return { desenhar, falar, pulsar };
  })();

  /* ======================= som de clique ======================= */
  // Um "blip" curto sintetizado aqui: os sons do Coucou têm licença própria e não são copiados para o projeto.
  let somCtx = null;
  function tocarClique() {
    try {
      somCtx = somCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (somCtx.state === 'suspended') somCtx.resume();
      const t = somCtx.currentTime, osc = somCtx.createOscillator(), g = somCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, t);
      osc.frequency.exponentialRampToValueAtTime(1320, t + .06);
      g.gain.setValueAtTime(.0001, t);
      g.gain.exponentialRampToValueAtTime(.12, t + .008);
      g.gain.exponentialRampToValueAtTime(.0001, t + .09);
      osc.connect(g).connect(somCtx.destination);
      osc.start(t); osc.stop(t + .1);
    } catch (_) { /* sem áudio, o clique funciona do mesmo jeito */ }
  }
  document.addEventListener('click', e => {
    if (e.target.closest('button, input, select, .card, #orbe, #mascote, #balao, .escolha-lista li')) tocarClique();
  }, true);

  /* ======================= orbe neural ======================= */
  const orbe = (() => {
    const c = $('#orbe'), ctx = c.getContext('2d');
    const S = 40;
    let ondas = [], fase = 0, ponteiro = null, energia = 0;
    const particulas = Array.from({ length: 14 }, (_, i) => ({ a: i / 14 * Math.PI * 2, r: 13 + (i % 3) * 2.5, v: .6 + (i % 4) * .2 }));
    c.width = S * DPR(); c.height = S * DPR();
    c.addEventListener('mousemove', e => { const b = c.getBoundingClientRect(); ponteiro = { x: e.clientX - b.left - S / 2, y: e.clientY - b.top - S / 2 }; });
    c.addEventListener('mouseleave', () => { ponteiro = null; });

    const PARAM = {
      calmo: { vel: .7, amp: .06, part: 6, onda: 0 },
      processando: { vel: 2.6, amp: .10, part: 14, onda: .9 },
      pensando: { vel: 1.7, amp: .16, part: 10, onda: .35 },
      alerta: { vel: 3.4, amp: .12, part: 8, onda: 1.8 },
      som: { vel: 1.4, amp: .05, part: 12, onda: 0 },
      pausado: { vel: .25, amp: .03, part: 3, onda: 0 },
    };

    function explodir() { for (let i = 0; i < 3; i++) ondas.push({ r: 10 + i * 3, a: .9 }); }

    function desenhar(humor, dt) {
      const p = PARAM[humor] || PARAM.calmo;
      fase += dt * p.vel;
      energia += ((humor === 'som' ? rms * 18 : 0) - energia) * .2;
      if (p.onda && Math.random() < p.onda * dt) ondas.push({ r: 11, a: .8 });
      if (humor === 'som' && pico > .35 && Math.random() < .3) ondas.push({ r: 11, a: .6 });
      ctx.setTransform(DPR(), 0, 0, DPR(), 0, 0);
      ctx.clearRect(0, 0, S, S);
      ctx.translate(S / 2, S / 2);
      const c1 = `rgb(${cor.a1.map(Math.round)})`, c2 = `rgb(${cor.a2.map(Math.round)})`;

      // halo
      const halo = ctx.createRadialGradient(0, 0, 4, 0, 0, 20);
      halo.addColorStop(0, c1.replace('rgb', 'rgba').replace(')', ',.35)'));
      halo.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(0, 0, 20, 0, Math.PI * 2); ctx.fill();

      // ondas de energia
      ondas = ondas.filter(o => o.a > .02 && o.r < 18.5);   // nunca passa da borda do canvas
      ondas.forEach(o => {
        o.r += dt * 22; o.a *= Math.pow(.12, dt);
        const alfa = o.a * Math.max(0, 1 - o.r / 18.5);
        ctx.strokeStyle = c1.replace('rgb', 'rgba').replace(')', `,${alfa.toFixed(3)})`);
        ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(0, 0, o.r, 0, Math.PI * 2); ctx.stroke();
      });

      // corpo: uma bolha que respira e se inclina para o cursor
      const respira = 1 + Math.sin(fase * 1.3) * (humor === 'calmo' || humor === 'pausado' ? .06 : .03) + energia * .12;
      const R = 9.5 * respira;
      ctx.beginPath();
      for (let i = 0; i <= 48; i++) {
        const t = i / 48 * Math.PI * 2;
        let r = R * (1 + p.amp * Math.sin(3 * t + fase * 2.1) + p.amp * .7 * Math.sin(5 * t - fase * 1.7)
          + (humor === 'som' ? (bandas[Math.floor(i / 48 * bandas.length) % bandas.length] || 0) * .28 : 0));
        if (ponteiro) {
          const ang = Math.atan2(ponteiro.y, ponteiro.x);
          r += Math.max(0, Math.cos(t - ang)) * 2.4;
        }
        const x = Math.cos(t) * r, y = Math.sin(t) * r;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      const g = ctx.createRadialGradient(-3, -4, 1, 0, 0, R * 1.4);
      g.addColorStop(0, '#ffffff'); g.addColorStop(.25, c1); g.addColorStop(1, c2);
      ctx.fillStyle = g; ctx.shadowColor = c1; ctx.shadowBlur = 10; ctx.fill(); ctx.shadowBlur = 0;

      // pensando: um anel tracejado girando como raciocínio
      if (humor === 'pensando') {
        ctx.save(); ctx.rotate(fase * 2); ctx.setLineDash([3, 4]);
        ctx.strokeStyle = c2; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.arc(0, 0, R + 5, 0, Math.PI * 1.4); ctx.stroke();
        ctx.restore();
      }
      // partículas orbitando
      particulas.slice(0, p.part).forEach(q => {
        q.a += dt * q.v * p.vel;
        const rr = q.r + Math.sin(fase + q.a * 3) * 1.2;
        ctx.fillStyle = c1;
        ctx.globalAlpha = .55; ctx.beginPath(); ctx.arc(Math.cos(q.a) * rr, Math.sin(q.a) * rr * .8, .9, 0, Math.PI * 2); ctx.fill();
      });
      ctx.globalAlpha = 1;
    }
    return { desenhar, explodir };
  })();

  /* ======================= balões do narrador ======================= */
  const filaBalao = [];
  let balaoOcupado = false;

  function falar(texto, origem, tom) {
    if (!texto) return;
    filaBalao.push({ texto, origem, tom });
    adicionarFala(texto, origem);
    if (tom === 'alerta') alertaAte = performance.now() + 3500;
    if (!balaoOcupado) proximoBalao();
  }

  function proximoBalao() {
    const item = filaBalao.shift();
    const balao = $('#balao');
    if (!item) { balaoOcupado = false; balao.classList.remove('ativo'); if (!aberta) moverPara(TAM.compacta); return; }
    balaoOcupado = true;
    $('#balao-origem').textContent = item.origem === 'ollama' ? 'IA' : item.origem === 'voce' ? 'VOCÊ'
      : item.origem === 'pet' ? (estado.pet || 'Pestinha').toUpperCase() : 'NÚCLEO';
    $('#balao-txt').textContent = item.texto;
    balao.classList.add('ativo');
    if (!aberta) requestAnimationFrame(() => moverPara(tamanhoAtual()));
    orbe.explodir();
    setTimeout(proximoBalao, lim(item.texto.length * 70, 3800, 8000));
  }

  function adicionarFala(texto, origem) {
    const lista = $('#falas');
    const li = document.createElement('li');
    li.textContent = texto;
    const s = document.createElement('small');
    s.textContent = (origem === 'ollama' ? 'IA local · ' : '') + new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    li.appendChild(s);
    lista.prepend(li);
    while (lista.children.length > 4) lista.lastChild.remove();
  }

  $('#narrar').addEventListener('click', () => { if (ponte) ponte.pedir_insight(); });
  $('#narrador-liga').addEventListener('click', e => {
    const ligado = !e.currentTarget.classList.contains('ligada');
    e.currentTarget.classList.toggle('ligada', ligado);
    e.currentTarget.textContent = ligado ? 'Narrador ligado' : 'Narrador mudo';
    if (ponte) ponte.ligar_narrador(ligado);
  });

  /* ======================= vistas e dock ======================= */
  function carregarQuadro(quadro) {
    if (!quadro || quadro.getAttribute('src')) return;
    quadro.addEventListener('load', () => enviarInicio(quadro), { once: true });
    quadro.src = quadro.dataset.src;
  }

  function mostrarVista(nome) {
    vista = nome;
    $$('.dock [data-vista]').forEach(b => b.classList.toggle('ativo', b.dataset.vista === nome));
    $$('.vista').forEach(s => s.classList.toggle('ativa', s.dataset.vista === nome));
    const quadro = $(`.vista[data-vista="${nome}"] iframe`);
    if (quadro && !quadro.hidden) carregarQuadro(quadro);
    if (nome === 'chat' && !modelos.length && ponte) ponte.listar_modelos();
    if (aberta) moverPara(tamanhoAtual());
    setTimeout(redimensionarCanvases, 60);
  }

  const dock = $('#dock');
  // avatar do topo da tira: o rosto do mascote copiado a cada quadro (mesma vida, mesmo tamanho)
  const avatar = (() => {
    const cv = $('#avatar-cv'), cx = cv.getContext('2d');
    return { copiar() { ajustarCanvas(cv, 28, 24); cx.drawImage($('#mascote'), 0, 0, cv.width, cv.height); } };
  })();
  $$('.dock [data-vista]').forEach(b => b.addEventListener('click', () => mostrarVista(b.dataset.vista)));
  $$('[data-painel]').forEach(b => b.addEventListener('click', () => { if (ponte) ponte.painel(b.dataset.painel); }));

  /* ======================= controles (aba Controles) ======================= */
  let narradorLigado = true;
  $$('.chave[data-acao]').forEach(b => b.addEventListener('click', () => {
    const nome = b.dataset.acao;
    if (nome === 'narrador') {
      narradorLigado = !narradorLigado;
      $('#narrador-liga').classList.toggle('ligada', narradorLigado);
      $('#narrador-liga').textContent = narradorLigado ? 'Narrador ligado' : 'Narrador mudo';
      if (ponte) ponte.ligar_narrador(narradorLigado);
      atualizarControles();
    } else if (ponte) {
      ponte.acao(nome, !(b.getAttribute('aria-pressed') === 'true'));
    }
  }));
  const BARRAS_PET = [['energia', 'ctl-energia', 'ctl-energia-b'], ['estimulacao', 'ctl-estimulo', 'ctl-estimulo-b'],
    ['insatisfacao', 'ctl-insatisfacao', 'ctl-insatisfacao-b']];
  function atualizarControles() {
    $('#ctl-emocao').textContent = (estado.emocao || '—').toLowerCase();
    BARRAS_PET.forEach(([chave, valor, barra]) => {
      const pct = estado[chave] ?? 0;
      $('#' + valor).textContent = pct + '%';
      $('#' + barra).style.transform = `scaleX(${lim(pct / 100, 0, 1).toFixed(3)})`;
    });
    const marcado = { pausa: !!estado.pausado, voz: !!estado.voz, travessuras: !!estado.travessuras,
      avion: !!estado.offline, narrador: narradorLigado };
    $$('.chave[data-acao]').forEach(b => b.setAttribute('aria-pressed', String(!!marcado[b.dataset.acao])));
  }
  // efeito lupa: os ícones crescem conforme o cursor se aproxima (a tira é vertical)
  dock.addEventListener('mousemove', e => {
    $$('button', dock).forEach(b => {
      const r = b.getBoundingClientRect();
      const d = Math.abs(e.clientY - (r.top + r.height / 2));
      b.style.transform = `scale(${(1 + Math.max(0, 1 - d / 90) * .38).toFixed(3)})`;
    });
  });
  dock.addEventListener('mouseleave', () => $$('button', dock).forEach(b => { b.style.transform = ''; }));

  /* ======================= cards interativos ======================= */
  $$('.card').forEach(card => {
    card.addEventListener('pointermove', e => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      card.style.setProperty('--mx', (x * 100).toFixed(1) + '%');
      card.style.setProperty('--my', (y * 100).toFixed(1) + '%');
      if (!trilho.classList.contains('arrastando')) {
        card.style.transform = `perspective(700px) rotateX(${((.5 - y) * 7).toFixed(2)}deg) rotateY(${((x - .5) * 9).toFixed(2)}deg) translateY(-2px)`;
      }
    });
    card.addEventListener('pointerleave', () => { card.style.transform = ''; });
  });

  // trilho: arrastar para os lados com inércia (como widgets de celular)
  const trilho = $('#trilho');
  let arrasto = null;
  trilho.addEventListener('pointerdown', e => {
    if (e.target.closest('button')) return;
    arrasto = { x: e.clientX, s: trilho.scrollLeft, v: 0, t: performance.now(), ultimoX: e.clientX, moveu: false };
  });
  window.addEventListener('pointermove', e => {
    if (!arrasto) return;
    const dx = e.clientX - arrasto.x;
    if (Math.abs(dx) > 4) { arrasto.moveu = true; trilho.classList.add('arrastando'); }
    const agora = performance.now();
    arrasto.v = (arrasto.ultimoX - e.clientX) / Math.max(1, agora - arrasto.t);
    arrasto.t = agora; arrasto.ultimoX = e.clientX;
    trilho.scrollLeft = arrasto.s - dx;
  });
  window.addEventListener('pointerup', () => {
    if (!arrasto) return;
    let v = arrasto.v * 16;
    arrasto = null;
    const inercia = () => {
      if (Math.abs(v) < .4) { trilho.classList.remove('arrastando'); return; }
      trilho.scrollLeft += v; v *= .93;
      requestAnimationFrame(inercia);
    };
    inercia();
  });
  trilho.addEventListener('wheel', e => { trilho.scrollLeft += e.deltaY + e.deltaX; e.preventDefault(); }, { passive: false });

  /* ======================= card do pet ======================= */
  $('#bt-pausa').addEventListener('click', () => { if (ponte) ponte.acao('pausa', true); });
  $('#bt-voz').addEventListener('click', () => { if (ponte) ponte.acao('voz', true); });

  function aplicarEstado(e) {
    const antes = estado;
    estado = { ...antes, ...(e || {}) };
    if (!e || e.logs == null) estado.logs = antes.logs || [];   // logs vêm a cada 2 s: mantém os últimos
    $('#pet-nome').textContent = estado.pet || 'Pestinha';
    $('#pet-emocao').textContent = (estado.emocao || '—').toLowerCase();
    mascote.definirEmocao(estado.emocao_chave);
    $('#st-energia').textContent = (estado.energia ?? 0) + '%';
    $('#st-estimulo').textContent = (estado.estimulacao ?? 0) + '%';
    $('#st-insatisfacao').textContent = (estado.insatisfacao ?? 0) + '%';
    $('#anel-energia').style.strokeDashoffset = (163.4 * (1 - (estado.energia ?? 0) / 100)).toFixed(1);
    $('#bt-pausa').textContent = estado.pausado ? 'Retomar' : 'Pausar';
    $('#bt-voz').classList.toggle('ligada', !!estado.voz);
    grafico.empurrar(estado);
    enviarMetricas();
    if (antes.offline !== estado.offline && estado.offline) falar('Modo avião: o chat local ficou desligado.', 'sistema', 'calmo');
    atualizarControles();
  }

  /* ======================= gráfico em tempo real ======================= */
  const grafico = (() => {
    const c = $('#grafico'), ctx = c.getContext('2d');
    const series = { energia: [], estimulacao: [], atividade: [] };
    const CORES = { energia: '#45e6ff', estimulacao: '#b07bff', atividade: '#4dffb0' };
    function empurrar(e) {
      for (const k in series) { series[k].push(Number(e[k]) || 0); if (series[k].length > 120) series[k].shift(); }
    }
    function desenhar() {
      const w = c.clientWidth, h = c.clientHeight;
      if (!w || !h) return;
      ajustarCanvas(c, w, h);
      ctx.setTransform(DPR(), 0, 0, DPR(), 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = 'rgba(255,255,255,.06)'; ctx.lineWidth = 1;
      for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(0, h * i / 4); ctx.lineTo(w, h * i / 4); ctx.stroke(); }
      for (const k in series) {
        const s = series[k];
        if (s.length < 2) continue;
        ctx.beginPath();
        // a amostra mais nova fica sempre na borda direita; o histórico corre para a esquerda
        s.forEach((v, i) => { const x = w - (s.length - 1 - i) / 119 * w, y = h - 4 - v / 100 * (h - 8); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
        ctx.strokeStyle = CORES[k]; ctx.lineWidth = 2; ctx.shadowColor = CORES[k]; ctx.shadowBlur = 8; ctx.stroke(); ctx.shadowBlur = 0;
      }
    }
    return { empurrar, desenhar };
  })();

  /* ======================= som: card mini e estúdio ======================= */
  const ICONE_PLAY = '<svg viewBox="0 0 24 24"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.2-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" fill="currentColor"/></svg>';
  const ICONE_PAUSA = '<svg viewBox="0 0 24 24"><rect x="6.5" y="5" width="4" height="14" rx="1.4" fill="currentColor"/><rect x="13.5" y="5" width="4" height="14" rx="1.4" fill="currentColor"/></svg>';
  const leds = $('#leds');
  for (let i = 0; i < 16; i++) leds.appendChild(document.createElement('i'));
  const historicoOnda = new Array(220).fill(0);
  let marcas = [];

  function alternarAudio() { if (ponte) ponte.audio(!audioAtivo); }
  $('#som-play').addEventListener('click', alternarAudio);
  $('#estudio-audio').addEventListener('click', alternarAudio);
  $('#estudio-limpar').addEventListener('click', limparMomentos);
  $('#gv-marcar').addEventListener('click', () => $('#estudio').dispatchEvent(new MouseEvent('click')));

  function atualizarBotoesSom() {
    $('#som-play').innerHTML = audioAtivo ? ICONE_PAUSA : ICONE_PLAY;
    $('#estudio-audio').classList.toggle('gravando', audioAtivo);
    $('#estudio-audio').setAttribute('aria-pressed', String(audioAtivo));
    $('#estudio-audio').setAttribute('aria-label', audioAtivo ? 'Parar a escuta' : 'Ouvir o áudio do sistema');
    $('#som-titulo').textContent = audioAtivo ? (rms > .004 ? 'Tocando agora' : 'Silêncio') : 'Silêncio';
    $('#som-sub').textContent = audioAtivo ? 'Loopback do sistema · 48 kHz' : 'Toque para ouvir o que sai do PC';
  }
  atualizarBotoesSom();

  function aoReceberNiveis(d) {
    bandas = Array.isArray(d.bandas) ? d.bandas : bandas;
    rms = Number(d.rms) || 0;
    pico = Number(d.pico) || 0;
    historicoOnda.push(rms); historicoOnda.shift();
    const acesos = Math.round(lim(pico * 1.4, 0, 1) * 16);
    $$('i', leds).forEach((l, i) => { l.className = i < acesos ? ('on' + (i >= 13 ? ' pico' : i >= 10 ? ' quente' : '')) : ''; });
    const silencio = !!d.silencio;
    $('#som-titulo').textContent = silencio ? 'Silêncio' : 'Tocando agora';
    $('#estudio-estado').textContent = silencio ? 'Ouvindo · sem som agora' : 'Ouvindo o áudio do sistema';
    $$('i', gvMedidor).forEach((l, i) => { const acesos = Math.round(lim(pico * 1.4, 0, 1) * 16); l.className = i < acesos ? (i >= 13 ? 'on pico' : i >= 10 ? 'on quente' : 'on') : ''; });
  }

  function aoEstadoAudio(texto) {
    if (texto === 'conectando') { $('#estudio-estado').textContent = 'Conectando ao áudio do sistema…'; return; }
    if (texto === 'ativo' || texto === 'parado') {
      const era = audioAtivo;
      audioAtivo = texto === 'ativo';
      if (!audioAtivo) { bandas = bandas.map(() => 0); rms = 0; pico = 0; }
      $('#estudio-estado').textContent = audioAtivo ? 'Ouvindo o áudio do sistema' : 'Captura parada';
      if (audioAtivo && !era) falar('Ouvindo o som do PC. A cor segue a música.', 'sistema', 'calmo');
    } else {
      audioAtivo = false;
      $('#estudio-estado').textContent = texto;
      falar(texto, 'sistema', 'alerta');
    }
    atualizarBotoesSom();
  }

  function desenharSomMini() {
    const c = $('#som-mini'), ctx = c.getContext('2d');
    const w = c.clientWidth, h = c.clientHeight;
    if (!w || !h) return;
    ajustarCanvas(c, w, h);
    ctx.setTransform(DPR(), 0, 0, DPR(), 0, 0);
    const c1 = `rgb(${cor.a1.map(Math.round)})`, c2 = `rgb(${cor.a2.map(Math.round)})`;
    const fundo = ctx.createLinearGradient(0, 0, w, h);
    fundo.addColorStop(0, c2); fundo.addColorStop(1, '#07080d');
    ctx.fillStyle = fundo; ctx.fillRect(0, 0, w, h);
    // sol que respira com o nível
    const r = 38 + rms * 260;
    const sol = ctx.createRadialGradient(w * .72, h * .32, 4, w * .72, h * .32, r);
    sol.addColorStop(0, 'rgba(255,255,255,.85)'); sol.addColorStop(.35, c1); sol.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = sol; ctx.fillRect(0, 0, w, h);
    // onda que flui da direita para a esquerda
    const meio = h * .62, n = historicoOnda.length;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = i / (n - 1) * w, a = Math.min(1, historicoOnda[i] * 9) * h * .26 + 1.5;
      ctx.lineTo(x, meio - a);
    }
    for (let i = n - 1; i >= 0; i--) {
      const x = i / (n - 1) * w, a = Math.min(1, historicoOnda[i] * 9) * h * .26 + 1.5;
      ctx.lineTo(x, meio + a);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(255,255,255,.22)'; ctx.fill();
  }

  // estúdio: espectro radial + fita de onda + campo que reage ao mouse + marcas
  const estudio = (() => {
    const c = $('#estudio'), ctx = c.getContext('2d');
    let mouse = null, giro = 0;
    c.addEventListener('mousemove', e => { const b = c.getBoundingClientRect(); mouse = { x: e.clientX - b.left, y: e.clientY - b.top }; });
    c.addEventListener('mouseleave', () => { mouse = null; });
    c.addEventListener('click', marcar);
    document.addEventListener('keydown', e => {
      if (vista === 'som' && aberta && (e.key === 'm' || e.key === 'M') && document.activeElement.tagName !== 'TEXTAREA') marcar();
    });
    function marcar() {
      marcas.push({ idade: 0 });
      if (marcas.length > 12) marcas.shift();
      registrarMomento();
      orbe.explodir();
    }
    function desenhar(dt) {
      const w = c.clientWidth, h = c.clientHeight;
      if (!w || !h) return;
      ajustarCanvas(c, w, h);
      ctx.setTransform(DPR(), 0, 0, DPR(), 0, 0);
      const c1 = `rgb(${cor.a1.map(Math.round)})`, c2 = `rgb(${cor.a2.map(Math.round)})`;
      ctx.fillStyle = 'rgba(7,8,13,.35)'; ctx.fillRect(0, 0, w, h);   // rastro: cada quadro apaga só um pouco
      giro += dt * (.15 + rms * 4);
      const cx = w / 2, cy = h * .42, base = Math.min(w, h) * .13;
      // campo de pontos que se afasta do mouse
      ctx.fillStyle = 'rgba(255,255,255,.08)';
      for (let gx = 20; gx < w; gx += 34) {
        for (let gy = 20; gy < h; gy += 34) {
          let x = gx, y = gy;
          if (mouse) {
            const dx = gx - mouse.x, dy = gy - mouse.y, d = Math.hypot(dx, dy);
            if (d < 120) { const f = (1 - d / 120) * 18; x += dx / (d || 1) * f; y += dy / (d || 1) * f; }
          }
          ctx.fillRect(x, y, 1.6, 1.6);
        }
      }
      // espectro radial espelhado
      const n = bandas.length;
      ctx.lineCap = 'round';
      for (let i = 0; i < n * 2; i++) {
        const v = bandas[i < n ? i : n * 2 - 1 - i] || 0;
        const a = giro + i / (n * 2) * Math.PI * 2;
        const r1 = base, r2 = base + 6 + v * base * 1.05;
        ctx.strokeStyle = i % 2 ? c1 : c2;
        ctx.lineWidth = 4;
        ctx.globalAlpha = .35 + v * .65;
        ctx.beginPath(); ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1); ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2); ctx.stroke();
      }
      ctx.globalAlpha = 1;
      const nucleoG = ctx.createRadialGradient(cx, cy, 2, cx, cy, base * (.9 + rms * 4));
      nucleoG.addColorStop(0, '#fff'); nucleoG.addColorStop(.3, c1); nucleoG.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = nucleoG; ctx.beginPath(); ctx.arc(cx, cy, base * (.9 + rms * 4), 0, Math.PI * 2); ctx.fill();
      // fita de onda no rodapé
      const y0 = h * .86, nn = historicoOnda.length;
      ctx.beginPath();
      historicoOnda.forEach((v, i) => { const x = i / (nn - 1) * w, a = Math.min(1, v * 9) * h * .09 + 1; ctx.lineTo(x, y0 - a); });
      for (let i = nn - 1; i >= 0; i--) { const x = i / (nn - 1) * w, a = Math.min(1, historicoOnda[i] * 9) * h * .09 + 1; ctx.lineTo(x, y0 + a); }
      ctx.closePath(); ctx.fillStyle = c1; ctx.globalAlpha = .55; ctx.fill(); ctx.globalAlpha = 1;
      // marcas viajam junto com a fita (da direita para a esquerda)
      marcas.forEach(m => {
        m.idade += dt;
        const x = w - m.idade * (w / (nn / 21));
        if (x < 0) return;
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(x, y0 - h * .12); ctx.lineTo(x, y0 + h * .12); ctx.stroke();
        ctx.fillStyle = c2; ctx.beginPath(); ctx.arc(x, y0 - h * .12, 4, 0, Math.PI * 2); ctx.fill();
      });
      marcas = marcas.filter(m => w - m.idade * (w / (nn / 21)) > -10);
    }
    return { desenhar };
  })();

  /* ======================= momentos e cronômetro (aba Som) ======================= */
  const gvMedidor = $('#gv-medidor');
  for (let i = 0; i < 16; i++) gvMedidor.appendChild(document.createElement('i'));
  const listaMomentos = $('#gv-lista');
  let numMomentos = 0, tempoAudio = 0;
  const fmtTempo = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  function registrarMomento() {
    numMomentos++;
    listaMomentos.querySelector('.gv-vazio')?.remove();
    const li = document.createElement('li');
    li.textContent = `${fmtTempo(tempoAudio)} · pico ${Math.round(lim(pico, 0, 1) * 100)}%`;
    listaMomentos.prepend(li);
    while (listaMomentos.children.length > 12) listaMomentos.lastChild.remove();
    $('#gv-contagem').textContent = numMomentos;
  }
  function limparMomentos() {
    marcas = []; numMomentos = 0;
    listaMomentos.replaceChildren(Object.assign(document.createElement('li'), { className: 'gv-vazio', textContent: 'Nenhum momento marcado ainda' }));
    $('#gv-contagem').textContent = 0;
  }
  setInterval(() => {
    if (audioAtivo) tempoAudio += .1;
    $('#gv-tempo').textContent = fmtTempo(tempoAudio);
    $('#gv-decimo').textContent = '.' + (Math.floor(tempoAudio * 10) % 10);
  }, 100);

  /* ======================= foco (pomodoro) ======================= */
  let focoTotal = 25 * 60, focoResta = focoTotal, focoRodando = false, focoTimer = null;
  const fmt = s => String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
  function pintarFoco() {
    $('#foco-tempo').textContent = fmt(focoResta);
    $('#foco-sub').textContent = focoRodando ? 'Focando' : focoResta === focoTotal ? 'Pronto' : 'Pausado';
    $('#foco-play').innerHTML = focoRodando ? ICONE_PAUSA : ICONE_PLAY;
  }
  $('#foco-play').addEventListener('click', () => {
    focoRodando = !focoRodando;
    clearInterval(focoTimer);
    if (focoRodando) {
      falar(`Foco de ${Math.round(focoTotal / 60)} minutos. Eu seguro as pontas.`, 'sistema', 'calmo');
      focoTimer = setInterval(() => {
        focoResta = Math.max(0, focoResta - 1);
        if (!focoResta) {
          focoRodando = false; clearInterval(focoTimer); focoResta = focoTotal;
          falar('Foco concluído! Que tal uma pausa de 5 minutos?', 'sistema', 'alerta');
        }
        pintarFoco();
      }, 1000);
    }
    pintarFoco();
  });
  const ajustarFoco = d => { if (focoRodando) return; focoTotal = lim(focoTotal + d * 60, 5 * 60, 90 * 60); focoResta = focoTotal; pintarFoco(); };
  $('#foco-menos').addEventListener('click', () => ajustarFoco(-5));
  $('#foco-mais').addEventListener('click', () => ajustarFoco(5));
  pintarFoco();

  /* ======================= quadros (Moxen) ======================= */
  function enviar(quadro, dados) { if (quadro && quadro.contentWindow) quadro.contentWindow.postMessage(dados, '*'); }

  function enviarInicio(quadro) {
    if (!ponte) return;
    if (quadro.dataset.quadro === 'parrilla') {
      ponte.carregar('layout', t => enviar(quadro, { tipo: 'init', layout: t ? JSON.parse(t) : null }));
    } else if (quadro.dataset.quadro === 'eslabon') {
      ponte.carregar('diagrama', t => { const d = t ? JSON.parse(t) : {}; enviar(quadro, { tipo: 'init', flujo: d.flujo || null }); });
    }
    enviarMetricas();
  }

  window.addEventListener('message', ev => {
    const d = ev.data || {};
    const quadro = $$('iframe').find(f => f.contentWindow === ev.source);
    if (!quadro || !ponte) return;
    if (d.tipo === 'salvar') {
      clearTimeout(quadro._salvar);
      quadro._salvar = setTimeout(() => ponte.salvar(d.nome, d.dados), 350);
    } else if (d.tipo === 'acao') {
      ponte.acao(d.nome, !!d.valor);
    }
  });

  function enviarMetricas() {
    const e = estado;
    const dados = {
      energia: `${e.energia ?? 0}%`, atividade: `${e.atividade ?? 0}%`, estimulo: e.estimulacao ?? 0,
      energia_pct: `${e.energia ?? 0}%`, insatisfacao_pct: `${e.insatisfacao ?? 0}%`, atividade_pct: `${e.atividade ?? 0}%`,
      estimulo_pct: `${e.estimulacao ?? 0}%`, logs: e.logs || [],
    };
    $$('iframe[data-quadro="parrilla"]').forEach(f => enviar(f, { tipo: 'metricas', dados }));
  }

  /* ======================= chat local ======================= */
  const mensagens = $('#mensagens'), entrada = $('#entrada');
  const ehNuvem = m => /(:|-)cloud\b/i.test(m);

  function mostrarErro(texto, persistente = false) {
    const caixa = $('#erro');
    caixa.textContent = texto; caixa.hidden = false;
    clearTimeout(caixa._t);
    if (!persistente) caixa._t = setTimeout(() => { caixa.hidden = true; }, 7000);
  }

  function bolha(papel, texto) {
    const el = document.createElement('div');
    el.className = 'bolha ' + papel; el.textContent = texto;
    mensagens.appendChild(el); mensagens.scrollTop = mensagens.scrollHeight;
    return el;
  }

  function setOcupado(v) {
    respondendo = v;
    $('#enviar').disabled = v; $('#analisar').disabled = v; $('#parar').hidden = !v;
  }

  function enviarChat(texto, exibido) {
    const modelo = $('#modelo').value;
    if (!ponte || respondendo) return;
    if (!modelo) { mostrarErro('Nenhum modelo selecionado. Abra o Ollama e clique em Atualizar.'); return; }
    bolha('usuario', exibido || texto);
    historico.push({ role: 'user', content: texto });
    historico = historico.slice(-MAX_HISTORICO);
    bolhaAtual = bolha('assistente', '…'); textoAtual = '';
    setOcupado(true);
    ponte.enviar_chat(modelo, JSON.stringify(historico));
  }

  function enviarPelaCaixa() { const t = entrada.value.trim(); if (!t) return; entrada.value = ''; enviarChat(t); }
  $('#enviar').addEventListener('click', enviarPelaCaixa);
  entrada.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); enviarPelaCaixa(); } });
  $('#parar').addEventListener('click', () => { if (ponte) ponte.cancelar_chat(); });
  $('#atualizar').addEventListener('click', () => { if (ponte) ponte.listar_modelos(); });
  $('#ouvir').addEventListener('click', () => { if (ponte) ponte.ouvir(); });
  $('#analisar').addEventListener('click', () => {
    const contexto = { metricas: { energia: estado.energia, estimulacao: estado.estimulacao, insatisfacao: estado.insatisfacao,
      atividade: estado.atividade, emocao: estado.emocao, pausado: estado.pausado }, logs_recentes: (estado.logs || []).slice(-12) };
    enviarChat(PROMPT_ANALISE + JSON.stringify(contexto, null, 1), 'Analisar resultados do projeto');
  });
  $('#modelo').addEventListener('change', e => {
    localStorage.setItem('pestinha.modelo', e.target.value);
    $('#aviso-nuvem').hidden = !ehNuvem(e.target.value);
    if (ponte) ponte.definir_modelo(e.target.value);
    renderizarEscolha();
  });

  // Lista de modelos própria: fica dentro da ilha, então passar o mouse por ela não fecha nada.
  // O <select> oculto continua sendo a fonte da verdade (o resto do código lê dele).
  const escolhaBotao = $('#modelo-atual'), escolhaLista = $('#modelo-lista');
  function renderizarEscolha() {
    const sel = $('#modelo');
    const nomes = [...sel.options].map(o => ({ valor: o.value, texto: o.textContent }));
    escolhaLista.replaceChildren(...nomes.map(m => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.dataset.valor = m.valor;
      li.textContent = m.texto;
      li.setAttribute('aria-selected', String(m.valor === sel.value));
      li.classList.toggle('atual', m.valor === sel.value);
      li.classList.toggle('nuvem', ehNuvem(m.valor));
      return li;
    }));
    escolhaBotao.textContent = sel.value ? (ehNuvem(sel.value) ? sel.value + ' (nuvem)' : sel.value) : 'Sem modelo';
    escolhaBotao.classList.toggle('nuvem', ehNuvem(sel.value));
    escolhaBotao.disabled = !nomes.length;
    if (!nomes.length) escolhaLista.hidden = true;
  }
  escolhaBotao.addEventListener('click', e => {
    e.stopPropagation();
    const abre = escolhaLista.hidden;
    escolhaLista.hidden = !abre;
    escolhaBotao.setAttribute('aria-expanded', String(abre));
  });
  escolhaLista.addEventListener('click', e => {
    const li = e.target.closest('li');
    if (!li) return;
    const sel = $('#modelo');
    sel.value = li.dataset.valor;
    sel.dispatchEvent(new Event('change'));
    escolhaLista.hidden = true;
    escolhaBotao.setAttribute('aria-expanded', 'false');
  });
  document.addEventListener('click', e => {
    if (!$('#escolha').contains(e.target)) { escolhaLista.hidden = true; escolhaBotao.setAttribute('aria-expanded', 'false'); }
  });

  function aoModelos(lista) {
    modelos = Array.isArray(lista) ? lista : [];
    const sel = $('#modelo'), salvo = localStorage.getItem('pestinha.modelo');
    sel.innerHTML = '';
    modelos.forEach(m => { const o = document.createElement('option'); o.value = m; o.textContent = ehNuvem(m) ? m + ' (nuvem)' : m; sel.appendChild(o); });
    const local = modelos.find(m => !ehNuvem(m));
    if (salvo && modelos.includes(salvo)) sel.value = salvo; else if (local) sel.value = local;
    sel.disabled = !modelos.length;
    $('#aviso-nuvem').hidden = !ehNuvem(sel.value);
    if (ponte && sel.value) ponte.definir_modelo(sel.value);
    renderizarEscolha();
    if (modelos.length) $('#erro').hidden = true;
    else mostrarErro('Nenhum modelo instalado encontrado no Ollama local.', true);
  }

  // Voz: perguntou falando, a resposta também é falada (voz do LLM; sem ela, a do Windows)
  let veioDeVoz = false;
  function aoModeloVoz(s) {
    const caixa = $('#voz-baixar');
    if (s === 'ausente') { caixa.hidden = false; $('#voz-baixar-bt').disabled = false; $('#voz-progresso').textContent = ''; }
    else if (s === 'baixando') { caixa.hidden = false; $('#voz-baixar-bt').disabled = true; $('#voz-progresso').textContent = '0%'; }
    else if (s === 'pronto') { caixa.hidden = true; falar('Modelo de voz pronto. Clique em Falar e pergunte.', 'sistema', 'calmo'); }
    else { $('#voz-baixar-bt').disabled = false; mostrarErro(s); }
  }
  $('#voz-baixar-bt').addEventListener('click', () => { if (ponte) ponte.baixar_modelo_voz(); });

  function aoToken(t) {
    vibra.pulsar(.5);
    if (!bolhaAtual) return;
    textoAtual += t; bolhaAtual.textContent = textoAtual;
    mensagens.scrollTop = mensagens.scrollHeight;
  }

  function aoFim() {
    if (bolhaAtual && textoAtual) {
      historico.push({ role: 'assistant', content: textoAtual });
      historico = historico.slice(-MAX_HISTORICO);
      if (($('#ler').checked || veioDeVoz) && ponte) {
        ponte.falar_resposta($('#modelo').value, textoAtual);   // o Python escolhe o modelo que sabe falar
      }
      if (!aberta || vista !== 'chat') falar('Respondi no chat, quer dar uma olhada?', 'sistema', 'calmo');
    } else if (bolhaAtual) bolhaAtual.remove();
    bolhaAtual = null;
    veioDeVoz = false;
    setOcupado(false);
  }

  function aoErro(texto) {
    mostrarErro(texto, /desconectad/i.test(texto));
    alertaAte = performance.now() + 3000;
    if (respondendo && bolhaAtual && !textoAtual) { bolhaAtual.remove(); bolhaAtual = null; }
  }

  /* ======================= reações do pet (aba Diagramas) ======================= */
  // Cada reação: gatilho -> fala inicial -> espera -> se você reagir (sim) ou não (não), fala e ação.
  // Montado com DOM (sem innerHTML) porque o texto vem do usuário; o Python valida tudo ao salvar.
  const reacoes = (() => {
    const lista = $('#lista-reacoes');
    let dados = { ia: true, regras: [], gatilhos: {}, acoes: {} };
    let salvarT = null;

    const el = (tag, classe, texto) => {
      const e = document.createElement(tag);
      if (classe) e.className = classe;
      if (texto != null) e.textContent = texto;
      return e;
    };
    const salvarDepois = () => { clearTimeout(salvarT); salvarT = setTimeout(enviar, 300); };
    function enviar() {
      if (ponte) ponte.salvar('reacoes', JSON.stringify({ ia: dados.ia, regras: dados.regras }));
    }
    function selecao(mapa, atual, aoMudar) {
      const s = el('select');
      Object.entries(mapa || {}).forEach(([k, v]) => { const o = el('option', '', v); o.value = k; o.selected = k === atual; s.appendChild(o); });
      s.addEventListener('change', () => { aoMudar(s.value); salvarDepois(); });
      return s;
    }
    function texto(valor, aoMudar, dica) {
      const i = el('input');
      i.type = 'text'; i.value = valor || ''; i.maxLength = 160; i.placeholder = dica;
      i.addEventListener('input', () => { aoMudar(i.value.trim()); salvarDepois(); });
      return i;
    }
    function ramo(classe, rotulo, dadosRamo) {
      const box = el('div', `ramo ${classe}`);
      box.appendChild(el('span', 'tag', rotulo));
      box.appendChild(texto(dadosRamo.texto, t => { dadosRamo.texto = t; }, classe === 'sim' ? 'Fala se você reagir' : 'Fala se você não reagir'));
      const linha = el('div', 'linha');
      linha.appendChild(selecao(dados.acoes, dadosRamo.acao, a => { dadosRamo.acao = a; }));
      box.appendChild(linha);
      return box;
    }
    function cartao(regra) {
      const art = el('article', 'regra' + (regra.ativa ? '' : ' desligada'));
      const topo = el('div', 'regra-topo');
      const ativa = el('label', 'marca');
      const chk = el('input'); chk.type = 'checkbox'; chk.checked = !!regra.ativa;
      chk.addEventListener('change', () => { regra.ativa = chk.checked; art.classList.toggle('desligada', !chk.checked); salvarDepois(); });
      ativa.append(chk, ' ativa');
      const espera = el('label', 'espera', 'espera ');
      const seg = el('input'); seg.type = 'number'; seg.min = 5; seg.max = 120; seg.value = regra.espera;
      seg.addEventListener('change', () => { regra.espera = lim(Number(seg.value) || 20, 5, 120); seg.value = regra.espera; salvarDepois(); });
      espera.append(seg, ' s');
      const remover = el('button', 'pilula remover', 'Remover');
      remover.type = 'button';
      remover.addEventListener('click', () => { dados.regras = dados.regras.filter(r => r !== regra); render(); salvarDepois(); });
      topo.append(ativa, selecao(dados.gatilhos, regra.gatilho, g => { regra.gatilho = g; }), espera, remover);

      const fluxo = el('div', 'fluxo');
      const inicio = el('div', 'inicio');
      inicio.appendChild(el('span', 'tag', 'Quando acontece'));
      inicio.appendChild(texto(regra.texto, t => { regra.texto = t; }, 'Fala inicial (vazio = fala normal do pet)'));
      const linha = el('div', 'linha');
      linha.appendChild(selecao({ calmo: 'Tom calmo', alerta: 'Tom de alerta' }, regra.tom, t => { regra.tom = t; }));
      const vozL = el('label', 'marca');
      const vz = el('input'); vz.type = 'checkbox'; vz.checked = !!regra.voz;
      vz.addEventListener('change', () => { regra.voz = vz.checked; salvarDepois(); });
      vozL.append(vz, ' em voz');
      linha.appendChild(vozL);
      inicio.appendChild(linha);
      const ramos = el('div', 'ramos');
      ramos.append(ramo('sim', 'Se eu reagir', regra.sim), ramo('nao', 'Se não reagir', regra.nao));
      fluxo.append(inicio, el('div', 'seta'), ramos);

      art.append(topo, fluxo);
      return art;
    }
    function render() { lista.replaceChildren(...dados.regras.map(cartao)); }
    function nova() {
      dados.regras.push({ id: 'r' + Date.now().toString(36), gatilho: 'bravo', ativa: true, texto: '', tom: 'calmo', voz: false,
        espera: 20, sim: { texto: '', acao: 'carinho' }, nao: { texto: '', acao: 'falar' } });
      render(); salvarDepois();
      if (lista.lastElementChild) lista.lastElementChild.scrollIntoView({ block: 'nearest' });
    }
    function carregar(bruto) {
      try { dados = JSON.parse(bruto); } catch (_) { return; }
      dados.regras = Array.isArray(dados.regras) ? dados.regras : [];
      $('#ia-falas').checked = dados.ia !== false;
      render();
    }
    $('#ia-falas').addEventListener('change', e => { dados.ia = e.target.checked; salvarDepois(); });
    $('#nova-reacao').addEventListener('click', nova);
    return { carregar };
  })();

  function mostrarFluxo(modo) {
    $$('[data-fluxo]').forEach(b => b.classList.toggle('ligada', b.dataset.fluxo === modo));
    $('#lista-reacoes').hidden = modo !== 'reacoes';
    $('#nova-reacao').hidden = modo !== 'reacoes';
    $('#marca-ia').hidden = modo !== 'reacoes';
    const quadro = $('[data-quadro="eslabon"]');
    quadro.hidden = modo !== 'livre';
    if (modo === 'livre') carregarQuadro(quadro);
  }
  $$('[data-fluxo]').forEach(b => b.addEventListener('click', () => mostrarFluxo(b.dataset.fluxo)));

  /* ======================= laço de animação ======================= */
  function redimensionarCanvases() { grafico.desenhar(); desenharSomMini(); }
  window.addEventListener('resize', redimensionarCanvases);

  let ultimo = performance.now(), ultimoOrbe = 0;
  function quadro(t) {
    const dt = lim((t - ultimo) / 1000, 0, .05);
    ultimo = t;
    const humor = atualizarCores();
    // recolhida e sem balão, o orbe anima a 30 fps: a mesma respiração, metade do trabalho
    const ocioso = !aberta && !balaoOcupado && !respondendo && !pensandoNarrador;
    if (!ocioso || t - ultimoOrbe >= 1000 / 30) {
      orbe.desenhar(humor, lim((t - (ultimoOrbe || t)) / 1000, 0, .1));
      ultimoOrbe = t;
    }
    if (aberta) avatar.copiar();
    if (aberta && vista === 'home') { grafico.desenhar(); desenharSomMini(); }
    if (aberta && vista === 'som') estudio.desenhar(dt);
    if (aberta && vista === 'chat') vibra.desenhar(dt);
    requestAnimationFrame(quadro);
  }
  requestAnimationFrame(quadro);
  aplicarForma();

  /* ======================= ponte com o Python ======================= */
  if (window.QWebChannel && window.qt) {
    new QWebChannel(qt.webChannelTransport, canal => {
      ponte = canal.objects.ponte;
      ponte.modo_inicial(m => aplicarModo(m !== 'livre'));
      ponte.modo_mudou.connect(m => aplicarModo(m !== 'livre'));
      ponte.aparencia_pet(s => mascote.configurar(JSON.parse(s)));
      ponte.estado.connect(s => aplicarEstado(JSON.parse(s)));
      ponte.aviso.connect(s => { const a = JSON.parse(s); falar(a.texto, a.origem, a.tom); });
      ponte.narrador_estado.connect(s => { pensandoNarrador = s === 'pensando'; });
      ponte.niveis.connect(s => aoReceberNiveis(JSON.parse(s)));
      ponte.audio_estado.connect(aoEstadoAudio);
      ponte.modelos.connect(s => aoModelos(JSON.parse(s)));
      ponte.token.connect(aoToken);
      ponte.chat_fim.connect(aoFim);
      ponte.erro.connect(aoErro);
      ponte.transcrito.connect(texto => { veioDeVoz = true; entrada.value = texto; enviarPelaCaixa(); });
      ponte.envelope.connect(s => vibra.falar(JSON.parse(s), 'modelo'));
      ponte.voz_estado.connect(s => { $('#ouvir').textContent = s === 'ouvindo' ? 'Ouvindo… (clique p/ parar)' : s === 'transcrevendo' ? 'Entendendo…' : 'Falar'; });
      ponte.voz_modelo.connect(aoModeloVoz);
      ponte.voz_download.connect(p => { $('#voz-progresso').textContent = p + '%'; });
      ponte.obter_estado(s => aplicarEstado(JSON.parse(s)));
      ponte.listar_modelos();
      ponte.carregar('reacoes', t => reacoes.carregar(t));
      informarRegiao(mola.w, mola.h);
      setTimeout(() => falar(`Núcleo online. Estou de olho no ${estado.pet || 'Pestinha'}.`, 'sistema', 'calmo'), 900);
    });
  }

  mostrarFluxo('reacoes');
  window.nucleoDebug = { abrir, mostrarVista, falar, niveis: aoReceberNiveis, audio: aoEstadoAudio, modelos: aoModelos, agendar: agendarRecolher, controles: atualizarControles, marcar: () => $("#estudio").dispatchEvent(new MouseEvent("click")) };   // testes e capturas
})();
