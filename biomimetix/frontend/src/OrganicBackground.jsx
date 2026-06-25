import { useEffect, useRef } from 'react';

const PARTICLE_COUNT = 120;
const MAX_TRAIL = 70;
const HUES = [168, 94, 196, 36, 155, 210]; // teal · lime · spore · amber · green · blue

/* Organic flow field — two overlapping sine-cosine waves create sweeping, river-like curves */
function getFlowAngle(x, y, t, w, h) {
  const nx = x / w;
  const ny = y / h;
  const a =
    Math.sin(nx * 1.6 + t * 0.38) * Math.cos(ny * 2.4 - t * 0.28) +
    Math.sin(nx * 4.2 - t * 0.18) * Math.cos(ny * 1.1 + t * 0.44) * 0.42;
  return a * Math.PI * 1.5;
}

function makeParticle(w, h, stagger = false) {
  const p = {
    x: Math.random() * w,
    y: Math.random() * h,
    vx: 0,
    vy: 0,
    history: [],
    age: 0,
    maxAge: 220 + Math.random() * 240,
    hue: HUES[Math.floor(Math.random() * HUES.length)],
    speed: 0.65 + Math.random() * 1.15,
    weight: Math.random() < 0.14 ? 1.9 : Math.random() < 0.40 ? 1.2 : 0.75,
  };
  if (stagger) p.age = Math.floor(Math.random() * p.maxAge * 0.55);
  return p;
}

export default function OrganicBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let rafId;
    let particles = [];
    let time = 0;

    const init = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      particles = Array.from({ length: PARTICLE_COUNT }, () =>
        makeParticle(canvas.width, canvas.height, true)
      );
    };

    const draw = () => {
      const { width: w, height: h } = canvas;
      ctx.clearRect(0, 0, w, h);
      time += 0.006;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        const angle = getFlowAngle(p.x, p.y, time, w, h);
        p.vx = p.vx * 0.88 + Math.cos(angle) * p.speed * 0.12;
        p.vy = p.vy * 0.88 + Math.sin(angle) * p.speed * 0.12;
        p.x += p.vx;
        p.y += p.vy;
        p.age++;

        p.history.push({ x: p.x, y: p.y });
        if (p.history.length > MAX_TRAIL) p.history.shift();

        const len = p.history.length;
        if (len < 3) continue;

        const lifeRatio = Math.max(0, 1 - p.age / p.maxAge);

        /* Draw trail segments with quadratic fade */
        const visible = Math.min(len - 1, 38);
        const startIdx = len - 1 - visible;

        for (let j = startIdx; j < len - 1; j++) {
          const t = (j - startIdx) / visible;
          const alpha = t * t * lifeRatio * 0.30;
          if (alpha < 0.007) continue;
          ctx.beginPath();
          ctx.moveTo(p.history[j].x, p.history[j].y);
          ctx.lineTo(p.history[j + 1].x, p.history[j + 1].y);
          ctx.strokeStyle = `hsla(${p.hue}, 86%, 72%, ${alpha})`;
          ctx.lineWidth = 0.35 + t * p.weight * 0.85;
          ctx.lineCap = 'round';
          ctx.stroke();
        }

        /* Bioluminescent glowing tip */
        if (lifeRatio > 0.08) {
          const tip = p.history[len - 1];
          const glowR = p.weight * 7;
          const grad = ctx.createRadialGradient(tip.x, tip.y, 0, tip.x, tip.y, glowR);
          grad.addColorStop(0,   `hsla(${p.hue}, 100%, 94%, ${lifeRatio * 0.55})`);
          grad.addColorStop(0.4, `hsla(${p.hue}, 100%, 80%, ${lifeRatio * 0.18})`);
          grad.addColorStop(1,   `hsla(${p.hue}, 100%, 60%, 0)`);
          ctx.beginPath();
          ctx.arc(tip.x, tip.y, glowR, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();
        }

        /* Respawn */
        if (
          p.age > p.maxAge ||
          p.x < -40 || p.x > w + 40 ||
          p.y < -40 || p.y > h + 40
        ) {
          particles[i] = makeParticle(w, h);
        }
      }

      rafId = requestAnimationFrame(draw);
    };

    init();
    draw();
    const onResize = () => init();
    window.addEventListener('resize', onResize);
    return () => { cancelAnimationFrame(rafId); window.removeEventListener('resize', onResize); };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: 'fixed', inset: 0, zIndex: -1,
        width: '100%', height: '100%', pointerEvents: 'none',
      }}
    />
  );
}
