/* =====================================================================
   Eslabón · Moxen
   Un constructor de automatizaciones en vertical: un disparador, los pasos que le siguen y, si hace falta,
   una bifurcación. Se EDITA (no solo se mira): se insertan pasos, se parte el cable en dos ramas y los datos
   de cada paso viajan al siguiente como píldoras.

   · Entre cada par de nodos hay un «+». Se abre en un menú de pasos (filtrar, transformar, esperar, enviar
     aviso, «Si…»): se filtra escribiendo, se elige con las flechas o con el ratón. El nodo nuevo entra y
     empuja a los de abajo con resorte, y su cable se dibuja.
   · «Si…» parte el cable en dos ramas que se separan: lo que venía detrás pasa a la rama «Sí» y la rama
     «No» nace vacía, con su propio «+».
   · Cada paso se configura en el panel de la derecha. Los datos de los pasos anteriores aparecen allí como
     píldoras: se ARRASTRAN a un campo (el fantasma sigue al puntero con resorte y se inclina con la
     velocidad), se tocan para insertarlas, o se eligen escribiendo «@» dentro del campo.
   · «Testar» envía un evento de ejemplo. Un pulso baja por el cable dejando tinta violeta, cada nodo se
     enciende al recibirlo y deja su salida en una ficha plegable, y todo termina en ✓. Si un paso falla,
     el pulso se detiene allí: el nodo se abre en su error y el panel señala el campo.
   · Teclado: ↑ ↓ percorrem nodos y «+» (un solo tope de tabulación), Enter elige o abre, Supr quita el paso.
     Con movimiento reducido todo cambia de golpe y se anuncia igual.

   Montaje (se inicia con la llamada de index.html; el HTML de esta demo es la plantilla):
     const e = Eslabon(document.querySelector('[data-eslabon]'), {
       flujo: FLUJO,                    // el flujo de partida (mira el formato justo abajo)
       alCambiar: ({ flujo }) => {},    // cada vez que cambia la estructura o un campo: lo que guardarías
       alTestar: ({ ok, pasos, ms, falla }) => {},      // al terminar la prueba
     });
     e.inserta('esperar', 1);   e.probar();   e.restablece();

   Qué cambia qué: FLUJO (cada paso: { id, tipo, campos }; «si» lleva `ramas: [[…], […]]`), TIPOS (los
   pasos que ofrece el menú) y EVENTOS (los datos de ejemplo del disparador); los colores, al principio de
   eslabon.css (--es-violeta es todo lo que se ejecuta con éxito, --es-ambar el pulso y los avisos).
   Sin dependencias; el tiempo viene de requestAnimationFrame, timers, Web Animations y transiciones CSS
   (nada de Date): la página y el vídeo coinciden.
   ===================================================================== */
(function () {
  'use strict';

  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  const quieto = () => mq.matches;
  const lim = (v, a, b) => Math.max(a, Math.min(b, v));
  const SVGNS = 'http://www.w3.org/2000/svg';

  /* Un resorte convertido en curva `linear()`: sirve para CSS y para Web Animations. */
  function muelle(k, c) {
    const pts = [0];
    let x = 0, v = 0, t = 0;
    while (t < 3) {
      v += (k * (1 - x) - c * v) / 240; x += v / 240; t += 1 / 240;
      pts.push(x);
      if (t > .15 && Math.abs(1 - x) < .001 && Math.abs(v) < .01) break;
    }
    const out = [];
    for (let i = 0; i <= 40; i++) out.push(pts[Math.round(i / 40 * (pts.length - 1))].toFixed(4));
    out[40] = '1';
    return 'linear(' + out.join(', ') + ')';
  }
  const h = (tag, clase, texto) => { const e = document.createElement(tag); if (clase) e.className = clase; if (texto != null) e.textContent = texto; return e; };
  const sv = (tag, clase) => { const e = document.createElementNS(SVGNS, tag); if (clase) e.setAttribute('class', clase); return e; };
  const norm = s => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const plural = (n, u, p) => n + ' ' + (n === 1 ? u : p);
  const suave = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const fmt = v => typeof v === 'number' ? String(v).replace('.', ',') : String(v);
  const muestra = v => typeof v === 'string' ? '"' + v + '"' : fmt(v);
  const copia = o => JSON.parse(JSON.stringify(o));

  /* ── medidas (el CSS las recibe como variables) ───────────────────── */
  const NODO_H = 60, GAP = 40, FORK = 90, TAIL = 34, FIN_H = 10, PAD_T = 30;
  const CHIP_M = 7, CHIP_H = 22, FICHA_M = 6, FILA = 18, FICHA_P = 14, ERR_H = 60;
  let W = 300, SEP = 170;

  /* ── los pasos que existen ────────────────────────────────────────── */
  const TIPOS = {
    disparador: { nom: 'Pedido recebido', ic: 'rayo', alias: 'pedido', desc: 'Dispara a cada pedido novo da loja.' },
    filtrar: { nom: 'Filtrar', ic: 'filtro', alias: 'filtro', desc: 'Continua só se uma condição for cumprida.', menu: 'Continua só se for cumprido' },
    transformar: { nom: 'Transformar', ic: 'cambio', alias: 'formato', desc: 'Muda o formato de um dado.', menu: 'Formata um dado' },
    esperar: { nom: 'Esperar', ic: 'reloj', alias: 'espera', desc: 'Detiene el flujo durante un rato.', menu: 'Pausa el flujo un rato' },
    avisar: { nom: 'Enviar aviso', ic: 'avion', alias: 'aviso', desc: 'Envia uma mensagem por e-mail.', menu: 'Envia um e-mail' },
    si: { nom: 'Se…', ic: 'rama', alias: 'condicion', desc: 'Divide o fluxo em dois ramos, Sim e Não.', menu: 'Divide o fio em dois ramos' },
  };
  const EN_MENU = ['filtrar', 'transformar', 'esperar', 'avisar', 'si'];
  const OPS = [{ k: 'mayor', et: 'mayor que', s: '>' }, { k: 'menor', et: 'menor que', s: '<' }, { k: 'igual', et: 'igual a', s: '=' }];
  const FORMATOS = [{ k: 'dec', et: '2 casas decimais' }, { k: 'ent', et: 'Inteiro' }, { k: 'may', et: 'Maiúsculas' }];
  const UNIDADES = [{ k: 'min', et: 'min', l: 'minutos' }, { k: 'h', et: 'horas', l: 'horas' }, { k: 'd', et: 'dias', l: 'dias' }];
  const CAMPOS = {
    disparador: [{ k: 'evento', t: 'fijo', et: 'Evento' }, { k: 'origen', t: 'fijo', et: 'Origen' }],
    filtrar: [{ k: 'dato', t: 'slot', et: 'Dado', ph: 'Arraste um dado aqui' }, { k: 'op', t: 'seg', et: 'Deve ser', opts: OPS }, { k: 'valor', t: 'texto', et: 'Valor' }],
    si: [{ k: 'dato', t: 'slot', et: 'Se o dado', ph: 'Arraste um dado aqui' }, { k: 'op', t: 'seg', et: 'É', opts: OPS }, { k: 'valor', t: 'texto', et: 'Valor' }],
    transformar: [{ k: 'dato', t: 'slot', et: 'Dado', ph: 'Arraste um dado aqui' }, { k: 'formato', t: 'seg', et: 'Formato', opts: FORMATOS }],
    esperar: [{ k: 'cantidad', t: 'texto', et: 'Cantidad', num: true }, { k: 'unidad', t: 'seg', et: 'Unidad', opts: UNIDADES }],
    avisar: [{ k: 'para', t: 'multi', et: 'Para', ph: 'E-mail do destinatário' }, { k: 'asunto', t: 'multi', et: 'Assunto', ph: 'Assunto do e-mail' }, { k: 'mensaje', t: 'multi', et: 'Mensagem', ph: 'Digite ou use @', alto: true }],
  };
  const defaultsDe = tipo => ({
    disparador: { evento: 'pedido.criado', origen: 'Loja online' },
    filtrar: { dato: [], op: 'mayor', valor: '0' },
    transformar: { dato: [], formato: 'dec' },
    esperar: { cantidad: '10', unidad: 'min' },
    avisar: { para: [], asunto: [], mensaje: [] },
    si: { dato: [], op: 'mayor', valor: '100' },
  }[tipo]);

  // los datos de ejemplo que entrega el disparador («Sem e-mail» hace fallar el aviso)
  const EVENTOS = {
    completo: { id: 'ped_4821', total: 128.5, articulos: 3, correo: 'cliente@ejemplo.dev' },
    sin: { id: 'ped_4822', total: 128.5, articulos: 3, correo: '' },
  };

  // el flujo de partida
  const FLUJO = [
    { id: 'disp', tipo: 'disparador' },
    { id: 'forma', tipo: 'transformar', campos: { dato: [{ ref: 'pedido.total' }], formato: 'dec' } },
    { id: 'aviso', tipo: 'avisar', campos: {
      para: [{ ref: 'pedido.correo' }],
      asunto: ['Pedido ', { ref: 'pedido.id' }, ' recebido'],
      mensaje: ['Total ', { ref: 'formato.texto' }, '.'] } },
  ];

  const IC = {
    rayo: '<svg viewBox="0 0 24 24"><path d="M13.2 3.4 5.6 13.4h5.3l-.9 7.2 7.6-10.1h-5.3z"/></svg>',
    filtro: '<svg viewBox="0 0 24 24"><path d="M4.6 5.8h14.8l-5.6 6.7v4.8l-3.6 1.9v-6.7z"/></svg>',
    cambio: '<svg viewBox="0 0 24 24"><path d="M4.5 8.2h12.6M13.6 4.7l3.5 3.5-3.5 3.5M19.5 15.8H6.9M10.4 12.3l-3.5 3.5 3.5 3.5"/></svg>',
    reloj: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.2"/><path d="M12 7.4V12l3.2 2"/></svg>',
    avion: '<svg viewBox="0 0 24 24"><path d="M20.4 4.2 3.7 10.6l6.4 2.6 2.6 6.4zM10.1 13.2l5.6-5"/></svg>',
    rama: '<svg viewBox="0 0 24 24"><path d="M12 4.2v5.4M12 9.6c0 3.4-6 2.6-6 7.4M12 9.6c0 3.4 6 2.6 6 7.4"/><circle cx="6" cy="18.4" r="1.7"/><circle cx="18" cy="18.4" r="1.7"/></svg>',
    mas: '<svg viewBox="0 0 24 24"><path d="M12 6.2v11.6M6.2 12h11.6"/></svg>',
    x: '<svg viewBox="0 0 24 24"><path d="M7.5 7.5l9 9M16.5 7.5l-9 9"/></svg>',
    chev: '<svg viewBox="0 0 24 24"><path d="M7 10l5 5 5-5"/></svg>',
    lupa: '<svg viewBox="0 0 24 24"><circle cx="10.6" cy="10.6" r="5.4"/><path d="m15 15 4.2 4.2"/></svg>',
    basura: '<svg viewBox="0 0 24 24"><path d="M5.5 7.5h13M10 7.5V5.6h4v1.9M7.3 7.5l.8 11h7.8l.8-11M10.3 11v4.8M13.7 11v4.8"/></svg>',
    grip: '<svg viewBox="0 0 24 24"><circle cx="9" cy="6.5" r="1.4"/><circle cx="15" cy="6.5" r="1.4"/><circle cx="9" cy="12" r="1.4"/><circle cx="15" cy="12" r="1.4"/><circle cx="9" cy="17.5" r="1.4"/><circle cx="15" cy="17.5" r="1.4"/></svg>',
    est: '<svg viewBox="0 0 24 24"><circle class="e-giro" cx="12" cy="12" r="8.6"/><g class="e-ok"><circle cx="12" cy="12" r="10.4"/><path d="M7.2 12.4l3.5 3.5 6.2-7" pathLength="1"/></g><g class="e-adv"><circle cx="12" cy="12" r="10.4"/><path d="M12 7.4v5.6M12 16.4v.2"/></g><g class="e-stop"><circle cx="12" cy="12" r="10.4"/><path d="M8 12h8"/></g></svg>',
    tilde: '<svg viewBox="0 0 24 24"><path d="M6.6 12.6l3.8 3.8 7.2-8.2" pathLength="1"/></svg>',
  };

  function Eslabon(raiz, opciones) {
    const op = Object.assign({ flujo: FLUJO, alCambiar: null, alTestar: null }, opciones);
    const $ = (s, r) => (r || raiz).querySelector(s);
    const el = {
      lienzo: $('[data-lienzo]'), mundo: $('[data-mundo]'), cables: $('[data-cables]'), pulso: $('[data-pulso]'), panel: $('[data-panel]'), pista: $('[data-pista]'),
      estado: $('[data-estado]'), estadoTxt: $('[data-estado-txt]'), probar: $('[data-probar]'), probarTxt: $('[data-probar-txt]'), reset: $('[data-reset]'),
      segEvento: $('[data-seg-evento]'), vivo: $('[data-vivo]'),
    };
    const EASE = muelle(260, 22);
    raiz.style.setProperty('--es-muelle', muelle(380, 17));
    raiz.style.setProperty('--es-blando', muelle(210, 20));
    raiz.style.setProperty('--es-nodo-h', NODO_H + 'px');
    const anuncia = t => { el.vivo.textContent = ''; setTimeout(() => { el.vivo.textContent = t; }, 30); };

    const E = { arrancando: true, seq: [], sel: null, evento: 'completo', run: null, menu: null, spawn: new Map(), errCampo: null, campoAct: null, arroba: null, foco: null };
    let uid = 0, cons = [], lista = [];
    const porId = new Map(), dom = new Set(), conRec = new Map();
    let raf = 0, ultimo = 0;
    const despierta = () => { if (!raf) raf = requestAnimationFrame(bucle); };

    /* ── el modelo ────────────────────────────────────────────────────── */
    function nuevoItem(it) {
      return Object.assign({ x: 0, y: 0, h: 0, vx: 0, vy: 0, vh: 0, tx: 0, ty: 0, th: 0, fresco: true, el: null, est: 'idle' }, it);
    }
    function creaNodo(tipo, id) {
      const n = nuevoItem({ it: 'nodo', id: id || 'n' + (++uid), tipo, campos: defaultsDe(tipo), cola: {}, salida: null, alias: '' });
      if (tipo === 'si') n.ramas = [{ etq: 'Sim', seq: [] }, { etq: 'Não', seq: [] }];
      porId.set(n.id, n);
      return n;
    }
    const nuevaFin = () => nuevoItem({ it: 'fin', id: 'f' + (++uid), h: FIN_H, th: FIN_H });

    // todos los nodos en el orden en que se ven (primero la rama Sí, luego la No)
    function todos(seq, out) {
      out = out || []; seq = seq || E.seq;
      seq.forEach(n => { out.push(n); if (n.ramas) n.ramas.forEach(r => todos(r.seq, out)); });
      return out;
    }
    function secuencias(seq, out) {
      out = out || []; seq = seq || E.seq; out.push(seq);
      seq.forEach(n => { if (n.ramas) n.ramas.forEach(r => secuencias(r.seq, out)); });
      return out;
    }
    function ubica(n) {
      for (const s of secuencias()) { const i = s.indexOf(n); if (i >= 0) return { seq: s, idx: i, prof: s === E.seq ? 0 : 1 }; }
      return null;
    }
    // los pasos que ya se ejecutaron cuando llega el turno de n (de ahí salen los datos disponibles)
    function previos(n) {
      const busca = (seq, acc) => {
        for (const x of seq) {
          if (x === n) return acc;
          acc = acc.concat(x);
          if (x.ramas) for (const r of x.ramas) { const f = busca(r.seq, acc); if (f) return f; }
        }
        return null;
      };
      return busca(E.seq, []) || [];
    }
    function aliasUnico(tipo) {
      const base = TIPOS[tipo].alias, usados = new Set(todos().map(x => x.alias));
      if (!usados.has(base)) return base;
      let i = 2; while (usados.has(base + i)) i++;
      return base + i;
    }

    // construye el flujo a partir de su definición; si un id ya existía, reutiliza el nodo (así vuelve con resorte)
    function construye(defs) {
      return defs.map(d => {
        const n = porId.get(d.id) || creaNodo(d.tipo, d.id);
        n.campos = Object.assign(defaultsDe(d.tipo), copia(d.campos || {}));
        n.cola = {}; n.est = 'idle'; n.salida = null;
        if (d.tipo === 'si') n.ramas = (d.ramas || [[], []]).map((r, j) => ({ etq: j ? 'Não' : 'Sim', seq: construye(r) }));
        return n;
      });
    }
    function flujoInicial() {
      const finViejo = secuencias().map(s => s.fin).find(Boolean) || null;   // el punto del final se reutiliza, para que no parpadee
      const seq = construye(op.flujo);
      const usados = new Set();                                              // los alias se asignan en orden
      todos(seq).forEach(n => { const base = TIPOS[n.tipo].alias; let a = base, i = 2; while (usados.has(a)) a = base + (i++); usados.add(a); n.alias = a; });
      seq.fin = finViejo;
      return seq;
    }

    /* ── lo que vale un dato ──────────────────────────────────────────── */
    function refValor(ref, ctx) {
      const i = ref.indexOf('.'), a = ref.slice(0, i), c = ref.slice(i + 1);
      return ctx[a] && c in ctx[a] ? ctx[a][c] : undefined;
    }
    function resuelve(ps, cola, ctx) {
      let texto = ''; const rotas = [];
      ps.forEach(p => {
        if (typeof p === 'string') texto += p;
        else { const v = refValor(p.ref, ctx); if (v === undefined) rotas.push(p.ref); else texto += fmt(v); }
      });
      return { texto: texto + (cola || ''), rotas };
    }
    function ejemploSalida(n) {
      const ev = EVENTOS[E.evento];
      switch (n.tipo) {
        case 'disparador': return Object.assign({}, ev);
        case 'filtrar': return { pasa: true };
        case 'transformar': return { texto: formatea(ev.total, n.campos.formato) };
        case 'esperar': return { esperado: n.campos.cantidad + ' ' + n.campos.unidad };
        case 'avisar': return { enviado: true, id: 'msg_91c2' };
        case 'si': return { resultado: true, rama: 'Sim' };
      }
      return {};
    }
    function formatea(v, f) {
      const x = Number(v);
      if (f === 'may') return String(v).toUpperCase();
      if (!isFinite(x)) return String(v);
      return f === 'ent' ? String(Math.round(x)) : x.toFixed(2).replace('.', ',');
    }
    function compara(opk, l, r) {
      const a = Number(l), b = Number(String(r).replace(',', '.'));
      if (isFinite(a) && isFinite(b) && String(r).trim() !== '') return opk === 'mayor' ? a > b : opk === 'menor' ? a < b : a === b;
      const s = String(l), t = String(r);
      return opk === 'mayor' ? s > t : opk === 'menor' ? s < t : s === t;
    }
    const OPS_S = Object.fromEntries(OPS.map(o => [o.k, o.s]));
    const refsDe = n => { const s = new Set(); previos(n).forEach(p => Object.keys(ejemploSalida(p)).forEach(k => s.add(p.alias + '.' + k))); return s; };
    const rota = (n, ref) => !refsDe(n).has(ref);

    // lo que hace un paso con los datos que le llegan: su salida, o por qué falla
    function ejecuta(n, ctx, ev) {
      const C = n.campos, T = n.tipo;
      const dato = () => {
        if (!C.dato.length) return { err: 'Escolha el dato que se compara.', campo: 'dato' };
        const v = refValor(C.dato[0].ref, ctx);
        return v === undefined ? { err: 'Não há «' + C.dato[0].ref + '» antes deste passo.', campo: 'dato' } : { v };
      };
      if (T === 'disparador') return { ok: true, dur: .16, ms: 3, salida: Object.assign({}, ev) };
      if (T === 'filtrar' || T === 'si') {
        const d = dato(); if (d.err) return { ok: false, dur: .24, msg: d.err, campo: d.campo };
        const pasa = compara(C.op, d.v, C.valor);
        if (T === 'si') return { ok: true, dur: .2, ms: 5, rama: pasa ? 0 : 1, salida: { resultado: pasa, rama: pasa ? 'Sim' : 'Não' } };
        return pasa ? { ok: true, dur: .24, ms: 12, salida: { pasa: true } } : { ok: true, stop: true, dur: .24, ms: 12, salida: { pasa: false } };
      }
      if (T === 'transformar') {
        const d = dato(); if (d.err) return { ok: false, dur: .24, msg: d.err, campo: d.campo };
        return { ok: true, dur: .18, ms: 8, salida: { texto: formatea(d.v, C.formato) } };
      }
      if (T === 'esperar') {
        if (!(Number(C.cantidad) > 0)) return { ok: false, dur: .24, msg: 'A quantidade precisa ser um número maior que zero.', campo: 'cantidad' };
        return { ok: true, dur: .55, ms: 600, salida: { esperado: C.cantidad + ' ' + C.unidad } };
      }
      if (T === 'avisar') {
        const res = {};
        for (const k of ['para', 'asunto', 'mensaje']) {
          res[k] = resuelve(C[k], n.cola[k], ctx);
          if (res[k].rotas.length) return { ok: false, dur: .3, msg: 'Não há «' + res[k].rotas[0] + '» antes deste passo.', campo: k };
        }
        if (!res.para.texto.trim()) {
          const t = C.para.find(p => typeof p !== 'string');
          return { ok: false, dur: .3, msg: t ? '«Para» chegou vazio: ' + t.ref + ' não traz valor.' : 'Falta o destinatário em «Para».', campo: 'para' };
        }
        return { ok: true, dur: .24, ms: 140, salida: { enviado: true, id: 'msg_91c2', para: res.para.texto } };
      }
      return { ok: true, dur: .2, ms: 1, salida: {} };
    }
    function incompleto(n) {
      const C = n.campos;
      if (n.tipo === 'filtrar' || n.tipo === 'si' || n.tipo === 'transformar') return !C.dato.length;
      if (n.tipo === 'avisar') return !C.para.length && !(n.cola.para || '').trim();
      return false;
    }
    const lee = (ps, cola) => ps.map(p => typeof p === 'string' ? p : p.ref).join('') + (cola || '');
    function resumenDe(n) {
      const C = n.campos;
      switch (n.tipo) {
        case 'disparador': return { t: C.evento };
        case 'filtrar': case 'si': return C.dato.length ? { t: C.dato[0].ref + ' ' + OPS_S[C.op] + ' ' + (C.valor || '…') } : { t: 'Escolha um dado', v: true };
        case 'transformar': return C.dato.length ? { t: C.dato[0].ref + ' → ' + FORMATOS.find(f => f.k === C.formato).et.toLowerCase() } : { t: 'Escolha um dado', v: true };
        case 'esperar': return { t: (C.cantidad || '…') + ' ' + UNIDADES.find(u => u.k === C.unidad).l };
        case 'avisar': { const p = lee(C.para, n.cola.para); return p ? { t: 'Para ' + p } : { t: 'Falta o destinatário', v: true }; }
      }
      return { t: '' };
    }

    /* ── la disposición: dónde va cada cosa ───────────────────────────── */
    const alto = n => {
      if (n.it === 'fin') return FIN_H;
      const s = n.salida;
      if (!s) return NODO_H;
      if (s.error) return NODO_H + ERR_H;
      return NODO_H + CHIP_M + CHIP_H + (s.abierta ? FICHA_M + s.filas.length * FILA + FICHA_P : 0);
    };
    function coloca(it, x, y) {
      it.tx = x; it.ty = y; it.th = alto(it);
      if (it.fresco) {
        const p = E.arrancando ? null : it.spawnDe; it.fresco = false;
        if (p) { it.x = p.tx; it.y = p.ty + p.th; } else { it.x = x; it.y = y; }
        it.h = it.th; it.vx = it.vy = it.vh = 0;
      }
    }
    function dispone(seq, cx, y, ent) {
      let yy = y, prev = null;
      const enlaza = (de, a, extra) => cons.push(Object.assign({ de, a, seq }, extra));
      seq.forEach((n, i) => {
        coloca(n, cx, yy);
        if (i === 0 && ent) enlaza(ent.si, n, { rama: ent.j, idx: 0 });
        else if (prev) enlaza(prev, n, { idx: i });
        lista.push(n); prev = n;
        yy += n.th;
        if (n.ramas) {
          const ys = yy + FORK; let fondo = ys;
          n.ramas.forEach((r, j) => { fondo = Math.max(fondo, dispone(r.seq, cx + (j ? SEP : -SEP), ys, { si: n, j })); });
          yy = fondo;
        } else yy += GAP;
      });
      const ult = seq[seq.length - 1];
      if (ult && ult.ramas) { seq.fin = null; return yy; }
      const f = seq.fin || (seq.fin = nuevaFin());
      const fy = seq.length ? yy : y;
      if (!f.el && !f.spawnDe) f.spawnDe = ent ? ent.si : ult;
      coloca(f, cx, fy);
      lista.push(f);
      if (seq.length) enlaza(ult, f, { idx: seq.length }); else enlaza(ent.si, f, { rama: ent.j, idx: 0 });
      return fy + FIN_H;
    }

    // lo que mide de alto una secuencia (igual que dispone, pero sin colocar nada)
    function medida(seq) {
      let hh = 0;
      seq.forEach(n => { hh += alto(n); hh += n.ramas ? FORK + Math.max(...n.ramas.map(r => medida(r.seq))) : GAP; });
      const ult = seq[seq.length - 1];
      return ult && ult.ramas ? hh : hh + FIN_H;
    }
    function layout(nuevaEntrada) {
      const ancho = el.lienzo.clientWidth || 800;
      const estrecho = matchMedia('(max-width: 560px)').matches;
      W = estrecho ? 252 : 300; SEP = (W + 40) / 2;
      raiz.style.setProperty('--es-w', W + 'px');
      const conSi = todos().some(n => n.ramas);
      const necesita = conSi ? 2 * (SEP + W / 2) + 48 : W + 48;
      const total = Math.max(ancho, necesita);
      const cx = total / 2;
      cons = []; lista = [];
      // con poco flujo, se baja un poco desde arriba para que no quede pegado al borde; crece y vuelve al borde
      const vh = el.lienzo.clientHeight || 700, dy = lim((vh - PAD_T - medida(E.seq) - 48) * .15, 0, 80);
      const fondo = dispone(E.seq, cx, PAD_T + dy, null);
      el.mundo.style.width = total + 'px';
      if (total > ancho + 1 && total !== E.ultTotal) el.lienzo.scrollLeft = (total - ancho) / 2;   // en pantallas estrechas, el cable principal queda al centro
      E.ultTotal = total;
      el.mundo.style.height = Math.max(el.lienzo.clientHeight, fondo + 26) + 'px';
      sincroniza(nuevaEntrada);
      if (quieto()) lista.forEach(it => { it.x = it.tx; it.y = it.ty; it.h = it.th; it.vx = it.vy = it.vh = 0; });
      lista.forEach(pinta);
      pintaCables();
      despierta();
    }

    /* ── el DOM de nodos, finales y cables ────────────────────────────── */
    function montaNodo(n) {
      const T = TIPOS[n.tipo];
      const b = h('div', 'es-bloque'); b.dataset.id = n.id;
      b.innerHTML =
        '<div class="es-nodo" role="button" tabindex="-1" data-tipo="' + n.tipo + '">' +
          '<span class="es-ic">' + IC[T.ic] + '</span>' +
          '<span class="es-txt"><b class="es-nom"></b><span class="es-res"></span></span>' +
          '<span class="es-est" data-e="idle" aria-hidden="true">' + IC.est + '</span>' +
          '<button class="es-x" type="button" tabindex="-1" aria-label="Remover este passo">' + IC.x + '</button>' +
        '</div>' +
        '<div class="es-salida">' +
          '<button class="es-chip" type="button" tabindex="-1" aria-expanded="false"><span class="es-chip-t"></span>' + IC.chev + '</button>' +
          '<div class="es-ficha"><div class="es-ficha-int"></div></div>' +
        '</div>' +
        '<div class="es-error" role="alert"></div>';
      n.el = b; n.nodoEl = b.firstChild;
      n.nomEl = $('.es-nom', b); n.resEl = $('.es-res', b); n.estEl = $('.es-est', b);
      n.chipEl = $('.es-chip', b); n.fichaEl = $('.es-ficha-int', b); n.errEl = $('.es-error', b); n.salEl = $('.es-salida', b);
      n.nomEl.textContent = T.nom;
      b.classList.add('es-entra');
      if (n.tipo === 'disparador') b.querySelector('.es-x').remove();
      el.mundo.appendChild(b);
      dom.add(n);
      pintaNodo(n);
      const fin = () => b.classList.remove('es-entra');
      setTimeout(fin, 900);
    }
    function montaFin(f) {
      const b = h('div', 'es-fin'); b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6.6 12.6l3.8 3.8 7.2-8.2" pathLength="1"/></svg>';
      f.el = b; b.classList.add('es-entra');
      el.mundo.appendChild(b); dom.add(f);
      setTimeout(() => b.classList.remove('es-entra'), 900);
    }
    function sale(it) {
      dom.delete(it);
      const e = it.el; it.el = null; it.fresco = true;
      if (!e) return;
      if (it.it === 'nodo' && E.sel === it) E.sel = null;
      e.classList.add('es-sale');
      setTimeout(() => e.remove(), 420);
    }
    function sincroniza() {
      const vivos = new Set(lista);
      Array.from(dom).forEach(it => { if (!vivos.has(it)) sale(it); });
      lista.forEach(it => { if (!it.el) (it.it === 'nodo' ? montaNodo : montaFin)(it); });
      // los cables: los que siguen existiendo conservan su tinta; los nuevos se dibujan
      const claves = new Set(cons.map(c => c.de.id + '>' + c.a.id));
      conRec.forEach((r, k) => { if (!claves.has(k)) quitaCable(r, k); });
      cons = cons.map(c => {
        const k = c.de.id + '>' + c.a.id;
        let r = conRec.get(k);
        if (!r) { r = creaCable(k); conRec.set(k, r); }
        Object.assign(r, c);
        r.mas.setAttribute('aria-label', 'Adicionar um passo ' + (r.rama != null ? 'no ramo «' + r.de.ramas[r.rama].etq + '»' : 'depois de «' + nombreDe(r.de) + '»'));
        if (r.rama != null) r.lab.textContent = r.de.ramas[r.rama].etq;
        return r;
      });
      // el orden del DOM sigue al visual solo para quien lo lee
    }
    const nombreDe = n => n.it === 'nodo' ? TIPOS[n.tipo].nom : 'o fim';
    function creaCable(k) {
      const g = sv('g', 'es-cable'), base = sv('path', 'es-c-base'), tinta = sv('path', 'es-c-tinta'), estela = sv('path', 'es-c-estela');
      base.setAttribute('pathLength', '1'); tinta.setAttribute('pathLength', '1'); estela.setAttribute('pathLength', '1');
      g.append(base, tinta, estela); el.cables.insertBefore(g, el.pulso);
      const mas = h('button', 'es-mas'); mas.type = 'button'; mas.tabIndex = -1; mas.innerHTML = IC.mas;
      mas.setAttribute('aria-haspopup', 'listbox');
      el.mundo.appendChild(mas);
      const lab = h('span', 'es-rama-etq'); el.mundo.appendChild(lab);
      const r = { clave: k, g, base, tinta, estela, mas, lab, p: 0, ap: false, pe: 0 };
      g.classList.add('es-nuevo'); mas.classList.add('es-entra');
      setTimeout(() => { g.classList.remove('es-nuevo'); mas.classList.remove('es-entra'); }, 900);
      return r;
    }
    function quitaCable(r, k) {
      conRec.delete(k);
      r.g.classList.add('es-sale'); r.mas.classList.add('es-sale'); r.lab.classList.add('es-sale');
      setTimeout(() => { r.g.remove(); r.mas.remove(); r.lab.remove(); }, 380);
    }

    /* ── pintar ───────────────────────────────────────────────────────── */
    function pinta(it) {
      if (!it.el) return;
      // con la propiedad `translate` (y no con `transform`) para que `scale` de las entradas no multiplique la posición
      it.el.style.translate = (it.x - (it.it === 'fin' ? 5 : W / 2)).toFixed(2) + 'px ' + it.y.toFixed(2) + 'px';
    }
    function pintaCables() {
      for (const c of cons) {
        const A = c.de, B = c.a;
        const x0 = A.x, y0 = A.y + A.h, x1 = B.x, y1 = B.y, dy = y1 - y0;
        let d, mx, my, lx = 0, ly = 0;
        if (Math.abs(x1 - x0) < .5) {
          d = 'M' + x0.toFixed(1) + ' ' + y0.toFixed(1) + 'V' + y1.toFixed(1);
          mx = x0; my = (y0 + y1) / 2;
        } else {
          const tail = Math.min(TAIL, Math.max(0, dy * .4)), ym = y1 - tail, k = (ym - y0) * .55;
          d = 'M' + x0.toFixed(1) + ' ' + y0.toFixed(1) + 'C' + x0.toFixed(1) + ' ' + (y0 + k).toFixed(1) + ' ' + x1.toFixed(1) + ' ' + (ym - k).toFixed(1) + ' ' + x1.toFixed(1) + ' ' + ym.toFixed(1) + 'V' + y1.toFixed(1);
          mx = x1; my = y1 - tail / 2; lx = (x0 + x1) / 2; ly = (y0 + ym) / 2;
        }
        c.base.setAttribute('d', d); c.tinta.setAttribute('d', d); c.estela.setAttribute('d', d);
        // la estela ámbar: un tramo corto de tinta que va pegado a la cabeza del pulso
        if (c.pe > 0 && c.p > 0 && c.p < 1) { const l = Math.min(.22, c.p); c.estela.style.strokeDasharray = l.toFixed(4) + ' 2'; c.estela.style.strokeDashoffset = (-(c.p - l)).toFixed(4); c.estela.style.opacity = 1; }
        else c.estela.style.opacity = 0;
        c.tinta.style.strokeDashoffset = (1 - c.p).toFixed(4); c.tinta.style.opacity = c.p > 0 ? 1 : 0;
        c.mas.style.translate = (mx - 11).toFixed(1) + 'px ' + (my - 11).toFixed(1) + 'px';
        if (c.rama != null) {
          c.lab.style.translate = (lx - 17).toFixed(1) + 'px ' + (ly - 11).toFixed(1) + 'px';
          c.lab.style.opacity = lim((Math.abs(x1 - x0) - 18) / 40, 0, 1).toFixed(2);
          c.lab.hidden = false;
        } else c.lab.hidden = true;
        c.g.classList.toggle('es-apagado', !!c.ap);
        if (c.rama != null) { c.lab.classList.toggle('is-tomada', c.p >= 1); c.lab.classList.toggle('is-apagada', !!c.ap); }
      }
    }
    function pintaNodo(n) {
      if (!n.el) return;
      const T = TIPOS[n.tipo], r = resumenDe(n);
      n.resEl.textContent = r.t; n.resEl.classList.toggle('is-vacio', !!r.v);
      let e = n.est;
      if (e === 'idle' && incompleto(n)) e = 'falta';
      n.estEl.dataset.e = e;
      n.nodoEl.dataset.e = n.est;
      const txt = { idle: '', falta: 'Falta um dado', run: 'Executando', ok: 'Correto', err: 'Com erro', stop: 'Parou aqui', skip: 'Ignorado' }[e] || '';
      n.nodoEl.setAttribute('aria-label', T.nom + '. ' + r.t + (txt ? '. ' + txt : '') + (E.sel === n ? '. Seleccionado' : ''));
      n.nodoEl.classList.toggle('is-sel', E.sel === n);
      n.nodoEl.setAttribute('aria-pressed', E.sel === n ? 'true' : 'false');
      n.el.classList.toggle('is-skip', n.est === 'skip');
      pintaSalida(n);
    }
    function pintaSalida(n) {
      const s = n.salida;
      n.salEl.classList.toggle('has-salida', !!s && !s.error);
      n.errEl.classList.toggle('has-error', !!s && !!s.error);
      if (!s) { n.salEl.classList.remove('is-abierta'); n.chipEl.setAttribute('aria-expanded', 'false'); return; }
      if (s.error) { n.errEl.innerHTML = '<span class="er-ic"><svg viewBox="0 0 24 24"><path d="M12 7.4v5.6M12 16.4v.2"/></svg></span><p></p>'; n.errEl.lastChild.textContent = s.msg; return; }
      n.chipEl.querySelector('.es-chip-t').textContent = 'Saída · ' + plural(s.filas.length, 'campo', 'campos') + ' · ' + (s.ms < 1000 ? s.ms + ' ms' : fmt(Math.round(s.ms / 100) / 10) + ' s');
      n.chipEl.setAttribute('aria-expanded', s.abierta ? 'true' : 'false');
      n.salEl.classList.toggle('is-abierta', !!s.abierta);
      if (!n.fichaEl.childElementCount) s.filas.forEach(([k, v]) => {
        const f = h('p', 'es-fila'); f.innerHTML = '<span class="k"></span><span class="v"></span>';
        f.firstChild.textContent = k; f.lastChild.textContent = muestra(v);
        n.fichaEl.appendChild(f);
      });
      n.salEl.style.setProperty('--fh', (s.filas.length * FILA + FICHA_P) + 'px');
    }
    const pintaTodos = () => todos().forEach(pintaNodo);

    /* ── el bucle: resortes de los nodos, la prueba y el fantasma que se arrastra ── */
    const K = 230, C_ = 20;
    function bucle(ts) {
      raf = 0;
      const dt = ultimo ? lim((ts - ultimo) / 1000, 0, .034) : .016; ultimo = ts;
      let vivo = false;
      const pasos = Math.max(1, Math.ceil(dt / (1 / 240))), hh = dt / pasos;
      for (const it of lista) {
        const quietoIt = Math.abs(it.tx - it.x) < .05 && Math.abs(it.ty - it.y) < .05 && Math.abs(it.th - it.h) < .05 && Math.abs(it.vx) + Math.abs(it.vy) + Math.abs(it.vh) < .3;
        if (quietoIt) { it.x = it.tx; it.y = it.ty; it.h = it.th; it.vx = it.vy = it.vh = 0; continue; }
        for (let k = 0; k < pasos; k++) {
          it.vx += (K * (it.tx - it.x) - C_ * it.vx) * hh; it.x += it.vx * hh;
          it.vy += (K * (it.ty - it.y) - C_ * it.vy) * hh; it.y += it.vy * hh;
          it.vh += (K * 1.3 * (it.th - it.h) - C_ * it.vh) * hh; it.h += it.vh * hh;
        }
        pinta(it); vivo = true;
      }
      if (E.run) { avanzaRun(dt); vivo = true; }
      if (arr) { vivo = avanzaArrastre(dt, hh, pasos) || vivo; }
      pintaCables();
      if (E.run) sigueConLaVista();
      if (vivo || E.run || arr) raf = requestAnimationFrame(bucle); else ultimo = 0;
    }

    /* ── seleccionar un paso y pintar su panel ───────────────────────── */
    function selecciona(n, anima) {
      if (!n) n = E.seq[0];
      const cambia = E.sel !== n;
      const ant = E.sel; E.sel = n;
      if (ant && ant.el) pintaNodo(ant);
      pintaNodo(n);
      ponFoco(n.nodoEl, false);
      if (cambia || anima) pintaPanel(anima !== false && cambia);
      if (cambia && !E.arrancando) anuncia('Editando «' + TIPOS[n.tipo].nom + '».');
    }
    function ponFoco(e, enfoca) {
      if (E.foco && E.foco !== e) E.foco.tabIndex = -1;
      E.foco = e; e.tabIndex = 0;
      if (enfoca) e.focus({ preventScroll: false });
    }

    /* ── los campos del panel ─────────────────────────────────────────── */
    const tok = (ref, n) => {
      const t = h('span', 'es-tok'), i = ref.indexOf('.');
      t.dataset.ref = ref;
      t.innerHTML = '<b></b><span></span><button class="es-tok-x" type="button" tabindex="-1">' + IC.x + '</button>';
      t.children[0].textContent = ref.slice(0, i); t.children[1].textContent = ref.slice(i);
      t.lastChild.setAttribute('aria-label', 'Quitar ' + ref);
      if (n && rota(n, ref)) { t.classList.add('is-rota'); t.title = 'Este dado não existe mais antes deste passo'; }
      return t;
    };
    function pintaPartes(n, def, caja) {
      const cont = $('.es-partes', caja), inp = $('.es-in', caja);
      Array.from(cont.children).forEach(c => { if (c !== inp) c.remove(); });
      const ps = n.campos[def.k];
      ps.forEach(p => cont.insertBefore(typeof p === 'string' ? h('span', 'es-tx', p) : tok(p.ref, n), inp));
      const lleno = def.t === 'slot' && ps.length > 0;
      inp.hidden = lleno;
      caja.classList.toggle('is-llena', lleno || ps.length > 0);
      caja.classList.toggle('is-slot-vacio', def.t === 'slot' && !ps.length);
      inp.placeholder = ps.length || n.cola[def.k] ? '' : def.ph || '';
    }
    function campoToken(n, def) {
      const g = h('div', 'es-campo-g'), caja = h('div', 'es-campo' + (def.alto ? ' es-alto' : ''));
      const et = h('p', 'es-et', def.et); et.id = 'es-et-' + def.k;
      caja.dataset.k = def.k; caja.dataset.acepta = '1';
      const cont = h('div', 'es-partes'), inp = h('input', 'es-in');
      inp.type = 'text'; inp.autocomplete = 'off'; inp.spellcheck = false; inp.setAttribute('aria-labelledby', et.id);
      inp.value = n.cola[def.k] || '';
      cont.appendChild(inp); caja.appendChild(cont); g.append(et, caja);
      pintaPartes(n, def, caja);
      caja.addEventListener('pointerdown', e => { if (!e.target.closest('.es-tok') && e.target !== inp) { e.preventDefault(); inp.focus(); } });
      inp.addEventListener('focus', () => { E.campoAct = def.k; caja.classList.add('is-foco'); });
      inp.addEventListener('blur', () => { caja.classList.remove('is-foco'); setTimeout(() => { if (E.arroba && !E.arroba.caja.contains(document.activeElement)) cierraArroba(); }, 120); });
      inp.addEventListener('input', () => {
        n.cola[def.k] = inp.value; cambio(n, def.k, false);
        const m = inp.value.match(/@([\wñáéíóú.]*)$/i);
        if (m) abreArroba(n, def, caja, inp, m[1]); else cierraArroba();
        inp.placeholder = n.campos[def.k].length || inp.value ? '' : def.ph || '';
      });
      inp.addEventListener('keydown', e => {
        if (E.arroba && E.arroba.caja === caja) {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); muevaArroba(e.key === 'ArrowDown' ? 1 : -1); return; }
          if (e.key === 'Enter' || e.key === 'Tab') { if (E.arroba.items.length) { e.preventDefault(); eligeArroba(); return; } }
          if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cierraArroba(); return; }
        }
        if (e.key === 'Backspace' && !inp.value && n.campos[def.k].length) {
          const ps = n.campos[def.k], u = ps[ps.length - 1];
          if (typeof u === 'string' && u.length > 1) ps[ps.length - 1] = u.slice(0, -1); else ps.pop();
          pintaPartes(n, def, caja); cambio(n, def.k, true);
        } else if (e.key === 'Enter' && inp.value && def.t === 'multi') {
          n.campos[def.k].push(inp.value); n.cola[def.k] = ''; inp.value = '';
          pintaPartes(n, def, caja); cambio(n, def.k, true);
        }
      });
      caja.addEventListener('click', e => {
        const x = e.target.closest('.es-tok-x'); if (!x) return;
        const t = x.closest('.es-tok'), i = Array.from(cont.children).indexOf(t);
        n.campos[def.k].splice(i, 1); pintaPartes(n, def, caja); cambio(n, def.k, true);
        anuncia('Dado removido de «' + def.et + '»');
        if (def.t === 'slot') inp.focus();
      });
      return g;
    }
    function campoSeg(n, def) {
      const g = h('div', 'es-campo-g'), et = h('p', 'es-et', def.et); et.id = 'es-et-' + def.k;
      const seg = h('div', 'es-seg es-seg-p'); seg.setAttribute('role', 'radiogroup'); seg.setAttribute('aria-labelledby', et.id);
      seg.style.setProperty('--n', def.opts.length);
      seg.appendChild(h('span', 'es-seg-fondo'));
      const idx = () => Math.max(0, def.opts.findIndex(o => o.k === n.campos[def.k]));
      seg.style.setProperty('--i', idx());
      def.opts.forEach((o, i) => {
        const b = h('button', null, o.et); b.type = 'button'; b.setAttribute('role', 'radio');
        b.setAttribute('aria-checked', o.k === n.campos[def.k] ? 'true' : 'false'); b.tabIndex = o.k === n.campos[def.k] ? 0 : -1;
        b.addEventListener('click', () => {
          n.campos[def.k] = o.k; seg.style.setProperty('--i', i);
          seg.querySelectorAll('button').forEach((x, j) => { x.setAttribute('aria-checked', j === i ? 'true' : 'false'); x.tabIndex = j === i ? 0 : -1; });
          cambio(n, def.k, true);
        });
        b.addEventListener('keydown', e => {
          if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
          e.preventDefault(); const j = lim(i + (e.key === 'ArrowRight' ? 1 : -1), 0, def.opts.length - 1);
          seg.querySelectorAll('button')[j].click(); seg.querySelectorAll('button')[j].focus();
        });
        seg.appendChild(b);
      });
      g.append(et, seg);
      return g;
    }
    function campoTexto(n, def) {
      const g = h('div', 'es-campo-g'), et = h('label', 'es-et', def.et);
      const caja = h('div', 'es-campo es-plano'), inp = h('input', 'es-in'); caja.dataset.k = def.k;
      inp.type = 'text'; inp.value = n.campos[def.k]; inp.autocomplete = 'off'; inp.spellcheck = false;
      if (def.num) inp.inputMode = 'decimal';
      inp.id = 'es-in-' + def.k; et.htmlFor = inp.id;
      inp.addEventListener('input', () => { n.campos[def.k] = inp.value; cambio(n, def.k, false); });
      inp.addEventListener('focus', () => caja.classList.add('is-foco')); inp.addEventListener('blur', () => caja.classList.remove('is-foco'));
      caja.appendChild(inp); caja.addEventListener('pointerdown', e => { if (e.target === caja) { e.preventDefault(); inp.focus(); } });
      g.append(et, caja);
      return g;
    }
    function campoFijo(n, def) {
      const g = h('div', 'es-campo-g'), et = h('p', 'es-et', def.et), caja = h('div', 'es-campo es-fijo'); caja.dataset.k = def.k;
      caja.appendChild(h('code', null, n.campos[def.k]));
      g.append(et, caja);
      return g;
    }
    // un campo cambió: el resumen del nodo, el aviso de «falta un dato» y lo que ya se había probado
    function cambio(n, k, rehace) {
      if (E.errCampo) { E.errCampo = null; $('.es-p-err', el.panel) && $('.es-p-err', el.panel).remove(); el.panel.querySelectorAll('.is-err').forEach(x => x.classList.remove('is-err')); }
      const antes = n.est;
      if (E.run) cancelaRun();
      if (todos().some(x => x.salida || x.est !== 'idle')) limpiaRun();
      else pintaNodo(n);
      pintaNodo(n);
      if (rehace) pintaTodos();
      pintaEstado();
      if (op.alCambiar) op.alCambiar({ flujo: serializa() });
    }

    /* Insertar un dato (una píldora) en un campo: el token entra con un resorte y un anillo. */
    function insertaRef(n, k, ref, desde) {
      const def = (CAMPOS[n.tipo] || []).find(d => d.k === k); if (!def) return;
      const caja = el.panel.querySelector('.es-campo[data-k="' + k + '"]'); if (!caja) return;
      const inp = $('.es-in', caja);
      if (def.t === 'slot') n.campos[k] = [{ ref }];
      else { if (n.cola[k]) { n.campos[k].push(n.cola[k]); n.cola[k] = ''; inp.value = ''; } n.campos[k].push({ ref }); }
      pintaPartes(n, def, caja);
      const ts = caja.querySelectorAll('.es-tok'), t = ts[ts.length - 1];
      if (t && !quieto()) {
        t.classList.add('es-llega');
        t.animate([{ transform: 'scale(.55)', opacity: .2 }, { transform: 'scale(1)', opacity: 1 }], { duration: 560, easing: EASE });
        const a = h('i', 'es-anillo');   // un anillo con la forma del dato se abre alrededor de él
        a.style.cssText = 'left:' + (t.offsetLeft - 2) + 'px;top:' + (t.offsetTop - 2) + 'px;width:' + (t.offsetWidth + 4) + 'px;height:' + (t.offsetHeight + 4) + 'px';
        caja.appendChild(a); setTimeout(() => a.remove(), 800);
      }
      cambio(n, k, true);
      anuncia('«' + ref + '» adicionado a «' + def.et + '»');
      if (def.t !== 'slot') inp.focus();
    }

    /* «@» dentro de un campo: lista de datos para elegir con el teclado */
    function disponibles(n) {
      const out = [];
      (n.tipo === 'disparador' ? [] : previos(n)).forEach(p => { const s = ejemploSalida(p); Object.keys(s).forEach(k => out.push({ ref: p.alias + '.' + k, v: s[k] })); });
      return out;
    }
    function abreArroba(n, def, caja, inp, q) {
      const items = disponibles(n).filter(x => !q || norm(x.ref).includes(norm(q)));
      if (!E.arroba || E.arroba.caja !== caja) {
        cierraArroba();
        const ul = h('ul', 'es-arroba'); ul.setAttribute('role', 'listbox'); ul.id = 'es-arroba';
        caja.parentElement.appendChild(ul);
        E.arroba = { ul, caja, inp, n, def, items: [], i: 0 };
        inp.setAttribute('aria-controls', 'es-arroba'); inp.setAttribute('aria-expanded', 'true');
        if (!quieto()) ul.animate([{ opacity: 0, transform: 'translateY(-6px) scale(.97)' }, { opacity: 1, transform: 'none' }], { duration: 380, easing: EASE });
      }
      const A = E.arroba; A.items = items; A.i = 0; A.ul.textContent = '';
      if (!items.length) A.ul.appendChild(h('li', 'es-arroba-vacio', 'Nenhum dado tem esse nome'));
      items.forEach((x, i) => {
        const li = h('li', 'es-arroba-i' + (i === 0 ? ' is-on' : '')); li.setAttribute('role', 'option'); li.id = 'es-arr-' + i;
        li.innerHTML = '<span class="r"></span><span class="v"></span>'; li.firstChild.textContent = x.ref; li.lastChild.textContent = muestra(x.v);
        li.addEventListener('pointerdown', e => { e.preventDefault(); A.i = i; eligeArroba(); });
        A.ul.appendChild(li);
      });
      inp.setAttribute('aria-activedescendant', items.length ? 'es-arr-0' : '');
    }
    function muevaArroba(d) {
      const A = E.arroba; if (!A.items.length) return;
      A.i = (A.i + d + A.items.length) % A.items.length;
      A.ul.querySelectorAll('.es-arroba-i').forEach((li, i) => li.classList.toggle('is-on', i === A.i));
      A.inp.setAttribute('aria-activedescendant', 'es-arr-' + A.i);
    }
    function eligeArroba() {
      const A = E.arroba, x = A.items[A.i]; if (!x) return;
      A.inp.value = A.inp.value.replace(/@[\wñáéíóú.]*$/i, ''); A.n.cola[A.def.k] = A.inp.value;
      const n = A.n, k = A.def.k;
      cierraArroba();
      insertaRef(n, k, x.ref);
    }
    function cierraArroba() {
      const A = E.arroba; if (!A) return;
      A.ul.remove(); A.inp.removeAttribute('aria-controls'); A.inp.removeAttribute('aria-activedescendant'); A.inp.setAttribute('aria-expanded', 'false');
      E.arroba = null;
    }

    /* ── el panel de la derecha ───────────────────────────────────────── */
    function pintaPanel(anima) {
      cierraArroba();
      const n = E.sel, P = el.panel;
      P.textContent = ''; P.dataset.arrastra = '0';
      if (!n) return;
      const T = TIPOS[n.tipo], orden = todos().indexOf(n) + 1;
      const cab = h('header', 'es-p-cab');
      cab.innerHTML = '<span class="es-ic es-ic-g" data-tipo="' + n.tipo + '">' + IC[T.ic] + '</span><div class="es-p-t"><p class="es-rot"></p><h2></h2></div>';
      $('.es-rot', cab).textContent = n.tipo === 'disparador' ? 'Gatilho' : n.tipo === 'si' ? 'Condição' : 'Passo ' + (orden - 1);
      $('h2', cab).textContent = T.nom;
      if (n.tipo !== 'disparador') {
        const b = h('button', 'es-p-borra'); b.type = 'button'; b.innerHTML = IC.basura; b.setAttribute('aria-label', 'Remover este passo'); b.title = 'Remover este passo';
        b.addEventListener('click', () => quitaNodo(n, true));
        cab.appendChild(b);
      }
      P.appendChild(cab);
      P.appendChild(h('p', 'es-p-desc', T.desc));
      const cs = h('div', 'es-campos');
      (CAMPOS[n.tipo] || []).forEach(def => {
        const g = def.t === 'seg' ? campoSeg(n, def) : def.t === 'texto' ? campoTexto(n, def) : def.t === 'fijo' ? campoFijo(n, def) : campoToken(n, def);
        cs.appendChild(g);
      });
      P.appendChild(cs);
      // los datos: píldoras que se arrastran a un campo
      const ds = h('section', 'es-datos');
      const usaDatos = (CAMPOS[n.tipo] || []).some(d => d.t === 'slot' || d.t === 'multi');
      const prev = n.tipo === 'disparador' ? [n] : usaDatos ? previos(n) : [];
      ds.appendChild(h('h3', 'es-d-tit', n.tipo === 'disparador' ? 'Dados que este passo entrega' : 'Dados disponíveis'));
      ds.appendChild(h('p', 'es-d-ayuda', n.tipo === 'disparador' ? 'Os passos abaixo poderão usá-los.' : usaDatos ? 'Arraste-os para um campo, toque neles ou digite @ dentro de um campo.' : 'Este passo não usa dados dos anteriores.'));
      prev.forEach(p => {
        const g = h('div', 'es-grupo'), tt = h('p', 'es-g-tit');
        tt.innerHTML = '<span class="es-ic es-ic-m" data-tipo="' + p.tipo + '">' + IC[TIPOS[p.tipo].ic] + '</span><b></b><code></code>';
        tt.children[1].textContent = TIPOS[p.tipo].nom; tt.children[2].textContent = p.alias;
        const ul = h('div', 'es-pildoras'); const s = ejemploSalida(p);
        Object.keys(s).forEach(k => {
          const b = h('button', 'es-pil'); b.type = 'button'; b.dataset.ref = p.alias + '.' + k;
          if (n.tipo === 'disparador') { b.dataset.fijo = '1'; b.tabIndex = -1; b.disabled = true; }
          b.innerHTML = '<span class="g">' + IC.grip + '</span><span class="n"></span><span class="v"></span>';
          b.children[1].textContent = k; b.children[2].textContent = muestra(s[k]);
          b.setAttribute('aria-label', 'Insertar ' + p.alias + '.' + k + ', valor ' + muestra(s[k]));
          ul.appendChild(b);
        });
        g.append(tt, ul); ds.appendChild(g);
      });
      P.appendChild(ds);
      if (E.errCampo && E.errCampo.id === n.id) marcaError(n, E.errCampo.k, E.errCampo.msg);
      P.scrollTop = 0;
      if (anima && !quieto()) Array.from(P.children).forEach((c, i) => c.animate([{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], { duration: 480, delay: i * 55, easing: EASE, fill: 'backwards' }));
    }
    function marcaError(n, k, msg) {
      const caja = el.panel.querySelector('.es-campo[data-k="' + k + '"]');
      if (!caja) return;
      caja.classList.add('is-err');
      const m = h('p', 'es-p-err'); m.textContent = msg; caja.parentElement.appendChild(m);
      if (!quieto()) { caja.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-5px)' }, { transform: 'translateX(4px)' }, { transform: 'translateX(-2px)' }, { transform: 'none' }], { duration: 420, easing: 'ease-out' }); }
    }

    /* ── el arrastre de una píldora ───────────────────────────────────── */
    let arr = null;
    el.panel.addEventListener('pointerdown', e => {
      const p = e.target.closest('.es-pil');
      if (!p || p.dataset.fijo || e.button > 0 || arr) return;
      arr = { p, ref: p.dataset.ref, id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, activo: false };
    });
    document.addEventListener('pointermove', e => {
      if (!arr || e.pointerId !== arr.id || arr.suelto) return;
      arr.x = e.clientX; arr.y = e.clientY;
      if (!arr.activo && Math.hypot(arr.x - arr.x0, arr.y - arr.y0) > 5) activaArrastre();
      if (arr.activo) { marcaZona(); despierta(); }
    });
    const finPuntero = e => {
      if (!arr || e.pointerId !== arr.id || arr.suelto) return;
      if (arr.activo) suelta(e.type === 'pointercancel'); else arr = null;
    };
    document.addEventListener('pointerup', finPuntero); document.addEventListener('pointercancel', finPuntero);
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && arr && arr.activo && !arr.suelto) suelta(true); });
    function activaArrastre() {
      const r = arr.p.getBoundingClientRect();
      const f = arr.p.cloneNode(true); f.classList.add('es-fantasma'); f.removeAttribute('data-ref'); f.tabIndex = -1; f.setAttribute('aria-hidden', 'true');
      f.style.width = r.width + 'px'; f.style.height = r.height + 'px';
      raiz.appendChild(f);
      Object.assign(arr, { activo: true, fant: f, w: r.width, h: r.height, ox: arr.x0 - (r.left + r.width / 2), oy: arr.y0 - (r.top + r.height / 2), gx: r.left + r.width / 2, gy: r.top + r.height / 2, gvx: 0, gvy: 0, rot: 0, vrot: 0, esc: 1 });
      arr.p.classList.add('is-origen');
      el.panel.dataset.arrastra = '1';
      arr.zonas = Array.from(el.panel.querySelectorAll('.es-campo[data-acepta]')).map(c => ({ c, k: c.dataset.k }));
      arr.zonas.forEach(z => z.c.classList.add('is-zona'));
      raiz.classList.add('is-arrastrando');
      arr.supr = true;
      anuncia('Arrastando ' + arr.ref + '. Solte sobre um campo.');
    }
    function marcaZona() {
      let hov = null, mejor = 1e9;
      arr.zonas.forEach(z => {
        const r = z.c.getBoundingClientRect(), m = 14;
        if (arr.x >= r.left - m && arr.x <= r.right + m && arr.y >= r.top - m && arr.y <= r.bottom + m) {
          const d = Math.abs(arr.y - (r.top + r.height / 2));
          if (d < mejor) { mejor = d; hov = z; }
        }
      });
      if (hov !== arr.hov) { arr.zonas.forEach(z => z.c.classList.toggle('is-sobre', z === hov)); arr.hov = hov; }
    }
    function suelta(cancela) {
      arr.suelto = true;
      const z = cancela ? null : arr.hov;
      arr.zonas.forEach(zz => zz.c.classList.remove('is-zona', 'is-sobre'));
      el.panel.dataset.arrastra = '0'; raiz.classList.remove('is-arrastrando');
      if (z) {
        const r = z.c.getBoundingClientRect(), caja = z.c;
        const finaliza = () => { arr.fant.remove(); arr.p.classList.remove('is-origen'); const a = arr; arr = null; insertaRef(E.sel, z.k, a.ref); };
        arr.vuela = { x: r.left + Math.min(r.width - 40, 22 + (caja.querySelectorAll('.es-tok').length * 60)) + arr.w / 2 - 18, y: r.top + r.height / 2 };
        arr.fant.classList.add('is-cae');
        if (quieto()) finaliza(); else setTimeout(finaliza, 230);
      } else {
        const r = arr.p.getBoundingClientRect();
        arr.vuela = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        arr.fant.classList.add('is-vuelve');
        const finaliza = () => { arr.fant.remove(); arr.p.classList.remove('is-origen'); arr = null; };
        if (quieto()) finaliza(); else setTimeout(finaliza, 300);
      }
      setTimeout(() => { if (arr) arr.supr = false; }, 0);
      despierta();
    }
    function avanzaArrastre(dt, hh, pasos) {
      if (!arr || !arr.activo) return false;
      const tx = arr.vuela ? arr.vuela.x : arr.x - arr.ox, ty = arr.vuela ? arr.vuela.y : arr.y - arr.oy;
      const k = arr.vuela ? 560 : 520, c = arr.vuela ? 38 : 33;
      for (let i = 0; i < pasos; i++) {
        arr.gvx += (k * (tx - arr.gx) - c * arr.gvx) * hh; arr.gx += arr.gvx * hh;
        arr.gvy += (k * (ty - arr.gy) - c * arr.gvy) * hh; arr.gy += arr.gvy * hh;
        // se inclina con la velocidad horizontal, como una carta que se lleva a rastras
        arr.vrot += (240 * (lim(arr.gvx * .014, -11, 11) - arr.rot) - 22 * arr.vrot) * hh; arr.rot += arr.vrot * hh;
      }
      const esc = arr.vuela ? 1 : 1.07;
      arr.fant.style.transform = 'translate3d(' + (arr.gx - arr.w / 2).toFixed(1) + 'px,' + (arr.gy - arr.h / 2).toFixed(1) + 'px,0) rotate(' + arr.rot.toFixed(2) + 'deg) scale(' + esc + ')';
      return true;
    }
    // tocar una píldora (sin arrastrar) la inserta en el campo donde estabas, o en el primero que acepte datos
    el.panel.addEventListener('click', e => {
      const p = e.target.closest('.es-pil');
      if (!p || p.dataset.fijo) return;
      if (arr && arr.supr) return;
      const n = E.sel, ks = el.panel.querySelectorAll('.es-campo[data-acepta]');
      if (!ks.length) return;
      let k = E.campoAct && el.panel.querySelector('.es-campo[data-k="' + E.campoAct + '"][data-acepta]') ? E.campoAct : null;
      if (!k) { const v = Array.from(ks).find(c => c.classList.contains('is-slot-vacio')); k = (v || ks[0]).dataset.k; }
      insertaRef(n, k, p.dataset.ref);
    });

    /* ── el menú de pasos que se abre en cada «+» ─────────────────────── */
    const menu = h('div', 'es-menu'); menu.hidden = true;
    menu.innerHTML = '<p class="es-m-tit">Adicionar um passo</p><div class="es-m-q">' + IC.lupa + '<input type="text" class="es-m-in" placeholder="Buscar passo…" aria-label="Buscar paso" role="combobox" aria-expanded="true" aria-controls="es-m-lista" autocomplete="off" spellcheck="false"></div><ul class="es-m-lista" id="es-m-lista" role="listbox" aria-label="Passos disponíveis"></ul>';
    raiz.appendChild(menu);
    const mIn = $('.es-m-in', menu), mLista = $('.es-m-lista', menu);
    function puedeSi(rec) {
      if (rec.rama != null) return false;                               // dentro de una rama no se anida otra
      const idx = rec.idx;
      return !rec.seq.slice(idx).some(x => x.ramas) && rec.seq === E.seq;
    }
    function pintaMenu() {
      const q = norm(mIn.value.trim()), M = E.menu;
      // lo que empieza como el nombre va primero; luego lo que lo contiene; al final lo que solo coincide en la descripción
      const puntos = k => { const nom = norm(TIPOS[k].nom); return nom.startsWith(q) ? 0 : nom.includes(q) ? 1 : norm(TIPOS[k].menu).includes(q) ? 2 : 9; };
      M.items = EN_MENU.filter(k => !q || puntos(k) < 9).sort((a, b) => !q ? 0 : puntos(a) - puntos(b));
      mLista.textContent = '';
      if (!M.items.length) mLista.appendChild(h('li', 'es-m-vacio', 'Nenhum passo tem esse nome'));
      M.items.forEach((k, i) => {
        const T = TIPOS[k], ok = k !== 'si' || puedeSi(M.rec);
        const li = h('li', 'es-m-i' + (i === M.i ? ' is-on' : '') + (ok ? '' : ' is-off')); li.id = 'es-mi-' + k; li.setAttribute('role', 'option'); li.dataset.k = k;
        if (!ok) li.setAttribute('aria-disabled', 'true');
        li.innerHTML = '<span class="es-ic" data-tipo="' + k + '">' + IC[T.ic] + '</span><span class="t"><b></b><span></span></span>';
        li.querySelector('b').textContent = T.nom; li.querySelector('.t span').textContent = ok ? T.menu : 'Só uma bifurcação por fluxo';
        li.addEventListener('pointermove', () => { if (M.i !== i) { M.i = i; marcaMenu(); } });
        li.addEventListener('click', () => { if (ok) elige(k); });
        li.style.setProperty('--d', (i * 32) + 'ms');
        mLista.appendChild(li);
      });
      mIn.setAttribute('aria-activedescendant', M.items[M.i] ? 'es-mi-' + M.items[M.i] : '');
    }
    function marcaMenu() {
      const M = E.menu;
      mLista.querySelectorAll('.es-m-i').forEach((li, i) => li.classList.toggle('is-on', i === M.i));
      mIn.setAttribute('aria-activedescendant', M.items[M.i] ? 'es-mi-' + M.items[M.i] : '');
    }
    function abreMenu(rec, porTeclado) {
      if (E.run) cancelaRun();
      cierraMenu(false);
      E.menu = { rec, i: 0, items: [], desde: rec.mas, teclado: !!porTeclado };
      rec.mas.classList.add('is-abierto'); rec.mas.setAttribute('aria-expanded', 'true');
      mIn.value = ''; pintaMenu();
      menu.hidden = false;
      const rm = rec.mas.getBoundingClientRect(), rr = raiz.getBoundingClientRect(), mw = 268, mh = menu.offsetHeight || 340;
      const estrecho = rr.width < 640;
      let x = estrecho ? rm.left - rr.left - mw / 2 + 11 : rm.right - rr.left + 14;
      let y = estrecho ? rm.bottom - rr.top + 12 : rm.top - rr.top - 28;
      x = lim(x, 12, rr.width - mw - 12); y = lim(y, 12, rr.height - mh - 12);
      menu.style.translate = x.toFixed(0) + 'px ' + y.toFixed(0) + 'px';
      menu.style.setProperty('--ox', lim(rm.right - rr.left + 3 - x, 0, mw) + 'px'); menu.style.setProperty('--oy', (rm.top - rr.top + 11 - y) + 'px');
      menu.classList.remove('es-cierra'); void menu.offsetWidth; menu.classList.add('es-abre');
      mIn.focus({ preventScroll: true });
      setTimeout(() => menu.classList.remove('es-abre'), 700);
    }
    function cierraMenu(devuelve) {
      const M = E.menu; if (!M) return;
      M.rec.mas.classList.remove('is-abierto'); M.rec.mas.removeAttribute('aria-expanded');
      E.menu = null;
      menu.classList.remove('es-abre'); menu.classList.add('es-cierra');
      setTimeout(() => { if (!E.menu) { menu.hidden = true; menu.classList.remove('es-cierra'); } }, quieto() ? 0 : 160);
      if (quieto()) menu.hidden = true;
      if (devuelve && M.rec.mas.isConnected) ponFoco(M.rec.mas, true);
    }
    mIn.addEventListener('input', () => { if (!E.menu) return; E.menu.i = 0; pintaMenu(); });
    mIn.addEventListener('keydown', e => {
      const M = E.menu; if (!M) return;
      if (e.key === 'Escape') { e.preventDefault(); cierraMenu(true); }
      else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (M.items.length) { M.i = (M.i + (e.key === 'ArrowDown' ? 1 : -1) + M.items.length) % M.items.length; marcaMenu(); } }
      else if (e.key === 'Enter') { e.preventDefault(); const k = M.items[M.i]; if (k && (k !== 'si' || puedeSi(M.rec))) elige(k); }
      else if (e.key === 'Tab') { e.preventDefault(); cierraMenu(true); }
    });
    document.addEventListener('pointerdown', e => { if (E.menu && !menu.contains(e.target) && !E.menu.rec.mas.contains(e.target)) cierraMenu(false); });

    /* ── insertar y quitar pasos ──────────────────────────────────────── */
    function elige(tipo) {
      const M = E.menu, rec = M.rec, teclado = M.teclado;
      cierraMenu(false);
      const n = inserta(tipo, rec);
      if (n && teclado) ponFoco(n.nodoEl, true);
    }
    function inserta(tipo, donde, indice) {
      // `donde` es el conector (lo que elige el menú) o una secuencia; con `indice` la API pública pone el paso en esa posición
      let seq, idx, rec = null;
      if (donde && donde.seq) { rec = donde; seq = donde.seq; idx = donde.idx; }
      else { seq = E.seq; idx = lim(indice == null ? seq.length : indice, 1, seq.length); rec = { seq, idx, de: seq[idx - 1], rama: null }; }
      if (tipo === 'si' && !puedeSi(rec)) return null;
      if (E.run) cancelaRun();
      el.pista.classList.add('is-fuera');
      const n = creaNodo(tipo); n.alias = aliasUnico(tipo);
      if (tipo === 'si') {
        const cola = seq.splice(idx);
        cola.fin = seq.fin; seq.fin = null;
        n.ramas[0].seq = cola; n.ramas[1].seq = [];
        n.ramas[1].seq.fin = null;
        seq.push(n);
      } else seq.splice(idx, 0, n);
      limpiaRunSolo();
      layout();
      selecciona(n, true);
      pintaTodos(); pintaEstado();
      anuncia('Passo adicionado: ' + TIPOS[tipo].nom + (tipo === 'si' ? '. O fluxo se divide em dois ramos, Sim e Não.' : '.'));
      if (op.alCambiar) op.alCambiar({ flujo: serializa() });
      return n;
    }
    function quitaNodo(n, enfoca) {
      if (n.tipo === 'disparador') return;
      if (E.run) cancelaRun();
      const u = ubica(n); if (!u) return;
      const { seq, idx } = u;
      if (n.ramas) {                     // al quitar el «Si…», lo que colgaba de «Sí» vuelve al cable principal
        const sí = n.ramas[0].seq, fin = sí.fin;
        seq.splice(idx, 1, ...sí); seq.fin = fin;
      } else seq.splice(idx, 1);
      porId.delete(n.id);
      const vecino = seq[idx - 1] || seq[0];
      limpiaRunSolo();
      if (E.sel === n) E.sel = null;
      layout();
      selecciona(vecino, true);
      pintaTodos(); pintaEstado();
      if (enfoca) ponFoco(vecino.nodoEl, true);
      anuncia('Passo removido: ' + TIPOS[n.tipo].nom);
      if (op.alCambiar) op.alCambiar({ flujo: serializa() });
    }
    function serializa() {
      const s = seq => seq.map(n => Object.assign({ id: n.id, tipo: n.tipo, campos: copia(n.campos) }, n.ramas ? { ramas: n.ramas.map(r => s(r.seq)) } : {}));
      return s(E.seq);
    }

    /* ── probar: un pulso baja por el cable ───────────────────────────── */
    const entra = it => cons.find(c => c.a === it);
    function construyePlan() {
      const ev = EVENTOS[E.evento], ctx = {}, plan = [];
      let ms = 0, pasos = 0, falla = null;
      const sigue = (seq, primeraCon) => {
        for (let i = 0; i < seq.length; i++) {
          const n = seq[i], c = i === 0 ? primeraCon : entra(n);
          if (c) plan.push({ tipo: 'viaje', con: c, dur: .34 });
          const r = ejecuta(n, ctx, ev);
          plan.push({ tipo: 'nodo', n, r, dur: r.dur });
          pasos++; ms += r.ms || 0;
          if (!r.ok) { falla = { n, r }; return false; }
          if (r.stop) { plan.parada = n; return false; }
          ctx[n.alias] = r.salida;
          if (n.ramas) {
            const j = r.rama, otra = n.ramas[1 - j].seq;
            plan.push({ tipo: 'apaga', rama: otra, con: entra(otra[0] || otra.fin), dur: 0 });
            const dentro = n.ramas[j].seq;
            return sigue(dentro, entra(dentro[0] || dentro.fin));
          }
        }
        const f = seq.fin;
        if (f) { plan.push({ tipo: 'viaje', con: entra(f), dur: .34 }); plan.push({ tipo: 'fin', f, dur: .1 }); }
        return true;
      };
      const ok = sigue(E.seq, null);
      plan.ok = ok; plan.ms = ms; plan.pasos = pasos; plan.falla = falla;
      return plan;
    }
    function lanza() {
      if (E.run) return;
      if (E.menu) cierraMenu(false);
      el.pista.classList.add('is-fuera');
      limpiaRun();
      const plan = construyePlan();
      if (quieto()) plan.forEach(e => { e.dur = 0; });
      E.run = { plan, i: -1, t: 0, base: 0 };
      el.probar.dataset.e = 'corre'; el.probarTxt.textContent = 'Testando…'; el.probar.setAttribute('aria-disabled', 'true');
      el.estado.dataset.e = 'corre'; el.estadoTxt.textContent = 'Testando com «' + (E.evento === 'sin' ? 'Sem e-mail' : 'Completo') + '»';
      raiz.classList.add('is-corriendo');
      anuncia('Testando o fluxo com um evento de exemplo.');
      despierta();
    }
    function avanzaRun(dt) {
      const R = E.run; R.t += dt;
      for (let g = 0; g < 200 && E.run; g++) {
        if (R.i >= 0) {
          const e = R.plan[R.i], u = e.dur > 0 ? (R.t - R.base) / e.dur : 1;
          if (u < 1) { progreso(e, u); return; }
          progreso(e, 1); termina(e); R.base += e.dur;
        }
        R.i++;
        if (R.i >= R.plan.length) { acabaRun(); return; }
        inicia(R.plan[R.i]);
      }
    }
    function inicia(e) {
      if (e.tipo === 'viaje') { el.pulso.classList.remove('is-off'); e.con.p = 0; e.con.pe = 1; colocaPulso(e.con, 0); }
      else if (e.tipo === 'nodo') {
        el.pulso.classList.add('is-off');
        e.n.est = 'run'; pintaNodo(e.n);
        e.n.nodoEl.classList.remove('es-ping'); void e.n.nodoEl.offsetWidth; e.n.nodoEl.classList.add('es-ping');
      } else if (e.tipo === 'apaga') {
        if (e.con) e.con.ap = true;
        const marca = seq => { seq.forEach(x => { x.est = 'skip'; pintaNodo(x); if (x.ramas) x.ramas.forEach(r => marca(r.seq)); }); if (seq.fin) { seq.fin.est = 'skip'; seq.fin.el && seq.fin.el.classList.add('is-skip'); } };
        marca(e.rama);
      } else if (e.tipo === 'fin') {
        el.pulso.classList.add('is-off');
      }
    }
    function progreso(e, u) {
      if (e.tipo === 'viaje') { e.con.p = suave(u); colocaPulso(e.con, e.con.p); }
    }
    function termina(e) {
      if (e.tipo === 'viaje') { e.con.p = 1; e.con.pe = 0; }
      else if (e.tipo === 'nodo') {
        const { n, r } = e;
        if (!r.ok) {
          n.est = 'err'; n.salida = { error: true, msg: r.msg };
          E.errCampo = { id: n.id, k: r.campo, msg: r.msg };
        } else {
          n.est = r.stop ? 'stop' : 'ok';
          n.salida = { filas: Object.entries(r.salida), ms: r.ms, abierta: false };
        }
        pintaNodo(n); layout();
      } else if (e.tipo === 'fin') {
        e.f.est = 'ok'; e.f.el && e.f.el.classList.add('is-ok');
      }
    }
    function acabaRun() {
      const R = E.run, plan = R.plan; E.run = null;
      el.pulso.classList.add('is-off');
      raiz.classList.remove('is-corriendo');
      el.probar.removeAttribute('aria-disabled');
      const ms = plan.ms, tms = ms < 1000 ? ms + ' ms' : fmt(Math.round(ms / 100) / 10) + ' s';
      if (plan.ok) {
        // la ficha del último paso se abre sola: es lo que el flujo entregó
        const ult = plan.filter(e => e.tipo === 'nodo').pop();
        if (ult && ult.n.salida && !ult.n.salida.error) { ult.n.salida.abierta = true; ult.n.fichaEl.textContent = ''; pintaSalida(ult.n); layout(); }
        el.probar.dataset.e = 'ok'; el.probarTxt.textContent = 'Testar de novo';
        el.estado.dataset.e = 'ok'; el.estadoTxt.textContent = 'Testado · ' + plural(plan.pasos, 'passo', 'passos') + ' · ' + tms;
        anuncia('Teste concluído: ' + plural(plan.pasos, 'passo', 'passos') + ' en ' + tms + '.');
      } else if (plan.falla) {
        const { n, r } = plan.falla;
        el.probar.dataset.e = 'falla'; el.probarTxt.textContent = 'Testar de novo';
        el.estado.dataset.e = 'falla'; el.estadoTxt.textContent = 'Se detuvo en «' + TIPOS[n.tipo].nom + '»';
        selecciona(n, true);
        anuncia('Se detuvo en ' + TIPOS[n.tipo].nom + ': ' + r.msg);
      } else {
        const n = plan.parada;
        el.probar.dataset.e = 'ok'; el.probarTxt.textContent = 'Testar de novo';
        el.estado.dataset.e = 'ok'; el.estadoTxt.textContent = 'Se detuvo en «' + TIPOS[n.tipo].nom + '»';
        anuncia('O fluxo parou em ' + TIPOS[n.tipo].nom + ' porque não foi cumprido.');
      }
      if (op.alTestar) op.alTestar({ ok: !!plan.ok, pasos: plan.pasos, ms, falla: plan.falla ? { paso: plan.falla.n.id, motivo: plan.falla.r.msg } : null });
    }
    function colocaPulso(con, p) {
      const L = con.tinta.getTotalLength(), pt = con.tinta.getPointAtLength(Math.max(0, Math.min(1, p)) * L);
      el.pulso.style.transform = 'translate(' + pt.x.toFixed(1) + 'px,' + pt.y.toFixed(1) + 'px)';
    }
    // el lienzo acompaña al pulso cuando baja más allá de lo que se ve
    function sigueConLaVista() {
      const R = E.run; if (!R || R.i < 0) return;
      const e = R.plan[R.i], it = e.tipo === 'nodo' ? e.n : e.tipo === 'viaje' ? e.con.a : null;
      if (!it) return;
      const y = it.y + (e.tipo === 'nodo' ? it.h : 0), vh = el.lienzo.clientHeight, st = el.lienzo.scrollTop;
      const meta = lim(y - vh * .62, 0, Math.max(0, el.lienzo.scrollHeight - vh));
      if (y + 30 > st + vh || y < st) el.lienzo.scrollTop = st + (meta - st) * .12;
    }
    function cancelaRun() {
      if (!E.run) return;
      E.run = null; el.pulso.classList.add('is-off'); raiz.classList.remove('is-corriendo'); el.probar.removeAttribute('aria-disabled');
    }
    // vuelve todo a «sin probar»: tinta, estados y fichas de salida
    function limpiaRunSolo() {
      cancelaRun();
      E.errCampo = null;
      todos().forEach(n => { n.est = 'idle'; n.salida = null; if (n.fichaEl) n.fichaEl.textContent = ''; if (n.nodoEl) n.el.classList.remove('is-skip'); });
      secuencias().forEach(s => { if (s.fin) { s.fin.est = 'idle'; if (s.fin.el) s.fin.el.classList.remove('is-ok', 'is-skip'); } });
      conRec.forEach(r => { r.p = 0; r.pe = 0; r.ap = false; });
    }
    function limpiaRun() {
      const habia = todos().some(n => n.salida || n.est !== 'idle');
      limpiaRunSolo();
      el.probar.dataset.e = 'reposo'; el.probarTxt.textContent = 'Testar';
      pintaTodos(); pintaEstado();
      if (habia) layout();
    }
    function pintaEstado() {
      if (E.run) return;
      const n = todos().length, falta = todos().filter(incompleto).length;
      el.estado.dataset.e = falta ? 'falta' : 'borrador';
      el.estadoTxt.textContent = falta ? 'Rascunho · falta ' + plural(falta, 'dado', 'dados') : 'Rascunho · ' + plural(n, 'passo', 'passos');
      el.probar.dataset.e = el.probar.dataset.e === 'corre' ? 'corre' : 'reposo';
      if (el.probar.dataset.e === 'reposo') el.probarTxt.textContent = 'Testar';
    }

    /* ── restablecer y arranque ───────────────────────────────────────── */
    function restablece() {
      cierraMenu(false); cancelaRun();
      E.evento = 'completo';
      pintaSegEvento();
      el.pista.classList.remove('is-fuera');
      E.seq = flujoInicial();
      limpiaRunSolo();
      layout();
      selecciona(porId.get('aviso') || E.seq[E.seq.length - 1], true);
      pintaTodos(); pintaEstado();
      el.probar.dataset.e = 'reposo'; el.probarTxt.textContent = 'Testar';
      anuncia('Flujo restablecido.');
    }
    function pintaSegEvento() {
      const bs = Array.from(el.segEvento.querySelectorAll('button'));
      bs.forEach((b, i) => { const on = b.dataset.evento === E.evento; b.setAttribute('aria-checked', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; if (on) el.segEvento.style.setProperty('--i', i); });
    }

    /* ── eventos del lienzo: clic y teclado ───────────────────────────── */
    function enfocables() {
      const out = [];
      const nodo = n => out.push({ e: n.nodoEl, n });
      const rec = (seq, ent) => {
        seq.forEach((n, i) => {
          const c = cons.find(c => c.a === n);
          if (c) out.push({ e: c.mas, c });
          nodo(n);
          if (n.ramas) n.ramas.forEach((r, j) => rec2(r.seq, n, j));
        });
        const f = seq.fin; if (f && seq.length) { const c = cons.find(c => c.a === f); if (c) out.push({ e: c.mas, c }); }
      };
      const rec2 = (seq, si, j) => {
        if (!seq.length) { const c = cons.find(c => c.a === seq.fin); if (c) out.push({ e: c.mas, c }); return; }
        rec(seq);
      };
      rec(E.seq);
      return out;
    }
    el.mundo.addEventListener('click', e => {
      const mas = e.target.closest('.es-mas');
      if (mas) { const rec = cons.find(c => c.mas === mas); if (rec) { if (E.menu && E.menu.rec === rec) cierraMenu(true); else abreMenu(rec, false); } return; }
      const x = e.target.closest('.es-x');
      const b = e.target.closest('.es-bloque');
      if (x && b) { quitaNodo(porId.get(b.dataset.id), false); return; }
      const chip = e.target.closest('.es-chip');
      if (chip && b) { const n = porId.get(b.dataset.id); if (n.salida) { n.salida.abierta = !n.salida.abierta; pintaSalida(n); layout(); } return; }
      const nodo = e.target.closest('.es-nodo');
      if (nodo && b) { const n = porId.get(b.dataset.id); selecciona(n, true); ponFoco(nodo, false); }
    });
    el.lienzo.addEventListener('keydown', e => {
      const t = e.target; if (t.closest('.es-menu')) return;
      const lista_ = enfocables(), i = lista_.findIndex(x => x.e === t);
      if (i < 0) return;
      const ir = j => { const x = lista_[lim(j, 0, lista_.length - 1)]; if (x) ponFoco(x.e, true); };
      if (e.key === 'ArrowDown') { e.preventDefault(); ir(i + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); ir(i - 1); }
      else if (e.key === 'Home') { e.preventDefault(); ir(0); }
      else if (e.key === 'End') { e.preventDefault(); ir(lista_.length - 1); }
      else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const x = lista_[i];
        if (x.c) abreMenu(x.c, true); else { selecciona(x.n, true); const p = el.panel.querySelector('.es-in, .es-seg-p button'); if (p && e.key === 'Enter') p.focus(); }
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && lista_[i].n) { e.preventDefault(); quitaNodo(lista_[i].n, true); }
    });
    el.lienzo.addEventListener('focusin', e => { const x = e.target.closest('.es-nodo, .es-mas'); if (x) { if (E.foco && E.foco !== x) E.foco.tabIndex = -1; E.foco = x; x.tabIndex = 0; } });

    el.probar.addEventListener('click', () => lanza());
    el.reset.addEventListener('click', () => restablece());
    el.segEvento.addEventListener('click', e => {
      const b = e.target.closest('button[data-evento]'); if (!b || b.dataset.evento === E.evento) return;
      E.evento = b.dataset.evento; pintaSegEvento();
      limpiaRun(); pintaPanel(false);
      anuncia('Evento de exemplo: ' + b.textContent);
    });
    el.segEvento.addEventListener('keydown', e => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      const bs = Array.from(el.segEvento.querySelectorAll('button')), j = lim(bs.findIndex(b => b.dataset.evento === E.evento) + (e.key === 'ArrowRight' ? 1 : -1), 0, bs.length - 1);
      e.preventDefault(); bs[j].click(); bs[j].focus();
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && E.menu) { e.preventDefault(); cierraMenu(true); } });
    new ResizeObserver(() => { layout(); }).observe(el.lienzo);

    // arranque
    E.seq = flujoInicial();
    layout();
    E.arrancando = false;
    selecciona(porId.get('aviso') || E.seq[E.seq.length - 1], false);
    pintaPanel(false);
    pintaTodos(); pintaEstado();
    pintaSegEvento();

    return {
      inserta: (tipo, indice) => inserta(tipo, null, indice),
      probar: lanza, restablece,
      evento: k => { if (EVENTOS[k]) { E.evento = k; pintaSegEvento(); limpiaRun(); pintaPanel(false); } },
      flujo: serializa,
    };
  }

  window.Eslabon = Eslabon;
})();
