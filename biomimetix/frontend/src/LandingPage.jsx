import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { createRipple } from './ripple.js';
import ForestTransition from './ForestTransition.jsx';

const ORGANISMS = [
  { name: 'Lotus leaf',         trait: 'Superhydrophobic self-cleaning nanostructure' },
  { name: 'Sharkskin',          trait: 'Turbulence-breaking dermal denticles' },
  { name: 'Spider silk',        trait: '5× tensile strength of high-grade steel' },
  { name: 'Mantis shrimp club', trait: '1,500 N impact at 23 m/s without fracture' },
  { name: 'Kingfisher bill',    trait: 'Zero-splash water entry via gradient taper' },
  { name: 'Gecko foot',         trait: 'Van der Waals dry adhesion — no glue needed' },
  { name: 'Boxfish shell',      trait: 'Rigid-yet-flexible interlocking lattice' },
  { name: 'Bone trabeculate',   trait: 'Porous load-path optimisation' },
];

const TITLE = 'BioMimetix AI';

/* ──────────────────────────────────────────────
   SVG organism — dramatic, self-drawing on mount
   ────────────────────────────────────────────── */
/* Timing helpers for the draw → hold → retract → pause loop */
function spiralLoop(drawDur, holdRatio, delay) {
  const total    = drawDur / 0.38;        // retract runs at same speed, hold fills middle
  const holdEnd  = 0.38 + holdRatio;
  return {
    pathLength : [0, 1, 1, 0],
    opacity    : [0, 1, 1, 0.15],
    transition : {
      duration    : total,
      times       : [0, 0.38, holdEnd, 1],
      repeat      : Infinity,
      repeatDelay : 1.2,
      ease        : 'easeInOut',
      delay,
    },
  };
}

function OrganismSVG() {
  const spokes = Array.from({ length: 24 }, (_, i) => {
    const a  = (i / 24) * Math.PI * 2;
    const r1 = 40, r2 = i % 4 === 0 ? 272 : i % 2 === 0 ? 214 : 152;
    return {
      x1: 300 + Math.cos(a) * r1, y1: 300 + Math.sin(a) * r1,
      x2: 300 + Math.cos(a) * r2, y2: 300 + Math.sin(a) * r2,
      bold: i % 4 === 0, delay: 0.5 + i * 0.022,
    };
  });

  const petals = Array.from({ length: 8 }, (_, i) => {
    const a = (i / 8) * Math.PI * 2;
    return {
      cx: 300 + Math.cos(a) * 214, cy: 300 + Math.sin(a) * 214,
      rot: (a * 180) / Math.PI + 90, delay: 1.6 + i * 0.1,
    };
  });

  const hexagons = Array.from({ length: 6 }, (_, i) => {
    const a = (i / 6) * Math.PI * 2;
    const hcx = 300 + Math.cos(a) * 152, hcy = 300 + Math.sin(a) * 152;
    const pts = Array.from({ length: 6 }, (__, j) => {
      const ha = (j / 6) * Math.PI * 2;
      return `${hcx + Math.cos(ha) * 13},${hcy + Math.sin(ha) * 13}`;
    }).join(' ');
    return { pts, cx: hcx, cy: hcy, delay: 1.9 + i * 0.12 };
  });

  const mycelium = [
    { sx: 300 + 272 * Math.cos(0.3),  sy: 300 + 272 * Math.sin(0.3),  angle: 0.72, len: 55 },
    { sx: 300 + 272 * Math.cos(1.5),  sy: 300 + 272 * Math.sin(1.5),  angle: 1.88, len: 46 },
    { sx: 300 + 272 * Math.cos(2.8),  sy: 300 + 272 * Math.sin(2.8),  angle: 2.42, len: 60 },
    { sx: 300 + 272 * Math.cos(4.2),  sy: 300 + 272 * Math.sin(4.2),  angle: 4.72, len: 42 },
    { sx: 300 + 272 * Math.cos(5.4),  sy: 300 + 272 * Math.sin(5.4),  angle: 5.12, len: 50 },
    { sx: 300 + 272 * Math.cos(3.6),  sy: 300 + 272 * Math.sin(3.6),  angle: 3.20, len: 38 },
  ];

  const dots = [
    { cx: 300, cy: 300, r: 9,  fill: 'rgba(63,207,196,0.95)',  glow: 'url(#strong-glow)', delay: 0.60 },
    { cx: 322, cy: 300, r: 5,  fill: 'rgba(63,207,196,0.85)',  glow: 'url(#bio-glow)',    delay: 0.85 },
    { cx: 300, cy: 344, r: 5,  fill: 'rgba(200,151,61,0.85)',  glow: 'url(#bio-glow)',    delay: 1.00 },
    { cx: 229, cy: 300, r: 5,  fill: 'rgba(155,123,196,0.85)', glow: 'url(#bio-glow)',    delay: 1.15 },
    { cx: 300, cy: 185, r: 5,  fill: 'rgba(63,207,196,0.85)',  glow: 'url(#bio-glow)',    delay: 1.30 },
    { cx: 486, cy: 300, r: 5,  fill: 'rgba(200,151,61,0.85)',  glow: 'url(#bio-glow)',    delay: 1.45 },
  ];

  return (
    <svg viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <filter id="bio-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="strong-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="9" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <circle cx="300" cy="300" r="290" fill="rgba(4,12,6,0.50)" />

      {/* Concentric rings — slow fade in, very gentle pulse */}
      {[272, 214, 152].map((r, i) => (
        <motion.circle key={r} cx="300" cy="300" r={r}
          stroke={`rgba(${i === 1 ? '155,123,196' : '63,207,196'},${0.26 - i * 0.05})`}
          strokeWidth={i === 0 ? 1.1 : 0.75}
          strokeDasharray={`${5 - i} ${11 - i * 2}`}
          animate={{ opacity: [0.14, 0.38, 0.14] }}
          transition={{ duration: 5 + i * 1.8, repeat: Infinity, ease: 'easeInOut', delay: 0.4 + i * 0.4 }}
        />
      ))}

      {/* Spokes — slow mirror breathe (in sync with spiral cycle) */}
      {spokes.map((s, i) => (
        <motion.line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2}
          stroke={`rgba(63,207,196,${s.bold ? 0.40 : 0.14})`}
          strokeWidth={s.bold ? 1.5 : 0.6}
          animate={{ pathLength: [0, 1, 1, 0], opacity: [0, s.bold ? 0.40 : 0.14, s.bold ? 0.40 : 0.14, 0] }}
          transition={{
            duration: 11, times: [0, 0.30, 0.65, 1],
            repeat: Infinity, repeatDelay: 2.5,
            ease: 'easeInOut', delay: s.delay,
          }}
        />
      ))}

      {/* ── Main Fibonacci spiral — draw → hold → retract → repeat ── */}
      <motion.path
        d="M300 300 A22 22 0 0 1 322 300 A44 44 0 0 1 300 344 A71 71 0 0 1 229 300 A115 115 0 0 1 300 185 A186 186 0 0 1 486 300 A301 301 0 0 1 300 601"
        stroke="rgba(63,207,196,0.94)" strokeWidth="4.8" strokeLinecap="round"
        filter="url(#strong-glow)"
        animate={spiralLoop(3.0, 0.34, 0.65)}
      />

      {/* ── Counter spiral — amber, phase-shifted ── */}
      <motion.path
        d="M300 300 A14 14 0 0 0 286 300 A28 28 0 0 0 300 272 A45 45 0 0 0 345 300 A73 73 0 0 0 300 373 A118 118 0 0 0 182 300"
        stroke="rgba(200,151,61,0.88)" strokeWidth="3.2" strokeLinecap="round"
        filter="url(#bio-glow)"
        animate={spiralLoop(2.4, 0.30, 1.4)}
      />

      {/* ── Inner spiral — purple, faster cycle ── */}
      <motion.path
        d="M300 300 A8 8 0 0 1 308 300 A16 16 0 0 1 300 316 A26 26 0 0 1 274 300 A42 42 0 0 1 300 258 A68 68 0 0 1 368 300"
        stroke="rgba(155,123,196,0.80)" strokeWidth="2.4" strokeLinecap="round"
        filter="url(#bio-glow)"
        animate={spiralLoop(2.0, 0.26, 2.2)}
      />

      {/* Chamber walls — staggered draw/retract, tied to main spiral phase */}
      {[
        { r: 22,  a1: 0,   a2: 90  },
        { r: 44,  a1: 90,  a2: 180 },
        { r: 71,  a1: 180, a2: 270 },
        { r: 115, a1: 270, a2: 360 },
      ].map(({ r, a1, a2 }, i) => {
        const ra1 = (a1 * Math.PI) / 180, ra2 = (a2 * Math.PI) / 180;
        return (
          <motion.path key={i}
            d={`M ${300 + Math.cos(ra1) * r} ${300 + Math.sin(ra1) * r} A ${r} ${r} 0 0 1 ${300 + Math.cos(ra2) * r} ${300 + Math.sin(ra2) * r}`}
            stroke="rgba(63,207,196,0.52)" strokeWidth="1.5"
            animate={{ pathLength: [0, 1, 1, 0], opacity: [0, 0.52, 0.52, 0] }}
            transition={{
              duration: 9, times: [0, 0.36, 0.68, 1],
              repeat: Infinity, repeatDelay: 1.5,
              ease: 'easeInOut', delay: 1.8 + i * 0.22,
            }}
          />
        );
      })}

      {/* Leaf petals — bloom in, mirror pulse */}
      {petals.map((p, i) => (
        <motion.ellipse key={i} cx={p.cx} cy={p.cy} rx="12" ry="30"
          transform={`rotate(${p.rot},${p.cx},${p.cy})`}
          stroke="rgba(110,214,136,0.52)" strokeWidth="1.4"
          filter="url(#bio-glow)"
          animate={{ opacity: [0, 0.52, 0.52, 0], scale: [0, 1, 1, 0] }}
          transition={{
            duration: 7, times: [0, 0.28, 0.72, 1],
            repeat: Infinity, repeatDelay: 3.0,
            ease: 'easeInOut', delay: p.delay,
          }}
        />
      ))}

      {/* Hexagonal cells — appear and fade */}
      {hexagons.map((h, i) => (
        <g key={i}>
          <motion.polygon points={h.pts}
            stroke="rgba(63,207,196,0.44)" strokeWidth="1.1"
            animate={{ opacity: [0, 0.44, 0.44, 0], scale: [0.4, 1, 1, 0.4] }}
            transition={{
              duration: 6, times: [0, 0.32, 0.68, 1],
              repeat: Infinity, repeatDelay: 4.0,
              ease: 'easeInOut', delay: h.delay,
            }}
          />
          <motion.circle cx={h.cx} cy={h.cy} r="3" fill="rgba(63,207,196,0.65)"
            filter="url(#bio-glow)"
            animate={{ opacity: [0, 0.65, 0.65, 0], scale: [0, 1, 1, 0] }}
            transition={{
              duration: 6, times: [0, 0.35, 0.65, 1],
              repeat: Infinity, repeatDelay: 4.0,
              ease: 'easeInOut', delay: h.delay + 0.2,
            }}
          />
        </g>
      ))}

      {/* Mycelium — grow out then retract, independent short cycles */}
      {mycelium.map((m, i) => {
        const ex = m.sx + Math.cos(m.angle) * m.len;
        const ey = m.sy + Math.sin(m.angle) * m.len;
        const d  = 2.5 + i * 0.18;
        return (
          <motion.g key={i}>
            <motion.line x1={m.sx} y1={m.sy} x2={ex} y2={ey}
              stroke="rgba(155,123,196,0.70)" strokeWidth="1.4" strokeLinecap="round"
              animate={{ pathLength: [0, 1, 1, 0], opacity: [0, 0.70, 0.70, 0] }}
              transition={{ duration: 5.5, times: [0, 0.38, 0.70, 1], repeat: Infinity, repeatDelay: 2.5, ease: 'easeInOut', delay: d }}
            />
            <motion.line
              x1={ex} y1={ey}
              x2={ex + Math.cos(m.angle + 0.68) * 24} y2={ey + Math.sin(m.angle + 0.68) * 24}
              stroke="rgba(155,123,196,0.50)" strokeWidth="0.9" strokeLinecap="round"
              animate={{ pathLength: [0, 1, 1, 0], opacity: [0, 0.50, 0.50, 0] }}
              transition={{ duration: 5.5, times: [0, 0.40, 0.72, 1], repeat: Infinity, repeatDelay: 2.5, ease: 'easeInOut', delay: d + 0.22 }}
            />
            <motion.line
              x1={ex} y1={ey}
              x2={ex + Math.cos(m.angle - 0.58) * 19} y2={ey + Math.sin(m.angle - 0.58) * 19}
              stroke="rgba(155,123,196,0.38)" strokeWidth="0.7" strokeLinecap="round"
              animate={{ pathLength: [0, 1, 1, 0], opacity: [0, 0.38, 0.38, 0] }}
              transition={{ duration: 5.5, times: [0, 0.42, 0.74, 1], repeat: Infinity, repeatDelay: 2.5, ease: 'easeInOut', delay: d + 0.38 }}
            />
            <motion.circle cx={m.sx} cy={m.sy} r="4.5" fill="rgba(155,123,196,0.80)"
              filter="url(#bio-glow)"
              animate={{ opacity: [0, 0.80, 0.80, 0], scale: [0, 1, 1, 0] }}
              transition={{ duration: 5.5, times: [0, 0.36, 0.72, 1], repeat: Infinity, repeatDelay: 2.5, ease: 'easeInOut', delay: d }}
            />
          </motion.g>
        );
      })}

      {/* Center + chamber dots — appear once, then breathe */}
      {dots.map((d, i) => (
        <motion.circle key={i} cx={d.cx} cy={d.cy} r={d.r} fill={d.fill}
          filter={d.glow}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: [0, 1, i === 0 ? 1.18 : 1.12, 1] }}
          transition={{
            opacity : { duration: 0.45, delay: d.delay },
            scale   : {
              duration: i === 0 ? 3.0 : 2.5,
              repeat: Infinity,
              repeatType: 'mirror',
              ease: 'easeInOut',
              delay: d.delay + 0.45,
              times: [0, 0.15, 0.55, 1],
            },
          }}
        />
      ))}
    </svg>
  );
}

/* ──────────────────────────────────────────────
   Main LandingPage
   ────────────────────────────────────────────── */
export default function LandingPage({ onEnter }) {
  const [orgIdx, setOrgIdx] = useState(0);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    const id = setInterval(() => setOrgIdx(i => (i + 1) % ORGANISMS.length), 3200);
    return () => clearInterval(id);
  }, []);

  const handleEnter = (e) => {
    createRipple(e, 'rgba(5,18,8,0.5)');
    setTransitioning(true);
  };

  return (
    <motion.div
      className="landing"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1, transition: { duration: 1.0, ease: 'easeOut' } }}
      exit={{ opacity: 0, scale: 0.92, filter: 'blur(18px)', transition: { duration: 0.55, ease: 'easeIn' } }}
    >
      {/* Canvas forest transition — appears on CTA click */}
      {transitioning && <ForestTransition onComplete={onEnter} />}

      {/* SVG organism — right column */}
      <div className="landing-orb" aria-hidden="true">
        <OrganismSVG />
      </div>

      {/* Main content — left column */}
      <div className="landing-content">

        <motion.span className="landing-badge"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.2, duration: 0.6 } }}
        >
          Biomimicry × Industrial Design AI
        </motion.span>

        <h1 className="landing-title" aria-label={TITLE}>
          {TITLE.split('').map((ch, i) => (
            <motion.span key={i}
              initial={{ opacity: 0, y: 34, filter: 'blur(9px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ delay: 0.4 + i * 0.046, duration: 0.56, ease: [0.16, 1, 0.3, 1] }}
            >
              {ch === ' ' ? ' ' : ch}
            </motion.span>
          ))}
        </h1>

        <motion.p className="landing-tagline"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 1.1, duration: 0.7 } }}
        >
          4 billion years of R&amp;D.&ensp;Zero patents.
        </motion.p>

        <motion.div className="landing-organism-cycle"
          initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { delay: 1.4 } }}
        >
          <AnimatePresence mode="wait">
            <motion.div key={orgIdx} className="landing-organism-label"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0, transition: { duration: 0.44 } }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.26 } }}
            >
              <strong>{ORGANISMS[orgIdx].name}</strong>
              <span>{ORGANISMS[orgIdx].trait}</span>
            </motion.div>
          </AnimatePresence>
        </motion.div>

        <motion.div className="landing-stats"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 1.65, duration: 0.6 } }}
        >
          {[['3M+', 'species catalogued'], ['4B yr', 'of evolution'], ['0', 'patents held']].map(([v, l]) => (
            <div key={v} className="landing-stat">
              <strong>{v}</strong>
              <span>{l}</span>
            </div>
          ))}
        </motion.div>

        <motion.button
          className="landing-cta ripple-btn"
          onClick={handleEnter}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 1.95, duration: 0.65, ease: [0.34, 1.56, 0.64, 1] } }}
          whileHover={{ scale: 1.06, transition: { duration: 0.2 } }}
          whileTap={{ scale: 0.97 }}
        >
          Enter the Forest <ArrowRight size={20} />
        </motion.button>
      </div>
    </motion.div>
  );
}
