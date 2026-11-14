/* =====================================================================
   Centro · Moxen
   Un centro de control de cristal líquido: mosaicos de vidrio de distinto
   tamaño (un bento) sobre un fondo vivo. El fondo es la mitad del efecto:
   orbes grandes y borrosos que derivan despacio (un canvas pequeño que se
   estira) y, por encima, aros y discos nítidos que el cristal curva de
   verdad. En Chromium cada mosaico lleva su propio backdrop-filter con un
   mapa de desplazamiento del tamaño exacto del vidrio (un bisel de borde
   redondeado: la refracción es más fuerte en el borde y se apaga hacia
   dentro) y un fleco de color por canal; en el resto cae a un desenfoque
   con brillo, sin que se rompa nada.

   Qué hace cada pieza
   · Brillo y volumen: deslizadores verticales. Se llenan con un filo de
     luz, su ícono cambia con el nivel (rayos del sol, ondas del altavoz) y
     el mosaico se estira un poco hacia donde arrastras —y rebota al
     soltar— con un resorte. El brillo afecta a la escena de verdad: el
     fondo se oscurece o florece con una bruma clara. El volumen mueve
     el ecualizador del reproductor.
   · Conectividad: botones redondos con resorte. «Avión» apaga a los demás
     en cascada y, al desactivarlo, los devuelve como estaban.
   · Reproductor: carátula, barra que se arrastra (y flechas), mandos y un
     ecualizador que respira con el volumen. El reloj corre solo.
   · Foco: un interruptor de resorte; la bolita se estira al
     pulsarla y también se arrastra.
   · Linterna: alumbra la escena. Rotación: el candado gira.
   Teclado: flechas, Inicio/Fin y Re Pág/Av Pág en los deslizadores; Espacio
   o Enter en el resto.

   Se monta solo sobre [data-centro]:

     const c = Centro(document.querySelector('[data-centro]'), {
       brillo: .72, volumen: .42,       // niveles de partida (0 a 1)
       reproduce: true,                 // si la música «suena» al empezar
       onCambia: (que, valor) => { … }, // 'brillo' | 'volumen' | 'red' | 'avion' | 'linterna' …
     });
     c.brillo(.3);  c.volumen(.8);  c.conmuta('avion');  c.reproduce(false);

   Personalizar: los colores del fondo y los acentos, en las variables al
   principio de centro.css (--ce-c-* son los orbes: los lee este archivo);
   el tamaño del bento, en --ce-c y --ce-g; la fuerza de la refracción y el
   ancho del bisel, en FUERZA y BISEL de abajo; los resortes, en RES.
   Solo se anima transform y opacity. Sin dependencias.
   ===================================================================== */
(function () {
  'use strict';

  const FUERZA = 64;       // cuánto desplaza el borde del cristal (px, de lado a lado del mapa)
  const BISEL = 44;        // el ancho del borde que refracta (px)
  const RES = {
    luz: { k: 150, c: 22 },        // la luz de la escena sigue al deslizador con un poco de pereza
    nivel: { k: 640, c: 44 },      // el relleno del deslizador
    estira: { k: 250, c: 11 },     // el mosaico que se estira: rebota al soltar
    agarre: { k: 300, c: 26 },
    bola: { k: 340, c: 19 },       // la bolita del interruptor
  };
  const SVGNS = 'http://www.w3.org/2000/svg';
  const REFRACTA = /Chrome\//.test(navigator.userAgent) && (typeof CSS === 'undefined' || !CSS.supports || CSS.supports('backdrop-filter', 'blur(1px)'));

  /* ── resortes: el solver de siempre ───────────────────────────────── */
  const resorte = (x, p) => ({ x, v: 0, meta: x, k: p.k, c: p.c });
  function avanza(r, h) { r.v += (r.k * (r.meta - r.x) - r.c * r.v) * h; r.x += r.v * h; }
  const reposo = (r, e) => Math.abs(r.v) < (e || .01) * 4 && Math.abs(r.meta - r.x) < (e || .01);
  const limita = (v, a, b) => Math.max(a, Math.min(b, v));

  // un resorte convertido en curva CSS linear() (para transiciones y WAAPI)
  function muelle(k, c) {
    const pts = [0]; let x = 0, v = 0, t = 0;
    while (t < 3) {
      v += (k * (1 - x) - c * v) / 240; x += v / 240; t += 1 / 240; pts.push(x);
      if (t > .15 && Math.abs(1 - x) < .001 && Math.abs(v) < .01) break;
    }
    const out = [];
    for (let i = 0; i <= 40; i++) out.push(pts[Math.round(i / 40 * (pts.length - 1))].toFixed(4));
    out[40] = '1';
    return 'linear(' + out.join(', ') + ')';
  }

  /* azar con semilla: los orbes y el ecualizador son siempre los mismos */
  function mulberry32(s) {
    return () => {
      s = s + 0x6D2B79F5 | 0;
      let t = Math.imul(s ^ s >>> 15, 1 | s);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  /* El motor: un solo requestAnimationFrame para todo lo que se mueve. Cada
     pieza ofrece paso(h) —avanza sus resortes y dice si sigue en marcha— y
     pinta(t). Cuando nada se mueve, el motor duerme. */
  const motor = (function () {
    const vivos = new Set(); let raf = 0, previo = 0;
    function cuadro(ms) {
      raf = 0;
      const dt = previo ? limita((ms - previo) / 1000, 0, 1 / 30) : 1 / 60; previo = ms;
      const n = Math.max(1, Math.ceil(dt * 240));
      Array.from(vivos).forEach(o => {
        let activo = false;
        for (let i = 0; i < n; i++) activo = o.paso(dt / n) || activo;
        o.pinta(ms / 1000);
        if (!activo) vivos.delete(o);
      });
      if (vivos.size) raf = requestAnimationFrame(cuadro); else previo = 0;
    }
    return { despierta(o) { vivos.add(o); if (!raf) { previo = 0; raf = requestAnimationFrame(cuadro); } } };
  })();

  const rgba = (hex, a) => {
    const m = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex.trim());
    return m ? 'rgba(' + parseInt(m[1], 16) + ',' + parseInt(m[2], 16) + ',' + parseInt(m[3], 16) + ',' + a + ')' : hex;
  };

  /* =====================================================================
     El fondo: orbes que derivan. Un canvas de 256 × 160 que el navegador
     estira: al ser tan pequeño, cada degradado sale ya desenfocado.
     ===================================================================== */
  function Fondo(lienzo, reduce) {
    const g = lienzo.getContext('2d'), W = 256, H = 160;
    lienzo.width = W; lienzo.height = H;
    const cs = getComputedStyle(document.documentElement);
    const col = n => cs.getPropertyValue('--ce-c-' + n).trim() || '#888888';
    const colores = { base: col('base'), hondo: col('hondo'), malva: col('malva'), cielo: col('cielo'), naranja: col('naranja'), durazno: col('durazno') };
    // x, y, r en fracciones del ancho; ax, ay: cuánto vagan; fx, fy: con qué prisa (rad/s); px, py: fases
    const ORBES = [
      { c: 'hondo', x: .96, y: .96, r: .56, ax: .05, ay: .05, fx: .12, fy: .1, px: 0, py: 1, a: .9 },
      { c: 'hondo', x: .02, y: .06, r: .46, ax: .04, ay: .06, fx: .1, fy: .13, px: 2, py: 0, a: .8 },
      { c: 'naranja', x: .16, y: .84, r: .6, ax: .08, ay: .07, fx: .17, fy: .13, px: .3, py: 1.2, a: .96 },
      { c: 'cielo', x: .86, y: .3, r: .6, ax: .07, ay: .09, fx: .14, fy: .18, px: 2.1, py: .4, a: .96 },
      { c: 'malva', x: .46, y: .1, r: .52, ax: .11, ay: .06, fx: .12, fy: .16, px: 4, py: 2.6, a: .92 },
      { c: 'durazno', x: .66, y: .94, r: .34, ax: .08, ay: .05, fx: .19, fy: .15, px: 1.4, py: 3, a: .8 },
      { c: 'cielo', x: .3, y: .46, r: .3, ax: .09, ay: .1, fx: .21, fy: .17, px: 5, py: 1.7, a: .6 },
      { c: 'malva', x: .72, y: .62, r: .3, ax: .08, ay: .08, fx: .16, fy: .2, px: 3.2, py: .8, a: .62 },
    ];
    function pinta(t) {
      g.fillStyle = colores.base; g.fillRect(0, 0, W, H);
      ORBES.forEach(o => {
        const x = (o.x + o.ax * Math.sin(t * o.fx + o.px)) * W, y = (o.y + o.ay * Math.cos(t * o.fy + o.py)) * H;
        const r = o.r * W * (1 + .06 * Math.sin(t * .23 + o.px)), c = colores[o.c];
        const gr = g.createRadialGradient(x, y, 0, x, y, r);
        gr.addColorStop(0, rgba(c, o.a)); gr.addColorStop(.5, rgba(c, o.a * .5)); gr.addColorStop(1, rgba(c, 0));
        g.fillStyle = gr; g.fillRect(0, 0, W, H);
      });
    }
    let reloj = 14, ultimo = 0;     // la deriva arranca en un punto bonito, no en cero
    pinta(reloj);
    // el reloj propio avanza por cuadros: la página y el vídeo caminan igual
    const obj = { paso() { return true; }, pinta(s) { const d = ultimo ? limita(s - ultimo, 0, .05) : 1 / 60; ultimo = s; reloj += d; pinta(reloj); } };
    return { arranca() { if (!reduce) motor.despierta(obj); } };
  }

  /* =====================================================================
     El cristal: un mapa de desplazamiento para cada mosaico.
     Para cada píxel de un rectángulo de esquinas redondeadas se calcula la
     distancia al borde y la dirección hacia afuera; dentro de un bisel de
     BISEL px el desplazamiento crece hacia el borde (como en una gota de
     vidrio) y fuera de él es cero. El mapa codifica dx en el canal rojo y
     dy en el verde (128 = nada). El filtro lo aplica tres veces con fuerzas
     distintas, una por canal de color, y las suma: el fleco del vidrio.
     ===================================================================== */
  function mapa(w, h, radio) {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    const g = c.getContext('2d'), im = g.createImageData(w, h), d = im.data;
    const hw = w / 2, hh = h / 2, r = Math.min(radio, hw, hh), bz = Math.min(BISEL, r + 8);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const px = x + .5 - hw, py = y + .5 - hh;
        const qx = Math.abs(px) - (hw - r), qy = Math.abs(py) - (hh - r);
        let dist, nx, ny;
        if (qx > 0 && qy > 0) { const l = Math.hypot(qx, qy); dist = l - r; nx = qx / l * Math.sign(px); ny = qy / l * Math.sign(py); }
        else if (qx > qy) { dist = qx - r; nx = Math.sign(px); ny = 0; }
        else { dist = qy - r; nx = 0; ny = Math.sign(py); }
        const prof = -dist;                        // hacia adentro desde el borde
        let m = 0;
        if (prof < bz) { const u = 1 - Math.max(0, prof) / bz; m = Math.pow(u, 2.2); }
        const i = (y * w + x) * 4;
        d[i] = Math.round(128 + 127 * nx * m); d[i + 1] = Math.round(128 + 127 * ny * m); d[i + 2] = 128; d[i + 3] = 255;
      }
    }
    g.putImageData(im, 0, 0);
    return c.toDataURL('image/png');
  }
  function Cristal(defs, teselas) {
    if (!REFRACTA || !defs) return;
    document.documentElement.classList.add('ce-refracta');
    teselas.forEach((el, n) => {
      const id = 'ce-f-' + n, f = document.createElementNS(SVGNS, 'filter');
      f.setAttribute('id', id); f.setAttribute('x', '0'); f.setAttribute('y', '0'); f.setAttribute('width', '100%'); f.setAttribute('height', '100%');
      f.setAttribute('color-interpolation-filters', 'sRGB');
      defs.appendChild(f);
      let w0 = 0, h0 = 0;
      function dibuja() {
        const w = el.offsetWidth, h = el.offsetHeight;
        if (!w || !h || (w === w0 && h === h0)) return;
        w0 = w; h0 = h;
        const r = parseFloat(getComputedStyle(el).borderTopLeftRadius) || 40;
        const canal = (esc, m, sal) => '<feDisplacementMap in="SourceGraphic" in2="m" scale="' + esc + '" xChannelSelector="R" yChannelSelector="G" result="d' + sal + '"/><feColorMatrix in="d' + sal + '" type="matrix" values="' + m + '" result="' + sal + '"/>';
        f.innerHTML = '<feImage href="' + mapa(w, h, r) + '" preserveAspectRatio="none" result="m"/>' +
          canal(FUERZA, '1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0', 'r') +
          canal(FUERZA * .9, '0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0', 'g') +
          canal(FUERZA * .8, '0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0', 'b') +
          '<feBlend in="r" in2="g" mode="screen" result="rg"/><feBlend in="rg" in2="b" mode="screen"/>';
        const v = 'url(#' + id + ') blur(2px) saturate(1.7) brightness(1.06)';
        el.style.webkitBackdropFilter = v; el.style.backdropFilter = v;
      }
      if (typeof ResizeObserver === 'function') new ResizeObserver(dibuja).observe(el); else dibuja();
      dibuja();
    });
  }

  /* =====================================================================
     Los deslizadores verticales
     ===================================================================== */
  function Deslizador(el, op) {
    const llena = el.querySelector('.ce-llena'), numEl = el.querySelector('.ce-rot-val b');
    const rayos = Array.from(el.querySelectorAll('.ce-rayos path')), disco = el.querySelector('.ce-sol-disco');
    const ondas = Array.from(el.querySelectorAll('.ce-onda')), tache = el.querySelector('.ce-tache');
    const tipo = el.dataset.desl, reduce = op.reduce;
    let val = limita(+el.dataset.valor / 100, 0, 1), arrastre = null, tDato = 0, dentro = null, cubre = null;
    const vis = resorte(val, RES.nivel), est = resorte(0, RES.estira), agarre = resorte(0, RES.agarre);
    const alto = () => el.offsetHeight || 1;
    const va = (r, m) => { r.meta = m; if (reduce) { r.x = m; r.v = 0; } };

    function icono(v) {
      if (tipo === 'brillo') {
        // los rayos entran de dos en dos (0°/180°, 90°/270°, 45°/225°, 135°/315°) y el disco crece
        rayos.forEach((p, i) => { const j = [0, 2, 1, 3, 0, 2, 1, 3][i]; p.style.setProperty('--k', limita((v - .1 - j * .2) * 6.2, 0, 1).toFixed(3)); });
        disco.setAttribute('r', (3.3 + 1.7 * v).toFixed(2));
      } else {
        const k1 = limita(v * 10, 0, 1), k2 = limita((v - .25) * 7, 0, 1), k3 = limita((v - .55) * 7, 0, 1);
        [k1, k2, k3].forEach((k, i) => ondas[i].style.setProperty('--k', k.toFixed(3)));
        tache.style.setProperty('--kx', limita(1 - v * 30, 0, 1).toFixed(3));
      }
    }
    function pinta() {
      llena.style.transform = 'translate3d(0,' + ((1 - vis.x) * 100).toFixed(3) + '%,0)';
      icono(limita(vis.x, 0, 1));
      const d = vis.x * alto() > 86, c = vis.x > .86;
      if (d !== dentro) { dentro = d; el.classList.toggle('is-dentro', d); }
      if (c !== cubre) { cubre = c; el.classList.toggle('is-cubre', c); }
      const s = est.x, a = Math.abs(s), g = agarre.x;
      if (a < .0004 && Math.abs(g) < .0004) { if (el.style.transform) el.style.transform = ''; return; }
      el.style.transformOrigin = s >= 0 ? '50% 100%' : '50% 0%';
      el.style.transform = 'scale(' + (1 - .05 * a + .02 * g).toFixed(4) + ',' + (1 + .105 * a + .02 * g).toFixed(4) + ')';
    }
    const obj = {
      paso(h) {
        if (arrastre) {
          arrastre.vel *= 1 - Math.min(1, h * 9);            // sin movimiento, la velocidad se apaga
          est.meta = limita(arrastre.sobre * 2.6, -1, 1) + limita(-arrastre.vel / 4200, -.5, .5);
          est.meta = limita(est.meta, -1, 1);
        }
        avanza(vis, h); avanza(est, h); avanza(agarre, h);
        return !!arrastre || !reposo(vis, .0006) || !reposo(est, .001) || !reposo(agarre, .001);
      },
      pinta,
    };
    function fija(v, desdeTeclado) {
      const nuevo = limita(v, 0, 1);
      if (desdeTeclado && nuevo === val) est.v += (v > val ? 1 : -1) * 3.2;     // tope: un empujón elástico
      else if (desdeTeclado) est.v += (nuevo > val ? 1 : -1) * 1.1;
      val = nuevo; va(vis, val);
      const pct = Math.round(val * 100);
      numEl.textContent = pct; el.setAttribute('aria-valuenow', pct); el.setAttribute('aria-valuetext', pct + ' %');
      el.classList.add('is-dato'); clearTimeout(tDato);
      if (!arrastre) tDato = setTimeout(() => el.classList.remove('is-dato'), 1000);
      if (op.onCambia) op.onCambia(val);
      motor.despierta(obj);
    }

    el.addEventListener('pointerdown', e => {
      if (e.button > 0) return;
      try { el.setPointerCapture(e.pointerId); } catch (_) {}
      arrastre = { id: e.pointerId, y0: e.clientY, v0: val, ult: e.clientY, t: performance.now(), vel: 0, mueve: false, sobre: 0 };
      va(agarre, 1); el.classList.add('is-arrastre', 'is-dato'); clearTimeout(tDato);
      motor.despierta(obj);
    });
    el.addEventListener('pointermove', e => {
      if (!arrastre || e.pointerId !== arrastre.id) return;
      const dy = arrastre.y0 - e.clientY;
      if (!arrastre.mueve && Math.abs(dy) > 4) arrastre.mueve = true;
      if (!arrastre.mueve) return;
      const raw = arrastre.v0 + dy / (alto() * .86), nuevo = limita(raw, 0, 1);
      arrastre.sobre = raw - nuevo;
      const ahora = performance.now(), dt = (ahora - arrastre.t) / 1000;
      if (dt > .001) { arrastre.vel = arrastre.vel * .65 + ((e.clientY - arrastre.ult) / dt) * .35; arrastre.ult = e.clientY; arrastre.t = ahora; }
      if (nuevo !== val) { val = nuevo; va(vis, val); fija(val); }
      else if (reduce) { /* sin movimiento: nada que estirar */ }
    });
    function suelta(e) {
      if (!arrastre || (e && e.pointerId !== arrastre.id)) return;
      const a = arrastre; arrastre = null;
      va(agarre, 0); va(est, 0); el.classList.remove('is-arrastre');
      if (!a.mueve && e && e.type === 'pointerup') {            // un toque: salta a donde tocaste
        const r = el.getBoundingClientRect();
        fija(1 - (e.clientY - r.top) / r.height);
      }
      clearTimeout(tDato); tDato = setTimeout(() => el.classList.remove('is-dato'), 1000);
      motor.despierta(obj);
    }
    el.addEventListener('pointerup', suelta);
    el.addEventListener('pointercancel', suelta);
    el.addEventListener('keydown', e => {
      const k = e.key; let v = val;
      if (k === 'ArrowUp' || k === 'ArrowRight') v += e.shiftKey ? .1 : .05;
      else if (k === 'ArrowDown' || k === 'ArrowLeft') v -= e.shiftKey ? .1 : .05;
      else if (k === 'PageUp') v += .1; else if (k === 'PageDown') v -= .1;
      else if (k === 'Home') v = 0; else if (k === 'End') v = 1; else return;
      e.preventDefault(); fija(v, true);
    });
    pinta(); icono(val);
    numEl.textContent = Math.round(val * 100);
    return { fija: v => fija(v), get valor() { return val; } };
  }

  /* =====================================================================
     El interruptor de resorte (Foco)
     La bolita es un resorte: pulsarla la ensancha, arrastrarla la lleva y
     soltarla la asienta con rebote. La velocidad la estira como una gota.
     ===================================================================== */
  function Interruptor(btn, op) {
    const bola = btn.querySelector('.ce-sw-bola'), pista = btn.querySelector('.ce-sw-pista'), reduce = op.reduce;
    let on = false, arr = null;
    const x = resorte(0, RES.bola), g = resorte(0, RES.agarre);
    const recorrido = () => Math.max(1, btn.offsetWidth - 8 - bola.offsetWidth);
    const va = (r, m) => { r.meta = m; if (reduce) { r.x = m; r.v = 0; } };
    function pinta() {
      const rec = recorrido(), vel = Math.min(.5, Math.abs(x.v) * .09);
      bola.style.transform = 'translate3d(' + (x.x * rec).toFixed(2) + 'px,0,0) scale(' + (1 + .32 * g.x + vel).toFixed(3) + ',' + (1 - .07 * g.x - vel * .35).toFixed(3) + ')';
      pista.style.setProperty('--x', limita(x.x, 0, 1).toFixed(3));
    }
    const obj = {
      paso(h) { avanza(x, h); avanza(g, h); return !!arr || !reposo(x, .0008) || !reposo(g, .001); },
      pinta,
    };
    function pon(v, avisa) {
      on = v; btn.setAttribute('aria-checked', v ? 'true' : 'false'); va(x, v ? 1 : 0);
      if (avisa !== false && op.onCambia) op.onCambia(on);
      motor.despierta(obj);
    }
    btn.addEventListener('pointerdown', e => {
      if (e.button > 0) return;
      try { btn.setPointerCapture(e.pointerId); } catch (_) {}
      arr = { id: e.pointerId, x0: e.clientX, xi: x.x, mueve: false };
      va(g, 1); motor.despierta(obj);
    });
    btn.addEventListener('pointermove', e => {
      if (!arr || e.pointerId !== arr.id) return;
      const dx = e.clientX - arr.x0;
      if (!arr.mueve && Math.abs(dx) > 3) arr.mueve = true;
      if (arr.mueve) x.meta = limita(arr.xi + dx / recorrido(), -.06, 1.06);
      if (reduce) { x.x = x.meta; }
    });
    function suelta(e) {
      if (!arr || e.pointerId !== arr.id) return;
      const a = arr; arr = null; va(g, 0);
      if (!a.mueve) pon(!on); else pon(x.x + x.v * .05 > .5);
    }
    btn.addEventListener('pointerup', suelta);
    btn.addEventListener('pointercancel', e => { if (arr && e.pointerId === arr.id) { arr = null; va(g, 0); pon(on, false); } });
    btn.addEventListener('click', e => { if (e.detail === 0) pon(!on); });        // teclado: Espacio / Enter
    pinta();
    return { pon, get activo() { return on; } };
  }

  /* =====================================================================
     El reproductor: una pista que «suena» (sin audio), con una barra que se
     arrastra, mandos y un ecualizador que sigue al volumen.
     ===================================================================== */
  const PISTAS = [
    { t: 'Luz de fim de tarde', s: 'Sessão instrumental', dur: 214, c: ['#ffb169', '#9b63e6', '#fff1c9', '#4b2d9f'] },
    { t: 'Maré de verão', s: 'Piano e cordas', dur: 187, c: ['#7fd0ff', '#5b6df0', '#e8f6ff', '#2a2f9c'] },
    { t: 'Brasas', s: 'Ritmos suaves', dur: 241, c: ['#ffd27a', '#ff7e5f', '#fff5d6', '#8a2f4a'] },
  ];
  const mmss = s => { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };

  function Reproductor(sec, op) {
    const q = s => sec.querySelector(s), reduce = op.reduce;
    const barra = q('.ce-barra'), avance = q('.ce-avance'), perilla = q('.ce-perilla');
    const ahoraEl = q('.ce-t-ahora'), restoEl = q('.ce-t-resto');
    const play = q('.ce-m-play'), prev = q('.ce-m-prev'), sig = q('.ce-m-sig');
    const art = q('.ce-art'), tit = q('.ce-tit'), sub = q('.ce-sub'), barras = Array.from(sec.querySelectorAll('.ce-eq i'));
    let idx = 0, tiempo = 72, suena = op.reduce ? false : op.suena !== false, vol = op.volumen, sub0 = -1, scrub = false;
    const amp = resorte(0, { k: 90, c: 12 });
    const dur = () => PISTAS[idx].dur;

    function pintaTiempo(fuerza) {
      const seg = Math.floor(tiempo);
      if (seg !== sub0 || fuerza) {
        sub0 = seg; ahoraEl.textContent = mmss(tiempo); restoEl.textContent = '-' + mmss(dur() - tiempo);
        barra.setAttribute('aria-valuenow', seg); barra.setAttribute('aria-valuetext', mmss(tiempo));
      }
    }
    function pinta(s) {
      const f = limita(tiempo / dur(), 0, 1);
      avance.style.transform = 'scaleX(' + f.toFixed(4) + ')';
      perilla.style.setProperty('--px', (f * barra.offsetWidth).toFixed(1) + 'px');
      pintaTiempo(false);
      // el ecualizador: cada barra sube y baja a su ritmo; el volumen manda la altura
      barras.forEach((b, i) => {
        const o = .5 + .5 * Math.sin(s * (5.3 + 1.9 * i) + i * 2.1) * Math.sin(s * (2.1 + .7 * i) + i);
        b.style.transform = 'scaleY(' + limita(.16 + amp.x * (.12 + .88 * o), .12, 1).toFixed(3) + ')';
      });
    }
    const obj = {
      paso(h) {
        if (suena) { tiempo += h; if (tiempo >= dur()) { cambia(1, true); } }
        amp.meta = suena ? .1 + .9 * vol : 0; avanza(amp, h);
        return suena || !reposo(amp, .003);
      },
      pinta,
    };
    function textoCambia(p, clase, texto, dir) {
      const vieja = p.querySelector('span'), nueva = document.createElement('span');
      nueva.textContent = texto; nueva.className = clase;
      if (reduce || !vieja) { if (vieja) vieja.remove(); p.appendChild(nueva); return; }
      vieja.animate([{ opacity: 1, transform: 'translateY(0)', filter: 'blur(0)' }, { opacity: 0, transform: 'translateY(' + (-10 * dir) + 'px)', filter: 'blur(6px)' }], { duration: 280, easing: 'ease-in', fill: 'forwards' });
      p.appendChild(nueva);
      nueva.animate([{ opacity: 0, transform: 'translateY(' + (12 * dir) + 'px)', filter: 'blur(6px)' }, { opacity: 1, transform: 'translateY(0)', filter: 'blur(0)' }], { duration: 640, delay: 120, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'backwards' });
      setTimeout(() => vieja.remove(), 300);
    }
    function cambia(d, solo) {
      idx = (idx + d + PISTAS.length) % PISTAS.length; tiempo = 0; sub0 = -1;
      const p = PISTAS[idx];
      textoCambia(tit, 'ce-tit-s', p.t, d); textoCambia(sub, 'ce-sub-s', p.s, d);
      sec.style.setProperty('--ce-a1', p.c[0]); sec.style.setProperty('--ce-a2', p.c[1]); sec.style.setProperty('--ce-a3', p.c[2]); sec.style.setProperty('--ce-a4', p.c[3]);
      if (!reduce) art.animate([{ transform: 'scale(.86) rotate(' + (-4 * d) + 'deg)', opacity: .6 }, { transform: 'scale(1) rotate(0)', opacity: 1 }], { duration: 700, easing: op.muelle });
      pintaTiempo(true); motor.despierta(obj);
    }
    function pon(v) {
      suena = v; play.setAttribute('aria-pressed', v ? 'true' : 'false'); play.setAttribute('aria-label', v ? 'Pausa' : 'Reproducir');
      if (op.onCambia) op.onCambia(v);
      motor.despierta(obj);
    }
    const toca = (btn, f) => btn.addEventListener('click', () => {
      if (!reduce) btn.animate([{ transform: 'scale(.82)' }, { transform: 'scale(1)' }], { duration: 650, easing: op.muelle });
      f();
    });
    toca(play, () => pon(!suena)); toca(prev, () => { if (tiempo > 3) { tiempo = 0; pintaTiempo(true); motor.despierta(obj); } else cambia(-1); }); toca(sig, () => cambia(1));

    // la barra: arrastrar o tocar fija la posición; las flechas mueven 5 s
    const frac = e => { const r = barra.getBoundingClientRect(); return limita((e.clientX - r.left) / r.width, 0, 1); };
    barra.addEventListener('pointerdown', e => {
      if (e.button > 0) return;
      try { barra.setPointerCapture(e.pointerId); } catch (_) {}
      scrub = true; barra.classList.add('is-act'); tiempo = frac(e) * dur(); pintaTiempo(true); motor.despierta(obj); pinta(performance.now() / 1000);
    });
    barra.addEventListener('pointermove', e => { if (scrub) { tiempo = frac(e) * dur(); pintaTiempo(true); motor.despierta(obj); pinta(performance.now() / 1000); } });
    const fin = () => { scrub = false; barra.classList.remove('is-act'); };
    barra.addEventListener('pointerup', fin); barra.addEventListener('pointercancel', fin);
    barra.addEventListener('keydown', e => {
      const d = e.key === 'ArrowRight' || e.key === 'ArrowUp' ? 5 : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? -5 : 0;
      if (!d) return;
      e.preventDefault(); tiempo = limita(tiempo + d, 0, dur() - .5); pintaTiempo(true); motor.despierta(obj); pinta(performance.now() / 1000);
    });
    play.setAttribute('aria-pressed', suena ? 'true' : 'false');
    play.setAttribute('aria-label', suena ? 'Pausa' : 'Reproducir');
    pintaTiempo(true); pinta(0);
    if (suena || true) motor.despierta(obj);
    return { pon, volumen(v) { vol = v; motor.despierta(obj); }, get suena() { return suena; } };
  }

  /* =====================================================================
     El centro
     ===================================================================== */
  function Centro(raiz, opciones) {
    const o = Object.assign({ brillo: .72, volumen: .42, reproduce: true, onCambia: null }, opciones);
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const aviso = (q, v) => { if (o.onCambia) o.onCambia(q, v); };
    const curvaMuelle = muelle(300, 14);
    raiz.style.setProperty('--ce-muelle', curvaMuelle);
    const $$ = s => Array.from(raiz.querySelectorAll(s));

    // el fondo vivo
    const fondo = Fondo(raiz.querySelector('.ce-orbes'), reduce);
    fondo.arranca();

    // el brillo de la escena: un resorte lento que mueve --ce-b (velo y bruma del CSS)
    const luz = resorte(o.brillo, RES.luz);
    raiz.style.setProperty('--ce-b', luz.x.toFixed(4));
    const objLuz = {
      paso(h) { avanza(luz, h); return !reposo(luz, .0008); },
      pinta() { raiz.style.setProperty('--ce-b', limita(luz.x, 0, 1).toFixed(4)); },
    };
    const luzA = v => { luz.meta = v; if (reduce) { luz.x = v; luz.v = 0; } motor.despierta(objLuz); };

    const sliders = {};
    const repro = raiz.querySelector('.ce-rep') ? Reproductor(raiz.querySelector('.ce-rep'), { reduce, suena: o.reproduce, volumen: o.volumen, muelle: curvaMuelle, onCambia: s => aviso('reproduce', s) }) : { volumen() {}, pon() {} };
    $$('.ce-desl').forEach(el => {
      const nombre = el.dataset.desl;
      el.dataset.valor = String(Math.round((nombre === 'brillo' ? o.brillo : o.volumen) * 100));
      sliders[nombre] = Deslizador(el, {
        reduce,
        onCambia: v => { if (nombre === 'brillo') luzA(v); else repro.volumen(v); aviso(nombre, v); },
      });
    });

    // los botones redondos de conectividad: «Avión» apaga a los demás en cascada y los devuelve
    const bts = {}; $$('.ce-bt').forEach(b => { bts[b.dataset.bt] = b; });
    let antes = null;
    function pon(b, v, retardo) {
      const hacer = () => {
        b.setAttribute('aria-pressed', v ? 'true' : 'false');
        if (v) { b.classList.remove('is-gesto'); void b.offsetWidth; b.classList.add('is-gesto'); setTimeout(() => b.classList.remove('is-gesto'), 1100); }
        const c = b.querySelector('.ce-bt-c');
        if (!reduce) c.animate([{ transform: 'scale(.86)' }, { transform: 'scale(1)' }], { duration: 700, easing: curvaMuelle });
      };
      if (retardo && !reduce) setTimeout(hacer, retardo); else hacer();
    }
    $$('.ce-bt').forEach(b => b.addEventListener('click', () => {
      const nombre = b.dataset.bt, v = b.getAttribute('aria-pressed') !== 'true';
      pon(b, v);
      if (nombre === 'avion') {
        if (v) {
          antes = {}; ['red', 'cerca', 'datos'].forEach(n => { antes[n] = bts[n].getAttribute('aria-pressed') === 'true'; });
          ['red', 'cerca', 'datos'].forEach((n, i) => { if (antes[n]) pon(bts[n], false, 140 + i * 110); });
        } else if (antes) {
          ['red', 'cerca', 'datos'].forEach((n, i) => { if (antes[n]) pon(bts[n], true, 140 + i * 110); });
          antes = null;
        }
      } else if (v && bts.avion.getAttribute('aria-pressed') === 'true') {
        pon(bts.avion, false); antes = null;        // encender una conexión saca del modo avión
      }
      aviso(nombre, v);
    }));

    // concentración: el interruptor de resorte y su texto
    const foc = raiz.querySelector('.ce-foc'), focS = foc.querySelector('.ce-foc-s');
    const sw = Interruptor(foc.querySelector('.ce-sw'), { reduce, onCambia: v => {
      foc.classList.toggle('is-on', v); focS.textContent = v ? 'Pet pausado' : 'Pet ativo'; aviso('concentracion', v);
    } });

    // mosaicos-botón: linterna (alumbra la escena) y rotación (el candado gira)
    $$('.ce-tb').forEach(t => t.addEventListener('click', () => {
      const v = t.getAttribute('aria-pressed') !== 'true';
      t.setAttribute('aria-pressed', v ? 'true' : 'false');
      if (!reduce) t.animate([{ transform: 'scale(.92, .92)' }, { transform: 'scale(1, 1)' }], { duration: 750, easing: curvaMuelle });
      if (t.classList.contains('ce-lin')) raiz.classList.toggle('ce-lin-on', v);
      aviso(t.classList.contains('ce-lin') ? 'linterna' : 'rotacion', v);
    }));

    // el cristal: un filtro de refracción por mosaico
    Cristal(document.getElementById('ce-filtros'), $$('.ce-t'));

    return {
      brillo(v) { sliders.brillo.fija(v); },
      volumen(v) { sliders.volumen.fija(v); },
      conmuta(n) { const b = bts[n]; if (b) b.click(); },
      reproduce(v) { repro.pon(v); },
      concentracion(v) { sw.pon(v); },
    };
  }

  window.Centro = Centro;
  document.querySelectorAll('[data-centro]').forEach(el => { el._centro = Centro(el, { onCambia: window.ceAviso || null }); });
})();
