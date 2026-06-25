import { useEffect, useRef } from 'react';

const DURATION = 1100; // ms — intentionally shorter/lighter than ForestTransition

/* Same colour journey as ForestTransition but smaller palette */
const PALETTES = [
  { p: [63,207,196],  s: [110,214,136], fade: [7,19,10]  }, // →step2
  { p: [90,210,120],  s: [63,207,196],  fade: [5,22,8]   }, // →step3
  { p: [120,210,80],  s: [90,210,120],  fade: [6,20,5]   }, // →step4
  { p: [160,200,60],  s: [200,170,61],  fade: [8,16,4]   }, // →step5
  { p: [200,170,61],  s: [220,200,80],  fade: [12,14,3]  }, // →step6
  { p: [228,190,50],  s: [245,225,100], fade: [16,12,3]  }, // →step7
  { p: [255,220,80],  s: [255,248,170], fade: [20,15,4]  }, // →step8
];

function rgba(c, a) { return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }

/* Slightly elliptical, softly wobbly ring — looks like water surface, not a UI circle */
function organicRing(ctx, cx, cy, r, seed) {
  const seg = 32;
  ctx.beginPath();
  for (let i = 0; i <= seg; i++) {
    const a  = (i / seg) * Math.PI * 2;
    const wr = r + Math.sin(a * 3 + seed) * r * 0.016 + Math.sin(a * 7 - seed * 0.6) * r * 0.008;
    const x  = cx + Math.cos(a) * wr;
    const y  = cy + Math.sin(a) * wr * 0.80; // gentle ellipse — like looking at water from a slight angle
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
}

export default function StepTransition({ onComplete, stepIndex = 0 }) {
  const onCompleteRef = useRef(onComplete);
  useEffect(() => { onCompleteRef.current = onComplete; });

  const canvasRef = useRef(null);

  useEffect(() => {
    const idx = Math.max(0, Math.min(stepIndex, PALETTES.length - 1));
    const pal = PALETTES[idx];

    const canvas = canvasRef.current;
    const ctx    = canvas.getContext('2d');
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const maxR = Math.hypot(cx, cy) * 1.38;

    /* Ring wobble seed — set once so rings are stable across frames */
    const seed = Math.random() * Math.PI * 2;

    /* Spore/pollen particles — small, drift with slight arc */
    const spores = Array.from({ length: 55 }, () => ({
      a    : Math.random() * Math.PI * 2,
      speed: 0.7 + Math.random() * 3.2,
      r    : 0.7 + Math.random() * 2.2,
      arc  : (Math.random() - 0.5) * 0.08, // slight lateral drift
    }));

    /* Tiny filament threads — like mycelium tendrils in light */
    const filaments = Array.from({ length: 14 }, () => ({
      a  : Math.random() * Math.PI * 2,
      len: 30 + Math.random() * 70,
      delay: Math.random() * 0.35,
    }));

    const startTime = performance.now();
    let rafId;

    function frame(now) {
      const p = Math.min((now - startTime) / DURATION, 1);
      ctx.clearRect(0, 0, W, H);

      /* ── Soft radial glow bloom (primary light, not blinding) ── */
      const bR = Math.sin(Math.PI * p * 0.8) * maxR * 0.78;
      if (bR > 1) {
        const bl = ctx.createRadialGradient(cx, cy, 0, cx, cy, bR);
        bl.addColorStop(0,    rgba(pal.p, 0.28 * Math.sin(Math.PI * p)));
        bl.addColorStop(0.35, rgba(pal.s, 0.16 * Math.sin(Math.PI * p)));
        bl.addColorStop(1,    'transparent');
        ctx.fillStyle = bl;
        ctx.fillRect(0, 0, W, H);
      }

      /* ── 3 organic ripple rings, tightly staggered ── */
      [0, 0.10, 0.22].forEach((delay, ri) => {
        if (p < delay) return;
        const rp    = (p - delay) / (1 - delay);
        const r     = maxR * rp;
        const alpha = 0.55 * (1 - rp);

        ctx.strokeStyle = rgba(pal.p, alpha);
        ctx.lineWidth   = 2.0 * (1 - rp * 0.65);
        organicRing(ctx, cx, cy, r, seed + ri);
        ctx.stroke();

        if (r > 20) {
          ctx.strokeStyle = rgba(pal.s, alpha * 0.32);
          ctx.lineWidth   = 0.8;
          organicRing(ctx, cx, cy, r * 0.60, seed + ri + 1);
          ctx.stroke();
        }
      });

      /* ── Spore drift outward ── */
      if (p > 0.08) {
        const sp = (p - 0.08) / 0.92;
        spores.forEach(s => {
          const r  = s.speed * sp * 180;
          const da = s.arc * sp * 3;
          const x  = cx + Math.cos(s.a + da) * r;
          const y  = cy + Math.sin(s.a + da) * r;
          const a  = Math.sin(Math.PI * sp) * 0.65;
          ctx.beginPath();
          ctx.arc(x, y, s.r, 0, Math.PI * 2);
          ctx.fillStyle = rgba(pal.s, a);
          ctx.fill();
        });
      }

      /* ── Filament threads (like mycelium flashing in light) ── */
      if (p > 0.12 && p < 0.75) {
        filaments.forEach(f => {
          if (p < f.delay + 0.12) return;
          const fp = (p - f.delay - 0.12) / 0.50;
          if (fp > 1) return;
          const alpha = Math.sin(Math.PI * fp) * 0.30;
          const ex = cx + Math.cos(f.a) * f.len * fp;
          const ey = cy + Math.sin(f.a) * f.len * fp;
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(ex, ey);
          ctx.strokeStyle = rgba(pal.p, alpha);
          ctx.lineWidth   = 0.8;
          ctx.stroke();
        });
      }

      /* ── Fade to the step's deep background ── */
      if (p > 0.60) {
        const fade = (p - 0.60) / 0.40;
        ctx.fillStyle = `rgba(${pal.fade[0]},${pal.fade[1]},${pal.fade[2]},${fade * fade * 0.94})`;
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
  }, [stepIndex]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{ position: 'fixed', inset: 0, zIndex: 25, pointerEvents: 'none' }}
    />
  );
}
