import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowRight,
  Box,
  Check,
  Clipboard,
  Compass,
  ExternalLink,
  Eye,
  FileText,
  Leaf,
  Pencil,
  Printer,
  Sparkles,
  Video,
} from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';
const configuredApiBase = import.meta.env.VITE_API_BASE || API_BASE;
const normalizedApiBase = configuredApiBase.replace(/\/$/, '');
const BACKEND_BASE = normalizedApiBase.replace('/api', '');
const transition = { duration: 0.45, ease: 'easeOut' };

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
  return url.startsWith('http') ? url : `${BACKEND_BASE}${url}`;
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
  const [step, setStep] = useState(1);
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

  const functions = useMemo(() => uniqueFunctions(breakdown), [breakdown]);

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
        if (!res.ok) throw new Error('Backend unavailable');
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
    setStep(2);
  });

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

  const reset = () => {
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
  };

  return (
    <main className="app-shell">
      <BioluminescentBackground />
      <header className="topbar">
        <div>
          <span className="brand-mark">BioMimetix AI</span>
          <p>AI compass for hands-on biomimicry exploration</p>
        </div>
        <div className="topbar-actions">
          <ApiStatus health={health} />
          <button className="ghost-button" onClick={reset}>New cycle</button>
        </div>
      </header>

      <Timeline current={step} />
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
        <motion.section
          key={step}
          className="step-panel"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -18 }}
          transition={transition}
        >
          {step === 1 && (
            <StepIntro
              productName={productName}
              setProductName={setProductName}
              onAnalyze={analyzeProduct}
            />
          )}

          {step === 2 && (
            <StepFunctions
              productName={productName}
              breakdown={breakdown}
              functions={functions}
              selectedFunction={selectedFunction}
              setSelectedFunction={setSelectedFunction}
              onContinue={startNatureQuest}
            />
          )}

          {step === 3 && (
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

          {step === 4 && (
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

          {step === 5 && (
            <StepIdeation
              concepts={concepts}
              selectedConcept={selectedConcept}
              setSelectedConcept={setSelectedConcept}
              conceptRefined={conceptRefined}
              setConceptRefined={setConceptRefined}
              onContinue={generatePrompt}
            />
          )}

          {step === 6 && (
            <StepPrompt
              prompt={finalPrompt}
              promptUsed={promptUsed}
              setPromptUsed={setPromptUsed}
              onContinue={() => setStep(7)}
            />
          )}

          {step === 7 && (
            <StepPrintpal
              stlCreated={stlCreated}
              setStlCreated={setStlCreated}
              onContinue={() => setStep(8)}
            />
          )}

          {step === 8 && (
            <StepEvaluate
              evaluation={evaluation}
              setEvaluation={setEvaluation}
              onReset={reset}
            />
          )}
        </motion.section>
      </AnimatePresence>
    </main>
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

function Timeline({ current }) {
  return (
    <nav className="timeline" aria-label="Workflow progress">
      {STEPS.map((label, index) => {
        const number = index + 1;
        return (
          <div key={label} className={`timeline-item ${current === number ? 'active' : ''} ${current > number ? 'done' : ''}`}>
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
  const label = online ? (geminiReady ? 'Gemini ready' : 'Gemini key missing') : 'Backend offline';
  return (
    <span className={`api-status ${online && geminiReady ? 'ready' : 'warn'}`}>
      {label}
    </span>
  );
}

function StepHeader({ icon, eyebrow, title, children }) {
  return (
    <div className="step-header">
      <div className="icon-bubble">{icon}</div>
      <span>{eyebrow}</span>
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </div>
  );
}

function StepIntro({ productName, setProductName, onAnalyze }) {
  return (
    <div className="intro-layout">
      <div>
        <StepHeader icon={<Compass />} eyebrow="Step 1" title="Product Analyse">
          Define the product. The AI may break it down, but you choose the redesign path.
        </StepHeader>
        <div className="input-dock">
          <input
            value={productName}
            onChange={(event) => setProductName(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && onAnalyze()}
            placeholder="Helmet, running shoe, drone blade..."
          />
          <button onClick={onAnalyze} disabled={!productName.trim()}>
            Analyze product <ArrowRight size={18} />
          </button>
        </div>
        <div className="quick-examples">
          {['Helmet', 'Running shoe', 'Drone blade'].map((item) => (
            <button key={item} onClick={() => setProductName(item)}>{item}</button>
          ))}
        </div>
      </div>
      <div className="intro-visual" aria-hidden="true">
        <img src="/images/biomimicry-bg-1.png" alt="" />
        <img src="/images/biomimicry-bg-2.png" alt="" />
      </div>
    </div>
  );
}

function StepFunctions({ productName, breakdown, functions, selectedFunction, setSelectedFunction, onContinue }) {
  return (
    <>
      <StepHeader icon={<Box />} eyebrow="Step 2" title={`Product Functions: ${productName}`}>
        Review the AI breakdown. Manually lock the single function you want to redesign.
      </StepHeader>
      <div className="card-grid">
        {functions.map((item) => (
          <ChoiceCard
            key={`${item.component}-${item.function}`}
            active={selectedFunction?.function === item.function}
            onClick={() => setSelectedFunction(item)}
            title={item.component}
            text={item.function}
          />
        ))}
      </div>
      <BreakdownList items={breakdown} />
      <GateAction
        ready={Boolean(selectedFunction)}
        label="Start Nature Quest"
        disabledLabel="Lock a primary function first"
        onClick={onContinue}
      />
    </>
  );
}

function BreakdownList({ items }) {
  return (
    <div className="compact-list">
      <span>Structured product breakdown</span>
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
      <StepHeader icon={<Leaf />} eyebrow="Step 3" title="Biomimicry: Nature Quest">
        Choose one organism, then complete an exploration pack before abstraction unlocks.
      </StepHeader>
      <div className="card-grid">
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
      </div>
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
      <StepHeader icon={<Pencil />} eyebrow="Step 4" title="Principle Abstraction">
        Select one abstract principle, then sketch it before ideation becomes available.
      </StepHeader>
      <div className="card-grid">
        {principles.map((principle) => (
          <ChoiceCard
            key={principle.title}
            active={selectedPrinciple?.title === principle.title}
            onClick={() => setSelectedPrinciple(principle)}
            title={principle.title}
            text={principle.principle}
          />
        ))}
      </div>
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
      <div className="card-grid two">
        {concepts.map((concept) => (
          <ChoiceCard
            key={concept.concept_name}
            active={selectedConcept?.concept_name === concept.concept_name}
            onClick={() => setSelectedConcept(concept)}
            title={concept.concept_name}
            text={concept.description}
          />
        ))}
      </div>
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

function ChoiceCard({ active, onClick, title, text, action }) {
  return (
    <button className={`choice-card ${active ? 'active' : ''}`} onClick={onClick}>
      <strong>{title}</strong>
      <p>{text}</p>
      {action && <span>{action}</span>}
    </button>
  );
}

function GateAction({ ready, label, disabledLabel, onClick }) {
  return (
    <div className="gate-action">
      <button disabled={!ready} onClick={onClick}>
        {ready ? label : disabledLabel} <ArrowRight size={18} />
      </button>
    </div>
  );
}

export default App;
