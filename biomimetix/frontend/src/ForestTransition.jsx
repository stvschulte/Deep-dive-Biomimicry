import { useEffect, useRef } from 'react';

const DURATION = 1600; // ms total

/* ── Color palette — 7 entries for transitions TO steps 2-8 ──
   Journey: deep forest → forest floor → canopy → clearing → meadow → golden → dawn */
const PALETTES = [
  { p: [63,207,196],  s: [110,214,136], fade: [7,19,10],   leafHue: 95,  leafLight: 45, bright: 0.38 }, // →step2
  { p: [90,210,120],  s: [63,207,196],  fade: [5,22,8],    leafHue:108,  leafLight: 47, bright: 0.42 }, // →step3
  { p: [120,210,80],  s: [90,210,120],  fade: [6,20,5],    leafHue:118,  leafLight: 50, bright: 0.47 }, // →step4
  { p: [160,200,60],  s: [200,170,61],  fade: [8,16,4],    leafHue: 88,  leafLight: 52, bright: 0.52 }, // →step5
  { p: [200,170,61],  s: [220,200,80],  fade: [12,14,3],   leafHue: 68,  leafLight: 54, bright: 0.58 }, // →step6
  { p: [228,190,50],  s: [245,225,100], fade: [16,12,3],   leafHue: 48,  leafLight: 58, bright: 0.66 }, // →step7
  { p: [255,220,80],  s: [255,248,170], fade: [20,15,4],   leafHue: 38,  leafLight: 65, bright: 0.76 }, // →step8
];

function lerp(a, b, t) { return a + (b - a) * t; }
function rgba(c, a)     { return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }

/* ── Leaf with midrib + lateral veins ── */
function drawLeaf(ctx, x, y, size, rot, hue, lightness, alpha) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.globalAlpha = alpha;

  ctx.beginPath();
  ctx.moveTo(0, size * 0.52);
  ctx.bezierCurveTo(-size * 0.48, size * 0.16, -size * 0.48, -size * 0.24, 0, -size * 0.52);
  ctx.bezierCurveTo( size * 0.48, -size * 0.24,  size * 0.48, size * 0.16, 0,  size * 0.52);
  ctx.fillStyle = `hsla(${hue}, 68%, ${lightness}%, 1)`;
  ctx.fill();

  ctx.beginPath();
  ctx.moveTo(0,  size * 0.48); ctx.lineTo(0, -size * 0.48);
  ctx.strokeStyle = `hsla(${hue + 20}, 82%, 80%, 0.48)`;
  ctx.lineWidth = Math.max(0.4, size * 0.055);
  ctx.stroke();

  for (let i = 1; i <= 3; i++) {
    const vy = -size * 0.5 + i * size * 0.3;
    const vl = size * 0.28 * (1.18 - i * 0.14);
    ctx.beginPath();
    ctx.moveTo(0, vy); ctx.lineTo(-vl, vy - vl * 0.65);
    ctx.moveTo(0, vy); ctx.lineTo( vl, vy - vl * 0.65);
    ctx.strokeStyle = `hsla(${hue + 20}, 82%, 80%, 0.28)`;
    ctx.lineWidth = Math.max(0.25, size * 0.028);
    ctx.stroke();
  }

  ctx.globalAlpha = 1;
  ctx.restore();
}

/* ── Dandelion seed: dot + radiating hairs ── */
function drawSeed(ctx, x, y, size, angle, alpha) {
  ctx.save();
  ctx.translate(x, y);
  ctx.globalAlpha = alpha;

  ctx.beginPath();
  ctx.arc(0, 0, size * 0.18, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(255,240,160,0.9)';
  ctx.fill();

  const hairCount = 8;
  for (let i = 0; i < hairCount; i++) {
    const a = (i / hairCount) * Math.PI * 2 + angle;
    const len = size * (0.7 + Math.sin(a * 3) * 0.2);
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(Math.cos(a) * len, Math.sin(a) * len);
    ctx.strokeStyle = 'rgba(255,240,160,0.5)';
    ctx.lineWidth = 0.5;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(Math.cos(a) * len, Math.sin(a) * len, size * 0.09, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,240,180,0.7)';
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  ctx.restore();
}

/* ── Slightly imperfect (organic) ring path ── */
function organicRing(ctx, cx, cy, r, ellipseY, wobble, seedAngle) {
  const segments = 28;
  ctx.beginPath();
  for (let i = 0; i <= segments; i++) {
    const a = (i / segments) * Math.PI * 2;
    const wr = r + Math.sin(a * 4 + seedAngle) * wobble + Math.sin(a * 7 - seedAngle * 0.5) * wobble * 0.4;
    const x = cx + Math.cos(a) * wr;
    const y = cy + Math.sin(a) * wr * ellipseY;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
}

export default function ForestTransition({ onComplete, stepIndex = 0 }) {
  /* Keep latest onComplete in a ref so the effect never needs to re-run for it */
  const onCompleteRef = useRef(onComplete);
  useEffect(() => { onCompleteRef.current = onComplete; });

  const canvasRef = useRef(null);

  useEffect(() => {
    const idx  = Math.max(0, Math.min(stepIndex, PALETTES.length - 1));
    const pal  = PALETTES[idx];
    const prog = idx / (PALETTES.length - 1); // 0 → 1 across journey

    const canvas = canvasRef.current;
    const ctx    = canvas.getContext('2d');
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const maxR = Math.hypot(cx, cy) * 1.42;

    /* Leaves — colour + size varies with step */
    const leafCount = Math.round(70 + prog * 30);
    const leaves = Array.from({ length: leafCount }, () => {
      const angle = Math.random() * Math.PI * 2;
      const speed = 5 + Math.random() * 10;
      const hueShift = pal.leafHue + (Math.random() - 0.5) * 28;
      return {
        x: cx + (Math.random() - 0.5) * 120,
        y: cy + (Math.random() - 0.5) * 120,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 1.2,
        rot: Math.random() * Math.PI * 2,
        rotSpeed: (Math.random() - 0.5) * 0.17,
        size: 9 + Math.random() * (16 + prog * 12), // bigger leaves in later steps
        hue: hueShift,
        light: pal.leafLight + Math.random() * 8,
        delay: Math.random() * 0.44,
      };
    });

    /* Dandelion seeds — appear for steps 4+ */
    const seedCount = Math.round(Math.max(0, (idx - 2) * 10));
    const seeds = Array.from({ length: seedCount }, () => ({
      x: cx + (Math.random() - 0.5) * 60,
      y: cy + (Math.random() - 0.5) * 60,
      vx: (Math.random() - 0.5) * 4,
      vy: -1.5 - Math.random() * 2.5,
      size: 8 + Math.random() * 14,
      angle: Math.random() * Math.PI * 2,
      delay: 0.15 + Math.random() * 0.5,
    }));

    /* Water drops */
    const drops = Array.from({ length: 22 }, () => ({
      angle: Math.random() * Math.PI * 2,
      speed: 1.8 + Math.random() * 4.5,
      size:  2 + Math.random() * 5,
    }));

    /* Ring wobble seeds — fixed per animation for consistency */
    const ringSeeds = Array.from({ length: 7 }, () => Math.random() * Math.PI * 2);

    /* Light shaft directions for late steps */
    const shaftCount = Math.round((idx - 3) * 2.5);
    const shafts = Array.from({ length: Math.max(0, shaftCount) }, (_, i) => ({
      angle: (i / shaftCount) * Math.PI * 2 + Math.random() * 0.4,
      width: 18 + Math.random() * 40,
    }));

    const startTime = performance.now();
    let rafId;

    function frame(now) {
      const elapsed = now - startTime;
      const p = Math.min(elapsed / DURATION, 1);

      ctx.clearRect(0, 0, W, H);

      /* ── Central bioluminescent bloom ── */
      const bR = Math.sin(Math.PI * p * 0.86) * maxR;
      if (bR > 0) {
        const bl = ctx.createRadialGradient(cx, cy, 0, cx, cy, bR);
        bl.addColorStop(0,    `rgba(${lerp(220,255,prog)},${lerp(255,245,prog)},${lerp(240,200,prog)},${pal.bright * Math.sin(Math.PI * p)})`);
        bl.addColorStop(0.12, rgba(pal.p, pal.bright * 0.85 * Math.sin(Math.PI * p)));
        bl.addColorStop(0.42, rgba(pal.s, pal.bright * 0.42 * Math.sin(Math.PI * p)));
        bl.addColorStop(1,    'transparent');
        ctx.fillStyle = bl;
        ctx.fillRect(0, 0, W, H);
      }

      /* ── Light shafts (later steps) ── */
      if (shafts.length > 0 && p > 0.05 && p < 0.85) {
        const sa = Math.sin(Math.PI * p) * pal.bright * 0.28;
        shafts.forEach(sh => {
          ctx.save();
          ctx.translate(cx, cy);
          ctx.rotate(sh.angle);
          const sg = ctx.createLinearGradient(0, 0, 0, maxR);
          sg.addColorStop(0,   `rgba(255,248,200,${sa})`);
          sg.addColorStop(0.5, `rgba(255,230,140,${sa * 0.6})`);
          sg.addColorStop(1,    'transparent');
          ctx.fillStyle = sg;
          ctx.beginPath();
          ctx.moveTo(-sh.width / 2, 0);
          ctx.lineTo(sh.width / 2, 0);
          ctx.lineTo(sh.width * 0.8, maxR);
          ctx.lineTo(-sh.width * 0.8, maxR);
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        });
      }

      /* ── Organic water ripples (7 staggered, slightly imperfect) ── */
      [0, 0.06, 0.14, 0.24, 0.36, 0.50, 0.65].forEach((delay, ri) => {
        if (p < delay) return;
        const rp    = (p - delay) / (1 - delay);
        const r     = maxR * rp;
        const alpha = 0.68 * (1 - rp);
        const wobble = r * 0.025;
        const ellY  = 0.78 + ri * 0.014; // slightly more circular as rings expand

        ctx.strokeStyle = rgba(pal.p, alpha);
        ctx.lineWidth   = 2.6 * (1 - rp * 0.62);
        organicRing(ctx, cx, cy, r, ellY, wobble, ringSeeds[ri]);
        ctx.stroke();

        if (r > 30) {
          ctx.strokeStyle = rgba(pal.s, alpha * 0.36);
          ctx.lineWidth   = 0.9;
          organicRing(ctx, cx, cy, r * 0.65, ellY, wobble * 0.5, ringSeeds[ri] + 1);
          ctx.stroke();
        }
      });

      /* ── Water-drop splatter ── */
      if (p < 0.60) {
        const dp = p / 0.60;
        drops.forEach(d => {
          const x = cx + Math.cos(d.angle) * d.speed * dp * 88;
          const y = cy + Math.sin(d.angle) * d.speed * dp * 88 + dp * dp * 38;
          const a = Math.sin(Math.PI * dp) * 0.68;
          const grd = ctx.createRadialGradient(x, y, 0, x, y, d.size * (1 + dp));
          grd.addColorStop(0,   `rgba(${lerp(180,255,prog)},${lerp(250,248,prog)},${lerp(230,200,prog)},${a})`);
          grd.addColorStop(0.5, rgba(pal.p, a * 0.5));
          grd.addColorStop(1,   'transparent');
          ctx.fillStyle = grd;
          ctx.beginPath();
          ctx.arc(x, y, d.size * (1 + dp * 0.55), 0, Math.PI * 2);
          ctx.fill();
        });
      }

      /* ── Flying leaves ── */
      leaves.forEach(leaf => {
        const leafEnd = Math.min(leaf.delay + 0.80, 1.0);
        if (p < leaf.delay || p > leafEnd) return;
        const lp  = (p - leaf.delay) / (leafEnd - leaf.delay);
        const x   = leaf.x + leaf.vx * lp * 62;
        const y   = leaf.y + leaf.vy * lp * 62 + lp * lp * 48;
        const rot = leaf.rotation + leaf.rotSpeed * lp * 62;
        drawLeaf(ctx, x, y, leaf.size, rot, leaf.hue, leaf.light, Math.sin(Math.PI * lp) * 0.90);
      });

      /* ── Dandelion seeds (mid–late steps) ── */
      seeds.forEach(seed => {
        const seedEnd = Math.min(seed.delay + 0.75, 1.0);
        if (p < seed.delay || p > seedEnd) return;
        const sp = (p - seed.delay) / (seedEnd - seed.delay);
        const x  = seed.x + seed.vx * sp * 55;
        const y  = seed.y + seed.vy * sp * 55;
        drawSeed(ctx, x, y, seed.size, seed.angle + sp * 0.5, Math.sin(Math.PI * sp) * 0.85);
      });

      /* ── Spore/pollen cluster ── */
      if (p > 0.16 && p < 0.88) {
        const sp = (p - 0.16) / 0.72;
        for (let i = 0; i < 40; i++) {
          const a  = (i / 40) * Math.PI * 2 + p * 1.7;
          const r  = 48 + sp * 210 + Math.sin(a * 5 + p * 8) * 24;
          const sx = cx + Math.cos(a) * r;
          const sy = cy + Math.sin(a) * r;
          const pa = Math.sin(Math.PI * sp) * (0.40 + prog * 0.25);
          ctx.beginPath();
          ctx.arc(sx, sy, 1.2 + Math.sin(a * 4) * 0.8, 0, Math.PI * 2);
          ctx.fillStyle = rgba(pal.s, pa);
          ctx.fill();
        }
      }

      /* ── Fade to step bg colour ── */
      if (p > 0.66) {
        const fade = (p - 0.66) / 0.34;
        ctx.fillStyle = `rgba(${pal.fade[0]},${pal.fade[1]},${pal.fade[2]},${fade * fade * 0.95})`;
        ctx.fillRect(0, 0, W, H);
      }

      if (p < 1) {
        rafId = requestAnimationFrame(frame);
      } else {
        onCompleteRef.current?.();
      }
    }

    rafId = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafId);
  }, [stepIndex]); // onComplete intentionally omitted — tracked via ref above

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{ position: 'fixed', inset: 0, zIndex: 25, pointerEvents: 'none' }}
    />
  );
}
