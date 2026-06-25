import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowRight,
  Box,
  Check,
  Clipboard,
  ExternalLink,
  Eye,
  FileText,
  Pencil,
  Printer,
  RefreshCw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Video,
} from 'lucide-react';
import OrganicBackground from './OrganicBackground.jsx';
import LandingPage from './LandingPage.jsx';
import StepTransition from './StepTransition.jsx';
import { createRipple } from './ripple.js';

const API_BASE = '/api';
const configuredApiBase = import.meta.env.VITE_API_BASE || API_BASE;
const normalizedApiBase = configuredApiBase.replace(/\/$/, '');
const BACKEND_BASE = normalizedApiBase.replace('/api', '');

const HELMET_IMAGES = [
  '/images/fallback/product_helmets/helmet-1.jpg',
  '/images/fallback/product_helmets/helmet-2.jpg',
  '/images/fallback/product_helmets/helmet-3.jpg',
  '/images/fallback/product_helmets/helmet-4.jpg',
  '/images/fallback/product_helmets/helmet-5.jpg',
];

/* ── Framer Motion variants ── */
const stepVariants = {
  initial: { clipPath: 'circle(28px at 50% 56%)', opacity: 0 },
  animate: {
    clipPath: 'circle(150% at 50% 56%)',
    opacity: 1,
    transition: { duration: 0.78, ease: [0.16, 1, 0.3, 1] },
  },
  exit: {
    clipPath: 'circle(0px at 50% 56%)',
    opacity: 0,
    transition: { duration: 0.38, ease: [0.7, 0, 0.84, 0] },
  },
};

const containerVariants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.07, delayChildren: 0.18 } },
};

const cardVariants = {
  initial: { opacity: 0, scale: 0.84, y: 14 },
  animate: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.40, ease: [0.16, 1, 0.3, 1] } },
};

const iconBubbleVariants = {
  initial: { opacity: 0, scale: 0.6, rotate: -12 },
  animate: { opacity: 1, scale: 1, rotate: 0, transition: { duration: 0.50, ease: [0.34, 1.56, 0.64, 1] } },
};

const STEPS = [
  'Product Analyse',
  'Product Functions',
  'Biomimicry',
  'Principle Abstraction',
  'Ideation',
  '2D Image',
  '3D Model',
  'Evaluate',
];

const emptyEvaluation = {
  failure: '',
  lostNuance: '',
  printFunction: '',
  nextIteration: '',
};

const resolveImageUrl = (url) => {
  if (!url) return '';
  if (url.startsWith('http') || url.startsWith('/images/')) return url;
  return `${BACKEND_BASE}${url}`;
};

const uniqueFunctions = (items) => {
  const seen = new Set();
  return items
    .map((item) => ({
      component: item.component || 'Product component',
      function: item.function || 'Undefined function',
    }))
    .filter((item) => {
      const key = item.function.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
};

function App() {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [productName, setProductName] = useState('');
  const [breakdown, setBreakdown] = useState([]);
  const [productImage, setProductImage] = useState(null);
  const [selectedFunction, setSelectedFunction] = useState(null);
  const [biomimicryOptions, setBiomimicryOptions] = useState([]);
  const [selectedOrganism, setSelectedOrganism] = useState(null);
  const [organismImage, setOrganismImage] = useState(null);
  const [explorationDone, setExplorationDone] = useState(false);
  const [principles, setPrinciples] = useState([]);
  const [sketchPack, setSketchPack] = useState(null);
  const [selectedPrinciple, setSelectedPrinciple] = useState(null);
  const [sketchDone, setSketchDone] = useState(false);
  const [concepts, setConcepts] = useState([]);
  const [selectedConcept, setSelectedConcept] = useState(null);
  const [conceptRefined, setConceptRefined] = useState(false);
  const [finalPrompt, setFinalPrompt] = useState('');
  const [promptUsed, setPromptUsed] = useState(false);
  const [stlCreated, setStlCreated] = useState(false);
  const [evaluation, setEvaluation] = useState(emptyEvaluation);
  const [error, setError] = useState('');
  const [health, setHealth] = useState({ status: 'checking' });
  const [explodedView, setExplodedView] = useState(null);
  const [imageRedoLoading, setImageRedoLoading] = useState(false);
  const [imageRedoHint, setImageRedoHint] = useState('');

  /* ── New state for about page + function actions ── */
  const [showAbout, setShowAbout] = useState(false);
  const [pageTurning, setPageTurning] = useState(false);
  const [rejectedFunctions, setRejectedFunctions] = useState(new Set());
  const [approvedFunctions, setApprovedFunctions] = useState(new Set());
  const [helmetImageIndex, setHelmetImageIndex] = useState(0);

  /* ── Step transition orchestration ── */
  const [displayedStep, setDisplayedStep]   = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const pendingStepRef       = useRef(null);
  const skipNextTransition   = useRef(false);

  useEffect(() => {
    if (step === displayedStep) return;
    // Landing→step1: LandingPage handles its own transition; reset: jump directly
    if (step <= 1 || skipNextTransition.current) {
      skipNextTransition.current = false;
      setDisplayedStep(step);
      return;
    }
    pendingStepRef.current = step;
    setIsTransitioning(true);
  }, [step, displayedStep]);

  const handleStepTransitioned = useCallback(() => {
    if (pendingStepRef.current !== null) {
      setDisplayedStep(pendingStepRef.current);
      pendingStepRef.current = null;
    }
    setIsTransitioning(false);
  }, []);

  const functions = useMemo(
    () => uniqueFunctions(breakdown),
    [breakdown],
  );

  const requestJson = async (endpoint, payload) => {
    const res = await fetch(`${normalizedApiBase}/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'The request failed.');
    }
    return res.json();
  };

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${normalizedApiBase}/health`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error('API unavailable');
        return res.json();
      })
      .then((data) => setHealth(data))
      .catch(() => setHealth({ status: 'offline', gemini_configured: false }));
    return () => controller.abort();
  }, []);

  const runAction = async (action) => {
    setLoading(true);
    setError('');
    try {
      await action();
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const analyzeProduct = () => runAction(async () => {
    if (!productName.trim()) return;
    const [parts, image] = await Promise.all([
      requestJson('deconstruct', { product: productName.trim() }),
      requestJson('product-image', { product: productName.trim() }),
    ]);
    setBreakdown(parts);
    setProductImage({
      url: resolveImageUrl(image.image_url),
      source: image.source,
      sourceUrl: image.source_url,
      searchUrl: image.search_url,
      license: image.license,
    });
    setSelectedFunction(null);
    setRejectedFunctions(new Set());
    setApprovedFunctions(new Set());
    setHelmetImageIndex(0);
    setStep(2);
  });

  const isHelmet = () => productName.toLowerCase().includes('helmet');

  const cycleHelmetImage = () => {
    const url = HELMET_IMAGES[helmetImageIndex];
    setProductImage({ url, source: 'Preset library', sourceUrl: null, searchUrl: null, license: null });
    setHelmetImageIndex((helmetImageIndex + 1) % HELMET_IMAGES.length);
  };

  const handleRedoImage = (hint) => {
    if (isHelmet()) {
      cycleHelmetImage();
    } else {
      redoProductImage(hint);
    }
  };

  const startNatureQuest = () => runAction(async () => {
    const data = await requestJson('biomimicry', {
      product: productName,
      function: selectedFunction.function,
    });
    setBiomimicryOptions(data);
    setSelectedOrganism(null);
    setOrganismImage(null);
    setExplorationDone(false);
    setStep(3);
  });

  const selectOrganism = async (organism) => {
    setSelectedOrganism(organism);
    setExplorationDone(false);
    setOrganismImage(null);
    try {
      if (organism.image_url) {
        setOrganismImage({
          url: resolveImageUrl(organism.image_url),
          source: organism.source || 'AskNature',
          sourceUrl: organism.source_url,
          license: organism.license,
        });
        return;
      }
      const image = await requestJson('reference-image', {
        organism: organism.organism,
        function: selectedFunction.function,
      });
      setOrganismImage({
        url: resolveImageUrl(image.image_url),
        source: image.source,
        sourceUrl: image.source_url,
        license: image.license,
      });
    } catch (err) {
      console.error(err);
    }
  };

  const abstractPrinciples = () => runAction(async () => {
    const data = await requestJson('abstract', {
      product: productName,
      function: selectedFunction.function,
      organism: selectedOrganism.organism,
    });
    setPrinciples(data.principles || data);
    setSketchPack(data.sketch_pack || null);
    setSelectedPrinciple(null);
    setSketchDone(false);
    setStep(4);
  });

  const generateConcepts = () => runAction(async () => {
    const data = await requestJson('ideate', {
      product: productName,
      principle: selectedPrinciple.title,
    });
    setConcepts(data);
    setSelectedConcept(null);
    setConceptRefined(false);
    setStep(5);
  });

  const generatePrompt = () => runAction(async () => {
    const data = await requestJson('prompt-gen', {
      product: productName,
      concept: selectedConcept.concept_name,
    });
    setFinalPrompt(data.prompt);
    setPromptUsed(false);
    setStep(6);
  });

  const redoProductImage = async (hint) => {
    setImageRedoLoading(true);
    setError('');
    try {
      const image = await requestJson('product-image', { product: productName.trim(), hint: hint || '' });
      setProductImage({
        url: resolveImageUrl(image.image_url),
        source: image.source,
        sourceUrl: image.source_url,
        searchUrl: image.search_url,
        license: image.license,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setImageRedoLoading(false);
    }
  };

  const loadExplodedView = () => {
    if (isHelmet()) {
      setExplodedView({ image_url: '/images/helmets/helmet-exploded.svg', fallback: true });
      return;
    }
    runAction(async () => {
      const data = await requestJson('exploded-view', {
        product: productName,
        components: breakdown.map((item) => ({ component: item.component, function: item.function })),
      });
      setExplodedView(data);
    });
  };

  const beginPageTurn = () => {
    setPageTurning(true);
    setTimeout(() => {
      setShowAbout(false); // pageTurning still true → Framer exit is instant
      setTimeout(() => setPageTurning(false), 60);
    }, 720);
  };

  const reset = () => {
    skipNextTransition.current = true;
    setStep(1);
    setProductName('');
    setBreakdown([]);
    setProductImage(null);
    setSelectedFunction(null);
    setBiomimicryOptions([]);
    setSelectedOrganism(null);
    setOrganismImage(null);
    setExplorationDone(false);
    setPrinciples([]);
    setSketchPack(null);
    setSelectedPrinciple(null);
    setSketchDone(false);
    setConcepts([]);
    setSelectedConcept(null);
    setConceptRefined(false);
    setFinalPrompt('');
    setPromptUsed(false);
    setStlCreated(false);
    setEvaluation(emptyEvaluation);
    setError('');
    setExplodedView(null);
    setImageRedoHint('');
    setImageRedoLoading(false);
    setRejectedFunctions(new Set());
    setApprovedFunctions(new Set());
    setHelmetImageIndex(0);
  };

  return (
    <main className="app-shell">
      <OrganicBackground />
      <BioluminescentBackground />
      <BiomimeticDecorations />

      <AnimatePresence>
        {displayedStep === 0 && (
          <LandingPage
            key="landing"
            onEnter={() => { setShowAbout(true); setStep(1); }}
          />
        )}
      </AnimatePresence>

      {/* Subtle bioluminescent membrane transition for every step advance */}
      {isTransitioning && (
        <StepTransition
          key={`tr-${step}`}
          stepIndex={Math.min(Math.max(step - 2, 0), 6)}
          onComplete={handleStepTransitioned}
        />
      )}

      <header className="topbar">
        <div>
          <span className="brand-mark">BioMimetix AI</span>
          <p>AI compass for hands-on biomimicry exploration</p>
        </div>
        <div className="topbar-actions">
          <ApiStatus health={health} />
          <button className="ghost-button ripple-btn" onClick={reset}>New cycle</button>
        </div>
      </header>

      {displayedStep >= 1 && (
        <Timeline
          current={showAbout ? 0 : displayedStep}
          onStep1Click={showAbout ? () => setShowAbout(false) : null}
        />
      )}
      {error && <div className="error-banner">{error}</div>}
      {loading && <LoadingOverlay />}

      <ContextStrip
        productName={productName}
        productImage={productImage}
        selectedFunction={selectedFunction}
        selectedOrganism={selectedOrganism}
        organismImage={organismImage}
        selectedPrinciple={selectedPrinciple}
      />

      <AnimatePresence mode="wait">
        {displayedStep >= 1 && (
        <motion.section
          key={showAbout ? 'about' : displayedStep}
          className={`step-panel${showAbout ? ' about-panel' : ''}${pageTurning ? ' page-turning' : ''}`}
          variants={stepVariants}
          initial="initial"
          animate="animate"
          exit={pageTurning ? { opacity: 0, transition: { duration: 0 } } : 'exit'}
          transition={{ duration: 0.45, ease: 'easeOut' }}
        >
          {showAbout && (
            <AboutPage onBegin={beginPageTurn} />
          )}

          {!showAbout && displayedStep === 1 && (
            <StepIntro
              productName={productName}
              setProductName={setProductName}
              onAnalyze={analyzeProduct}
            />
          )}

          {!showAbout && displayedStep === 2 && (
            <StepFunctions
              productName={productName}
              breakdown={breakdown}
              functions={functions}
              selectedFunction={selectedFunction}
              setSelectedFunction={setSelectedFunction}
              approvedFunctions={approvedFunctions}
              setApprovedFunctions={setApprovedFunctions}
              onRejectFunction={(fn) => setRejectedFunctions((prev) => new Set([...prev, fn]))}
              rejectedFunctions={rejectedFunctions}
              productImage={productImage}
              imageRedoLoading={imageRedoLoading}
              imageRedoHint={imageRedoHint}
              setImageRedoHint={setImageRedoHint}
              onRedoImage={handleRedoImage}
              isHelmet={isHelmet()}
              explodedView={explodedView}
              onLoadExplodedView={loadExplodedView}
              onContinue={startNatureQuest}
            />
          )}

          {!showAbout && displayedStep === 3 && (
            <StepBiomimicry
              options={biomimicryOptions}
              selectedOrganism={selectedOrganism}
              onSelect={selectOrganism}
              organismImage={organismImage}
              explorationDone={explorationDone}
              setExplorationDone={setExplorationDone}
              onContinue={abstractPrinciples}
            />
          )}

          {!showAbout && displayedStep === 4 && (
            <StepPrinciples
              principles={principles}
              sketchPack={sketchPack}
              selectedPrinciple={selectedPrinciple}
              setSelectedPrinciple={setSelectedPrinciple}
              sketchDone={sketchDone}
              setSketchDone={setSketchDone}
              onContinue={generateConcepts}
            />
          )}

          {!showAbout && displayedStep === 5 && (
            <StepIdeation
              concepts={concepts}
              selectedConcept={selectedConcept}
              setSelectedConcept={setSelectedConcept}
              conceptRefined={conceptRefined}
              setConceptRefined={setConceptRefined}
              onContinue={generatePrompt}
            />
          )}

          {!showAbout && displayedStep === 6 && (
            <StepPrompt
              prompt={finalPrompt}
              promptUsed={promptUsed}
              setPromptUsed={setPromptUsed}
              onContinue={() => setStep(7)}
            />
          )}

          {!showAbout && displayedStep === 7 && (
            <StepPrintpal
              stlCreated={stlCreated}
              setStlCreated={setStlCreated}
              onContinue={() => setStep(8)}
            />
          )}

          {!showAbout && displayedStep === 8 && (
            <StepEvaluate
              evaluation={evaluation}
              setEvaluation={setEvaluation}
              onReset={reset}
            />
          )}
        </motion.section>
        )}
      </AnimatePresence>
    </main>
  );
}

function BiomimeticDecorations() {
  return (
    <div
      aria-hidden="true"
      style={{ position: 'fixed', inset: 0, zIndex: -1, pointerEvents: 'none', overflow: 'hidden' }}
    >
      {/* ── Fibonacci / Nautilus spiral — top right ── */}
      <svg
        style={{ position: 'absolute', top: '3%', right: '-5%', width: '440px', opacity: 0.17, animation: 'spiralTurn 90s linear infinite' }}
        viewBox="0 0 300 300" fill="none"
      >
        <path
          d="M150 150 A13 13 0 0 1 163 150 A26 26 0 0 1 150 176 A42 42 0 0 1 108 150 A67 67 0 0 1 150 83 A108 108 0 0 1 258 150 A175 175 0 0 1 150 325 A283 283 0 0 1 -133 150"
          stroke="rgba(63,207,196,1)" strokeWidth="1.3"
        />
        <path
          d="M150 150 A8 8 0 0 0 142 150 A16 16 0 0 0 150 134 A26 26 0 0 0 176 150 A42 42 0 0 0 150 192 A67 67 0 0 0 83 150"
          stroke="rgba(200,151,61,0.85)" strokeWidth="0.9"
        />
        <circle cx="150" cy="150" r="2.5" fill="rgba(63,207,196,0.6)" />
      </svg>

      {/* ── Leaf vein network — bottom left ── */}
      <svg
        style={{ position: 'absolute', bottom: '6%', left: '-3%', width: '360px', opacity: 0.15, animation: 'leafSway 16s ease-in-out infinite' }}
        viewBox="0 0 200 250" fill="none"
      >
        <path
          d="M100 230 C60 165 28 95 72 46 C96 18 132 16 148 56 C170 102 150 168 100 230Z"
          stroke="rgba(110,214,136,0.9)" strokeWidth="1.2"
        />
        <line x1="100" y1="230" x2="100" y2="46"  stroke="rgba(63,207,196,0.75)" strokeWidth="0.9" />
        <line x1="100" y1="76"  x2="132" y2="55"  stroke="rgba(63,207,196,0.60)" strokeWidth="0.65" />
        <line x1="100" y1="96"  x2="68"  y2="74"  stroke="rgba(63,207,196,0.55)" strokeWidth="0.60" />
        <line x1="100" y1="116" x2="138" y2="97"  stroke="rgba(63,207,196,0.50)" strokeWidth="0.55" />
        <line x1="100" y1="136" x2="66"  y2="114" stroke="rgba(63,207,196,0.45)" strokeWidth="0.50" />
        <line x1="100" y1="156" x2="132" y2="139" stroke="rgba(63,207,196,0.40)" strokeWidth="0.45" />
        <line x1="132" y1="55"  x2="148" y2="40"  stroke="rgba(63,207,196,0.35)" strokeWidth="0.40" />
        <line x1="132" y1="55"  x2="142" y2="68"  stroke="rgba(63,207,196,0.30)" strokeWidth="0.35" />
        <line x1="68"  y1="74"  x2="55"  y2="60"  stroke="rgba(63,207,196,0.30)" strokeWidth="0.35" />
      </svg>

      {/* ── Mycelium branching network — upper left ── */}
      <svg
        style={{ position: 'absolute', top: '18%', left: '-1%', width: '300px', opacity: 0.13, animation: 'myceliumDrift 22s ease-in-out infinite' }}
        viewBox="0 0 280 280" fill="none"
      >
        <line x1="80"  y1="210" x2="140" y2="145" stroke="rgba(155,123,196,1)"   strokeWidth="0.9" />
        <line x1="140" y1="145" x2="205" y2="80"  stroke="rgba(155,123,196,0.9)" strokeWidth="0.8" />
        <line x1="140" y1="145" x2="100" y2="78"  stroke="rgba(155,123,196,0.9)" strokeWidth="0.8" />
        <line x1="205" y1="80"  x2="248" y2="48"  stroke="rgba(155,123,196,0.7)" strokeWidth="0.65" />
        <line x1="205" y1="80"  x2="235" y2="112" stroke="rgba(155,123,196,0.7)" strokeWidth="0.65" />
        <line x1="100" y1="78"  x2="58"  y2="48"  stroke="rgba(155,123,196,0.7)" strokeWidth="0.65" />
        <line x1="100" y1="78"  x2="68"  y2="110" stroke="rgba(155,123,196,0.7)" strokeWidth="0.65" />
        <line x1="248" y1="48"  x2="265" y2="28"  stroke="rgba(155,123,196,0.5)" strokeWidth="0.50" />
        <line x1="248" y1="48"  x2="262" y2="62"  stroke="rgba(155,123,196,0.5)" strokeWidth="0.45" />
        <line x1="80"  y1="210" x2="48"  y2="242" stroke="rgba(155,123,196,0.6)" strokeWidth="0.60" />
        <line x1="80"  y1="210" x2="112" y2="240" stroke="rgba(155,123,196,0.5)" strokeWidth="0.50" />
        <circle cx="140" cy="145" r="2.8" fill="rgba(155,123,196,0.65)" />
        <circle cx="205" cy="80"  r="2.2" fill="rgba(155,123,196,0.55)" />
        <circle cx="100" cy="78"  r="2.2" fill="rgba(155,123,196,0.55)" />
        <circle cx="80"  cy="210" r="2.0" fill="rgba(155,123,196,0.45)" />
      </svg>

      {/* ── Small amber spiral — mid right ── */}
      <svg
        style={{ position: 'absolute', top: '48%', right: '1%', width: '190px', opacity: 0.13, animation: 'spiralTurn 130s linear infinite reverse' }}
        viewBox="0 0 160 160" fill="none"
      >
        <path
          d="M80 80 A7 7 0 0 1 87 80 A14 14 0 0 1 80 94 A23 23 0 0 1 57 80 A37 37 0 0 1 80 43 A60 60 0 0 1 140 80 A97 97 0 0 1 80 177"
          stroke="rgba(200,151,61,0.95)" strokeWidth="1.1"
        />
        <circle cx="80" cy="80" r="2" fill="rgba(200,151,61,0.7)" />
      </svg>
    </div>
  );
}

function BioluminescentBackground() {
  return (
    <div className="bio-bg" aria-hidden="true">
      <div className="glow glow-a" />
      <div className="glow glow-b" />
      <div className="glow glow-c" />
    </div>
  );
}

function Timeline({ current, onStep1Click }) {
  return (
    <nav className="timeline" aria-label="Workflow progress">
      {STEPS.map((label, index) => {
        const number = index + 1;
        const isNextUp = onStep1Click && number === 1;
        return (
          <div
            key={label}
            className={`timeline-item ${current === number ? 'active' : ''} ${current > number ? 'done' : ''} ${isNextUp ? 'next-up' : ''}`}
            onClick={isNextUp ? onStep1Click : undefined}
            role={isNextUp ? 'button' : undefined}
            tabIndex={isNextUp ? 0 : undefined}
            onKeyDown={isNextUp ? (e) => e.key === 'Enter' && onStep1Click() : undefined}
          >
            <span>{number}</span>
            <small>{label}</small>
          </div>
        );
      })}
    </nav>
  );
}

function ContextStrip({ productName, productImage, selectedFunction, selectedOrganism, organismImage, selectedPrinciple }) {
  if (!productName) return null;
  return (
    <aside className="context-strip">
      <MemoryCard
        label="Start product"
        title={productName}
        image={productImage}
        fallback="Product image"
      />
      {selectedFunction && (
        <div className="context-pill">
          <span>Locked function</span>
          <strong>{selectedFunction.function}</strong>
        </div>
      )}
      {selectedOrganism && (
        <MemoryCard
          label="Nature model"
          title={selectedOrganism.organism}
          image={organismImage}
          fallback="Organism image"
        />
      )}
      {selectedPrinciple && (
        <div className="context-pill">
          <span>Principle</span>
          <strong>{selectedPrinciple.title}</strong>
        </div>
      )}
    </aside>
  );
}

function MemoryCard({ label, title, image, fallback }) {
  return (
    <div className="memory-card">
      <div className="memory-image">
        {image?.url ? <img src={image.url} alt={title} /> : <span>{fallback}</span>}
      </div>
      <div>
        <span>{label}</span>
        <strong>{title}</strong>
        {(image?.sourceUrl || image?.searchUrl) && (
          <a href={image.sourceUrl || image.searchUrl} target="_blank" rel="noreferrer">
            {image.source || 'Source'} <ExternalLink size={13} />
          </a>
        )}
      </div>
    </div>
  );
}

function LoadingOverlay() {
  return (
    <div className="loading-overlay">
      <div className="pulse-orb" />
      <span>Guiding the next exploration...</span>
    </div>
  );
}

function ApiStatus({ health }) {
  const online = health.status === 'ok';
  const geminiReady = Boolean(health.gemini_configured);
  const claudeReady = Boolean(health.claude_configured);
  const aiReady = geminiReady || claudeReady;
  let label;
  if (!online) label = 'API offline';
  else if (geminiReady && claudeReady) label = 'Gemini + Claude ready';
  else if (geminiReady) label = 'Gemini ready';
  else if (claudeReady) label = 'Claude ready (text only)';
  else label = 'AI key missing';
  return (
    <span className={`api-status ${online && aiReady ? 'ready' : 'warn'}`}>
      {label}
    </span>
  );
}

function StepHeader({ icon, eyebrow, title, children }) {
  return (
    <div className="step-header">
      <motion.div
        className="icon-bubble"
        variants={iconBubbleVariants}
        initial="initial"
        animate="animate"
      >
        {icon}
      </motion.div>
      <span>{eyebrow}</span>
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </div>
  );
}

function StepIntro({ productName, setProductName, onAnalyze }) {
  return (
    <div className="intro-hero">
      {/* Biomimetic mandala — decorative SVG that slowly rotates */}
      <div className="intro-mandala" aria-hidden="true">
        <svg viewBox="0 0 700 600" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Outer dashed orbit */}
          <circle cx="350" cy="300" r="260" stroke="rgba(63,207,196,0.07)" strokeWidth="0.8" strokeDasharray="3 9"/>
          <circle cx="350" cy="300" r="196" stroke="rgba(155,123,196,0.09)" strokeWidth="0.7" strokeDasharray="2 7"/>
          <circle cx="350" cy="300" r="130" stroke="rgba(63,207,196,0.08)" strokeWidth="0.6" strokeDasharray="1.5 6"/>
          {/* Radial spokes — 24 lines at different lengths */}
          {Array.from({ length: 24 }, (_, i) => {
            const a = (i / 24) * Math.PI * 2;
            const r1 = 42, r2 = i % 3 === 0 ? 262 : i % 3 === 1 ? 198 : 130;
            return (
              <line key={i}
                x1={350 + Math.cos(a) * r1} y1={300 + Math.sin(a) * r1}
                x2={350 + Math.cos(a) * r2} y2={300 + Math.sin(a) * r2}
                stroke={`rgba(63,207,196,${i % 6 === 0 ? 0.18 : 0.07})`}
                strokeWidth={i % 6 === 0 ? 0.9 : 0.5}
              />
            );
          })}
          {/* Fibonacci spiral */}
          <path
            d="M350 300 A20 20 0 0 1 370 300 A40 40 0 0 1 350 340 A65 65 0 0 1 285 300 A104 104 0 0 1 350 196 A169 169 0 0 1 519 300 A274 274 0 0 1 350 574"
            stroke="rgba(200,151,61,0.22)" strokeWidth="1.4"
          />
          <path
            d="M350 300 A12 12 0 0 0 338 300 A24 24 0 0 0 350 276 A39 39 0 0 0 389 300 A62 62 0 0 0 350 362 A101 101 0 0 0 249 300"
            stroke="rgba(110,214,136,0.16)" strokeWidth="1.0"
          />
          {/* Leaf petals at 8 cardinal / intercardinal points */}
          {Array.from({ length: 8 }, (_, i) => {
            const a = (i / 8) * Math.PI * 2;
            const cx = 350 + Math.cos(a) * 198;
            const cy = 300 + Math.sin(a) * 198;
            const rot = (a * 180) / Math.PI + 90;
            return (
              <ellipse key={i} cx={cx} cy={cy} rx="10" ry="22"
                transform={`rotate(${rot},${cx},${cy})`}
                stroke="rgba(110,214,136,0.18)" strokeWidth="0.7"
              />
            );
          })}
          {/* Honeycomb cells at center cluster */}
          {[[-22,0],[22,0],[0,-20],[0,20],[-22,-20],[22,-20],[-22,20],[22,20]].map(([dx,dy],i) => (
            <polygon key={i}
              points={`${350+dx},${300+dy-10} ${350+dx+9},${300+dy-5} ${350+dx+9},${300+dy+5} ${350+dx},${300+dy+10} ${350+dx-9},${300+dy+5} ${350+dx-9},${300+dy-5}`}
              stroke="rgba(63,207,196,0.14)" strokeWidth="0.6"
            />
          ))}
          {/* Center nucleus */}
          <circle cx="350" cy="300" r="18" stroke="rgba(63,207,196,0.25)" strokeWidth="0.8"/>
          <circle cx="350" cy="300" r="6"  fill="rgba(63,207,196,0.20)"/>
          <circle cx="350" cy="300" r="2.5" fill="rgba(63,207,196,0.50)"/>
          {/* Mycelium tips at outer ring */}
          {Array.from({ length: 8 }, (_, i) => {
            const a = ((i + 0.5) / 8) * Math.PI * 2;
            const cx = 350 + Math.cos(a) * 258;
            const cy = 300 + Math.sin(a) * 258;
            return <circle key={i} cx={cx} cy={cy} r="2.2" fill="rgba(155,123,196,0.28)" key={i}/>;
          })}
        </svg>
      </div>

      <div className="intro-content">
        <StepHeader
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M12 2C6 8 4 14 12 22C20 14 18 8 12 2Z" />
              <path d="M12 2L12 22" />
              <path d="M12 8L8 12M12 8L16 12" />
              <path d="M12 13L9 16M12 13L15 16" />
            </svg>
          }
          eyebrow="Step 1 — Begin"
          title="Product Analyse"
        >
          Nature has already solved every engineering problem you face.
          Name your product — we find its biological twin.
        </StepHeader>

        <div className="input-dock">
          <input
            value={productName}
            onChange={(event) => setProductName(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && onAnalyze()}
            placeholder="Type your product name..."
            autoFocus
          />
          <button className="ripple-btn" onClick={onAnalyze} disabled={!productName.trim()}>
            Analyze product <ArrowRight size={18} />
          </button>
        </div>

        <div className="quick-examples">
          <button onClick={() => setProductName('Cycling Helmet')}>Cycling Helmet</button>
        </div>
      </div>
    </div>
  );
}

function StepFunctions({
  productName, breakdown, functions, selectedFunction, setSelectedFunction,
  approvedFunctions, setApprovedFunctions, onRejectFunction, rejectedFunctions,
  productImage, imageRedoLoading, imageRedoHint, setImageRedoHint, onRedoImage, isHelmet,
  explodedView, onLoadExplodedView, onContinue,
}) {
  return (
    <>
      <StepHeader icon={<Box />} eyebrow="Step 2" title={`${productName} — Functions`}>
        Approve the functions you want to explore, or reject ones that don't fit.
        Select one function to continue to the Nature Quest.
      </StepHeader>

      <div className="product-functions-layout">
        {/* ── Left: product image hero ── */}
        <div className="product-image-panel">
          <div className="product-image-hero">
            {imageRedoLoading && (
              <div className="image-loading-overlay">
                <div className="pulse-orb" />
              </div>
            )}
            {productImage?.url
              ? <img src={productImage.url} alt={productName} />
              : <div className="image-empty-hero"><Box size={40} /><span>{productName}</span></div>
            }
            {(productImage?.sourceUrl || productImage?.searchUrl) && (
              <a
                href={productImage.sourceUrl || productImage.searchUrl}
                target="_blank"
                rel="noreferrer"
                className="image-source-badge"
              >
                {productImage.source || 'Source'} <ExternalLink size={11} />
              </a>
            )}
          </div>

          <div className="image-redo-panel">
            <span className="image-redo-label">Not the right image?</span>
            {!isHelmet && (
              <input
                className="image-redo-input"
                value={imageRedoHint}
                onChange={(e) => setImageRedoHint(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && onRedoImage(imageRedoHint)}
                placeholder={`e.g. "sport ${productName.toLowerCase()}", "modern design"`}
              />
            )}
            <button
              className="image-redo-btn"
              onClick={() => onRedoImage(imageRedoHint)}
              disabled={imageRedoLoading}
            >
              <RefreshCw size={13} /> {isHelmet ? 'Next helmet image' : 'Try different image'}
            </button>
          </div>
        </div>

        {/* ── Right: function suggestion cards ── */}
        <div className="product-functions-cards">
          <p className="functions-hint">
            <Sparkles size={13} /> AI-suggested functions — approve or reject each one
          </p>
          <motion.div className="card-grid" variants={containerVariants} initial="initial" animate="animate">
            {functions.map((item) => {
              const key = `${item.component}-${item.function}`;
              const rejected = rejectedFunctions.has(item.function);
              return (
                <FunctionCard
                  key={key}
                  item={item}
                  active={!rejected && selectedFunction?.function === item.function}
                  approved={approvedFunctions.has(item.function)}
                  rejected={rejected}
                  onClick={() => setSelectedFunction(item)}
                  onApprove={() => {
                    setSelectedFunction(item);
                    setApprovedFunctions((prev) => new Set([...prev, item.function]));
                  }}
                  onReject={() => {
                    if (selectedFunction?.function === item.function) setSelectedFunction(null);
                    onRejectFunction(item.function);
                  }}
                />
              );
            })}
          </motion.div>
        </div>
      </div>

      {/* ── Exploded view ── */}
      <div className="exploded-section">
        {!explodedView ? (
          <button className="ghost-button exploded-trigger" onClick={onLoadExplodedView}>
            <Eye size={15} /> {isHelmet ? 'Show exploded view' : 'Generate exploded view'}
          </button>
        ) : (
          <div className="exploded-view-card">
            <span>Exploded view — {productName}</span>
            <img src={resolveImageUrl(explodedView.image_url)} alt={`${productName} exploded view`} />
          </div>
        )}
      </div>

      <BreakdownList items={breakdown} />

      <GateAction
        ready={Boolean(selectedFunction)}
        label="Start Nature Quest"
        disabledLabel="Select a function first"
        onClick={onContinue}
      />
    </>
  );
}

function BreakdownList({ items }) {
  return (
    <div className="compact-list">
      <span>Full AI breakdown</span>
      {items.map((item, index) => (
        <p key={`${item.component}-${index}`}>
          <strong>{item.component}</strong> {item.function}
        </p>
      ))}
    </div>
  );
}

function StepBiomimicry({ options, selectedOrganism, onSelect, organismImage, explorationDone, setExplorationDone, onContinue }) {
  const pack = selectedOrganism?.exploration_pack;
  return (
    <>
      <StepHeader
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M12 12C12 9 14 7 16 8C18 9 19 12 17 15C15 18 11 19 8 17C5 15 4 10 7 7C10 4 16 4 19 8" />
            <circle cx="12" cy="12" r="1.5" fill="currentColor" />
          </svg>
        }
        eyebrow="Step 3"
        title="Biomimicry: Nature Quest"
      >
        Choose one organism, then complete an exploration pack before abstraction unlocks.
      </StepHeader>
      <motion.div className="card-grid" variants={containerVariants} initial="initial" animate="animate">
        {options.map((option) => (
          <ChoiceCard
            key={option.organism}
            active={selectedOrganism?.organism === option.organism}
            onClick={() => onSelect(option)}
            title={option.organism}
            text={option.rationale}
            action="Open exploration pack"
          />
        ))}
      </motion.div>
      {selectedOrganism && (
        <ExplorationPack
          organism={selectedOrganism}
          image={organismImage}
          pack={pack}
          checked={explorationDone}
          setChecked={setExplorationDone}
          onContinue={onContinue}
        />
      )}
    </>
  );
}

function ExplorationPack({ organism, image, pack, checked, setChecked, onContinue }) {
  const watch = pack?.watch || [];
  const read = pack?.read || [];
  const act = pack?.act;
  return (
    <div className="exploration-pack">
      <div className="exploration-media">
        {image?.url ? <img src={image.url} alt={organism.organism} /> : <div className="image-empty">Loading organism image</div>}
        {image?.sourceUrl && (
          <a href={image.sourceUrl} target="_blank" rel="noreferrer">
            {image.source || 'Image source'} <ExternalLink size={13} />
          </a>
        )}
      </div>
      <div className="pack-content">
        <span>Exploration Pack</span>
        <h2>{organism.organism}</h2>
        <p>{organism.rationale}</p>
        <ResourceSection icon={<Video />} title="Watch" items={watch} />
        <ResourceSection icon={<FileText />} title="Read" items={read} />
        {act && (
          <div className="quest-card">
            <div><Eye size={20} /><strong>{act.title}</strong></div>
            <p>{act.description}</p>
            <ul>
              {(act.checklist || []).map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        )}
        <label className="gate-check">
          <input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />
          I have explored these resources and made my own observations.
        </label>
        <GateAction ready={checked} label="Abstract the principle" disabledLabel="Complete the Nature Quest gate" onClick={onContinue} />
      </div>
    </div>
  );
}

function ResourceSection({ icon, title, items }) {
  return (
    <div className="resource-section">
      <h3>{icon}{title}</h3>
      {items.map((item) => (
        <a key={`${title}-${item.title}`} href={item.url} target="_blank" rel="noreferrer">
          <div>
            <strong>{item.title}</strong>
            <small>{item.description}</small>
          </div>
          <ExternalLink size={15} />
        </a>
      ))}
    </div>
  );
}

function StepPrinciples({ principles, sketchPack, selectedPrinciple, setSelectedPrinciple, sketchDone, setSketchDone, onContinue }) {
  return (
    <>
      <StepHeader
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <polygon points="12,3 19,7 19,15 12,19 5,15 5,7" />
            <polygon points="12,7 16,9 16,14 12,16 8,14 8,9" />
            <circle cx="12" cy="12" r="1.2" fill="currentColor" />
          </svg>
        }
        eyebrow="Step 4"
        title="Principle Abstraction"
      >
        Select one abstract principle, then sketch it before ideation becomes available.
      </StepHeader>
      <motion.div className="card-grid" variants={containerVariants} initial="initial" animate="animate">
        {principles.map((principle) => (
          <ChoiceCard
            key={principle.title}
            active={selectedPrinciple?.title === principle.title}
            onClick={() => setSelectedPrinciple(principle)}
            title={principle.title}
            text={principle.principle}
          />
        ))}
      </motion.div>
      <SketchGate sketchPack={sketchPack} checked={sketchDone} setChecked={setSketchDone} />
      <GateAction
        ready={Boolean(selectedPrinciple && sketchDone)}
        label="Move to ideation"
        disabledLabel="Select a principle and complete the sketch gate"
        onClick={onContinue}
      />
    </>
  );
}

function SketchGate({ sketchPack, checked, setChecked }) {
  return (
    <div className="sketch-gate">
      <div className="icon-bubble"><Pencil /></div>
      <div>
        <span>{sketchPack?.title || 'Sketching Assignment'}</span>
        <h2>Grab pen and paper</h2>
        <p>{sketchPack?.prompt || 'Sketch the mechanism as forces, surfaces, material gradients, and failure modes.'}</p>
        <ul>
          {(sketchPack?.checks || []).map((item) => <li key={item}>{item}</li>)}
        </ul>
        <label className="gate-check">
          <input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />
          Sketch completed.
        </label>
      </div>
    </div>
  );
}

function StepIdeation({ concepts, selectedConcept, setSelectedConcept, conceptRefined, setConceptRefined, onContinue }) {
  return (
    <>
      <StepHeader icon={<Sparkles />} eyebrow="Step 5" title="Ideation and Creation">
        Select one concept. Before visualization, pause and refine what must remain physically testable.
      </StepHeader>
      <motion.div className="card-grid two" variants={containerVariants} initial="initial" animate="animate">
        {concepts.map((concept) => (
          <ChoiceCard
            key={concept.concept_name}
            active={selectedConcept?.concept_name === concept.concept_name}
            onClick={() => setSelectedConcept(concept)}
            title={concept.concept_name}
            text={concept.description}
          />
        ))}
      </motion.div>
      <label className="gate-check standalone">
        <input type="checkbox" checked={conceptRefined} onChange={(event) => setConceptRefined(event.target.checked)} />
        I have mentally refined this concept and identified what should be tested physically.
      </label>
      <GateAction
        ready={Boolean(selectedConcept && conceptRefined)}
        label="Generate strict 2D prompt"
        disabledLabel="Select and refine a concept"
        onClick={onContinue}
      />
    </>
  );
}

function StepPrompt({ prompt, promptUsed, setPromptUsed, onContinue }) {
  return (
    <>
      <StepHeader icon={<Clipboard />} eyebrow="Step 6" title="2D Image Prompt">
        Copy this strict prompt into your external image generator. Keep the output clean for 3D conversion.
      </StepHeader>
      <div className="prompt-box">{prompt}</div>
      <button className="secondary-button" onClick={() => navigator.clipboard.writeText(prompt)}>
        Copy prompt
      </button>
      <label className="gate-check standalone">
        <input type="checkbox" checked={promptUsed} onChange={(event) => setPromptUsed(event.target.checked)} />
        I have copied or used the prompt externally.
      </label>
      <GateAction ready={promptUsed} label="Continue to 3D pathway" disabledLabel="Use the 2D prompt first" onClick={onContinue} />
    </>
  );
}

function StepPrintpal({ stlCreated, setStlCreated, onContinue }) {
  return (
    <>
      <StepHeader icon={<Printer />} eyebrow="Step 7" title="3D Model: Printpal Pathway">
        Convert the clean 2D image into a printable model. The AI stops here; your hands take over.
      </StepHeader>
      <div className="instruction-grid">
        {[
          ['Upload', 'Take the single-object 2D image and upload it into Printpal or another image-to-3D tool.'],
          ['Inspect', 'Rotate the mesh. Look for broken surfaces, impossible overhangs, and lost biological features.'],
          ['Export', 'Export an STL. Keep a screenshot of the mesh before slicing.'],
          ['Print', '3D print a small prototype, even if the model is imperfect.'],
        ].map(([title, text]) => (
          <div key={title} className="instruction-card">
            <strong>{title}</strong>
            <p>{text}</p>
          </div>
        ))}
      </div>
      <label className="gate-check standalone">
        <input type="checkbox" checked={stlCreated} onChange={(event) => setStlCreated(event.target.checked)} />
        I have created or inspected an STL pathway.
      </label>
      <GateAction ready={stlCreated} label="Evaluate physical result" disabledLabel="Create or inspect the STL first" onClick={onContinue} />
    </>
  );
}

function StepEvaluate({ evaluation, setEvaluation, onReset }) {
  const complete = Object.values(evaluation).every((value) => value.trim().length > 8);
  const update = (key, value) => setEvaluation((current) => ({ ...current, [key]: value }));
  return (
    <>
      <StepHeader icon={<Check />} eyebrow="Step 8" title="Evaluate">
        Log what failed. Biomimicry improves when the physical prototype argues back.
      </StepHeader>
      <div className="evaluation-form">
        <Question
          label="How did the translation from nature to AI to physical object fail?"
          value={evaluation.failure}
          onChange={(value) => update('failure', value)}
        />
        <Question
          label="What nuances of the biological organism were lost?"
          value={evaluation.lostNuance}
          onChange={(value) => update('lostNuance', value)}
        />
        <Question
          label="Did the 3D print function as expected?"
          value={evaluation.printFunction}
          onChange={(value) => update('printFunction', value)}
        />
        <Question
          label="What should change in the next iteration?"
          value={evaluation.nextIteration}
          onChange={(value) => update('nextIteration', value)}
        />
      </div>
      <GateAction ready={complete} label="Finish and start new cycle" disabledLabel="Complete every evaluation field" onClick={onReset} />
    </>
  );
}

function Question({ label, value, onChange }) {
  return (
    <label className="question-field">
      <span>{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={4} />
    </label>
  );
}

function FunctionCard({ item, active, approved, rejected, onClick, onApprove, onReject }) {
  return (
    <motion.div
      className={`choice-card function-card ${active ? 'active' : ''} ${approved ? 'approved' : ''} ${rejected ? 'rejected' : ''}`}
      variants={cardVariants}
    >
      <button
        className="function-card-body ripple-btn"
        disabled={rejected}
        onClick={(e) => { createRipple(e); onClick?.(); }}
      >
        <strong>{item.component}</strong>
        <p>{item.function}</p>
      </button>
      <div className="function-card-actions">
        <button
          className={`fn-action fn-approve ${approved ? 'fn-active' : ''}`}
          onClick={(e) => { e.stopPropagation(); onApprove?.(); }}
          title="Approve this function"
          disabled={rejected}
        >
          <ThumbsUp size={13} />
        </button>
        <button
          className="fn-action fn-reject"
          onClick={(e) => { e.stopPropagation(); onReject?.(); }}
          title="Disable this function"
        >
          <ThumbsDown size={13} />
        </button>
      </div>
    </motion.div>
  );
}

function ChoiceCard({ active, onClick, title, text, action }) {
  return (
    <motion.button
      className={`choice-card ${active ? 'active' : ''}`}
      onClick={(e) => { createRipple(e); onClick?.(); }}
      variants={cardVariants}
      whileHover={{ scale: 1.015, transition: { duration: 0.30, ease: 'easeOut' } }}
      whileTap={{ scale: 0.96, transition: { duration: 0.12 } }}
    >
      <strong>{title}</strong>
      <p>{text}</p>
      {action && <span>{action}</span>}
    </motion.button>
  );
}

function GateAction({ ready, label, disabledLabel, onClick }) {
  return (
    <div className="gate-action">
      <button
        className="ripple-btn"
        disabled={!ready}
        onClick={(e) => { createRipple(e); onClick?.(); }}
      >
        {ready ? label : disabledLabel} <ArrowRight size={18} />
      </button>
    </div>
  );
}

const METHOD_STEPS = [
  { n: 1, title: 'Product Analyse', text: 'Define the problem context and physical constraints to set strict boundaries for the AI.' },
  { n: 2, title: 'Product Functions', text: 'Break the design into fundamental mechanical functions and select the specific parameters you want to explore.' },
  { n: 3, title: 'Biomimicry', text: 'Retrieve biological organisms that match your selected functions and complete visual Nature Quests, such as studying woodpecker skull anatomy.' },
  { n: 4, title: 'Principle Abstraction', text: 'Translate biological behaviours into technical engineering rules and perform mandatory offline observation tasks.' },
  { n: 5, title: 'Ideation', text: 'Generate conceptual solutions from the abstracted rules. Force prompt re-runs, reject unfeasible ideas, and explicitly select which features to merge.' },
  { n: 6, title: '2D Image', text: 'Create a clean 2D visual by refining generative prompts. Ensure the base geometry has no background noise and a clear orientation.' },
  { n: 7, title: '3D Model', text: 'Convert the 2D image into a digital 3D model and manually review the resulting mesh for structural integrity.' },
  { n: 8, title: 'Evaluate', text: 'Assess real-world feasibility by slicing and 3D-printing a physical prototype.' },
];

function AboutPage({ onBegin }) {
  return (
    <div className="about-page">
      <motion.div
        className="about-header"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } }}
      >
        <span className="about-eyebrow">Deep-dive Biomimicry</span>
        <h1>Welcome to BioMimetix AI</h1>
        <p className="about-intro">
          A structured 8-step workflow that bridges digital AI inspiration with hands-on physical biomimetic design.
          Use it during the ideation and early concept generation phases, after defining your product's core functions
          and right before physical prototyping begins.
        </p>
      </motion.div>

      <motion.div
        className="about-meta-row"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0, transition: { delay: 0.18, duration: 0.55 } }}
      >
        <div className="about-meta-card">
          <span>WHEN</span>
          <p>Ideation and early concept generation. Apply it after defining the core functions of your product, right before physical prototyping begins.</p>
        </div>
        <div className="about-meta-card">
          <span>MINDSET</span>
          <p>AI serves as inspiration, not a final answer. Critically evaluate every output against physical feasibility.</p>
        </div>
        <div className="about-meta-card">
          <span>OUTCOME</span>
          <p>A physically validated 3D-printed prototype, a list of abstracted biological principles, and hand-drawn observational sketches.</p>
        </div>
      </motion.div>

      <motion.div
        className="about-steps-grid"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, transition: { delay: 0.32, duration: 0.6 } }}
      >
        {METHOD_STEPS.map((s, i) => (
          <motion.div
            key={s.n}
            className="about-step-card"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0, transition: { delay: 0.36 + i * 0.055, duration: 0.42 } }}
          >
            <div className="about-step-num">{s.n}</div>
            <div>
              <strong>{s.title}</strong>
              <p>{s.text}</p>
            </div>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        className="about-cta"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0, transition: { delay: 0.9, duration: 0.5 } }}
      >
        <p className="about-cta-hint">Click <strong>Step 1</strong> in the timeline above, or use the button below to begin.</p>
        <button className="ripple-btn about-begin-btn" onClick={(e) => { createRipple(e); onBegin(); }}>
          Begin: Product Analyse <ArrowRight size={18} />
        </button>
      </motion.div>
    </div>
  );
}

export default App;
