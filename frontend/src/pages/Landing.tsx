import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { SceneStage, type SceneContent } from '../landing/engine/SceneStage';
import { PaperDefs } from '../landing/engine/PaperDefs';
import { TearEdge } from '../landing/engine/TearEdge';
import { useStaticMode } from '../landing/engine/useStatic';
import { NavbarLanding } from '../landing/chrome/NavbarLanding';
import { DotNav } from '../landing/chrome/DotNav';
import { CoverScene, CoverTeaser } from '../landing/scenes/CoverScene';
import { ProblemScene, ProblemTeaser } from '../landing/scenes/ProblemScene';
import { FieldNotesScene, FieldNotesTeaser } from '../landing/scenes/FieldNotesScene';
import { RolesScene, RolesTeaser } from '../landing/scenes/RolesScene';
import { TrustScene, TrustTeaser } from '../landing/scenes/TrustScene';
import { DemoScene, DemoTeaser } from '../landing/scenes/DemoScene';
import { FinaleScene } from '../landing/scenes/FinaleScene';

import { SCENES } from '../landing/engine/config';
import { sceneStore } from '../landing/engine/store';
import { toggleStaticMode } from '../landing/engine/useStatic';

export const Landing: React.FC = () => {
  const isStatic = useStaticMode();
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  const toggleFaq = (idx: number) => {
    setActiveFaq(activeFaq === idx ? null : idx);
  };

  // Sync navbar theme during static reading mode. The sticky stage drives the
  // store itself; in static mode nothing does, so the sections are measured here.
  React.useEffect(() => {
    if (!isStatic) return;
    const handleScroll = () => {
      let cur = 0;
      SCENES.forEach((s, idx) => {
        const el = document.getElementById(s.id);
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= 100 && rect.bottom >= 100) {
            cur = idx;
          }
        }
      });
      sceneStore.set({ scene: cur, theme: SCENES[cur].theme });
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [isStatic]);

  const faqs = [
    {
      q: 'Why does this need an agent, not a simple script?',
      a: 'Scientific repositories break in heterogeneous, unscriptable ways: undeclared C-dependencies, subtle syntax depreciations, or silent parameter discrepancies. An agent diagnoses unstructured logs, formulates hypotheses, generates minimal diffs, and audits configs against paper text.',
    },
    {
      q: 'Why not just use a standard coding assistant chatbot?',
      a: 'Chatbots hallucinate fixes, lack runtime sandboxes, cannot run or measure code, and often cheat by editing evaluation scripts to fabricate high metrics. Rerun combines an independent Critic, deterministic policy checks, and sandboxed execution.',
    },
    {
      q: 'Is it safe to run untrusted research code from the web?',
      a: 'Yes. Code runs inside hardened Docker containers with root privileges dropped, network interfaces locked down, strict CPU/memory quotas, and zero host filesystem access.',
    },
    {
      q: 'What if the research paper itself contains flawed results?',
      a: 'Rerun never accuses the paper. If code fails to reproduce, the report neutrally documents that this code, in this environment, did not reach the reported metric.',
    },
    {
      q: 'Does Rerun tune parameters until the number matches?',
      a: 'Strictly forbidden. Rule P7 and Critic Check #5 block metric-chasing. Hyperparameters may only be altered if justified by explicit quotes in the paper text or traceback provenances.',
    },
    {
      q: 'Can I upload an arbitrary repository right now?',
      a: 'Rerun operates on an allow-list of curated benchmark cases to ensure verifiable, deterministic evaluation.',
    },
  ];

  const scenes: SceneContent[] = [
    {
      id: 'cover',
      body: <CoverScene />,
      teaser: <CoverTeaser />,
    },
    {
      id: 'problem',
      body: <ProblemScene />,
      teaser: <ProblemTeaser />,
    },
    {
      id: 'how-it-works',
      body: <FieldNotesScene />,
      teaser: <FieldNotesTeaser />,
    },
    {
      id: 'roles',
      body: <RolesScene />,
      teaser: <RolesTeaser />,
    },
    {
      id: 'trust',
      body: <TrustScene />,
      teaser: <TrustTeaser />,
    },
    {
      id: 'demo',
      body: <DemoScene />,
      teaser: <DemoTeaser />,
    },
    {
      id: 'finale',
      body: <FinaleScene />,
    },
  ];

  return (
    <div className="relative w-full bg-night-deep text-cream overflow-visible">
      {/* Skip to Content link for accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[999] focus:px-4 focus:py-2 focus:bg-cream focus:text-ink focus:font-mono focus:text-xs focus:ring-2 focus:ring-rust shadow-xl"
      >
        Skip to main content
      </a>

      {/* Static SVG Filters mounted once near root */}
      <PaperDefs />

      {/* Fixed Chrome */}
      <NavbarLanding />
      {!isStatic && <DotNav />}

      <main id="main-content" className="relative w-full overflow-visible">
        {/* Dynamic Sticky Stage vs Static Fallback */}
        {isStatic ? (
          <div className="w-full flex flex-col">
            {scenes.map((s, i) => {
              const last = i === scenes.length - 1;
              return (
                <section
                  key={s.id}
                  id={s.id}
                  aria-label={`Scene ${i + 1}: ${s.id}`}
                  className="relative w-full min-h-[100svh] flex flex-col"
                >
                  <div className="w-full flex-1 relative">{s.body}</div>
                  {!last && (
                    <div className="relative w-full h-[80px] -mt-[40px] z-20 pointer-events-none">
                      <TearEdge seed={1000 + i * 7} edge="bottom" />
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        ) : (
          <SceneStage scenes={scenes} />
        )}

        {/* ============================================================ */}
        {/* FINALE REST OF CONTENT (In normal flow with seamless --night-deep) */}
        {/* ============================================================ */}
        <div className="relative z-10 bg-night-deep text-cream px-6 py-20 border-t border-cream/10">
          <div className="max-w-4xl mx-auto space-y-24">
            {/* Limits Panel: What Rerun Deliberately Does Not Do */}
            <section
              aria-labelledby="limits-heading"
              className="p-8 bg-night-bot border border-cream/20 shadow-2xl relative"
              style={{
                clipPath:
                  'polygon(0% 4px, 4px 0%, calc(100% - 4px) 0%, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0% calc(100% - 4px))',
              }}
            >
              <div className="flex items-center gap-2 text-rust font-mono text-xs font-bold uppercase tracking-widest mb-4">
                <span>⚠</span>
                <h3 id="limits-heading">Limits First: What Rerun Deliberately Does Not Do</h3>
              </div>
              <ul className="space-y-3 font-mono text-xs text-cream/80 leading-relaxed">
                <li className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">•</span>
                  <span>
                    <strong>Computational reproduction only:</strong> Verifies whether this code
                    produces these numbers, not whether the author's broader scientific theories are
                    true.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">•</span>
                  <span>
                    <strong>Curated benchmark cases:</strong> Runs operate on the 5 allow-listed
                    benchmark cases to ensure verifiable, deterministic evaluation.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">•</span>
                  <span>
                    <strong>Synthetic benchmark papers:</strong> Papers used for evaluation are
                    synthetic papers labelled as such.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">•</span>
                  <span>
                    <strong>No secret telemetry:</strong> All containers execute strictly on your
                    local machine with isolated networks and offline verification.
                  </span>
                </li>
              </ul>
            </section>

            {/* FAQ Accordion */}
            <section id="faq" aria-labelledby="faq-heading" className="space-y-8">
              <div className="text-center">
                <div className="text-[11px] font-mono uppercase tracking-[0.28em] text-cream/70 mb-1">
                  Field Handbook
                </div>
                <h2
                  id="faq-heading"
                  className="font-serif text-3xl md:text-4xl uppercase tracking-[0.02em] text-cream"
                >
                  Frequently Asked Questions
                </h2>
              </div>

              <div className="space-y-3">
                {faqs.map((f, i) => (
                  <div
                    key={i}
                    className="bg-paper text-ink rounded-sm border border-kraft overflow-hidden shadow-sm"
                  >
                    <button
                      type="button"
                      onClick={() => toggleFaq(i)}
                      className="w-full px-6 py-4 flex items-center justify-between text-left font-serif text-base md:text-lg font-medium text-ink hover:text-rust transition-colors focus:outline-none focus:ring-1 focus:ring-rust"
                    >
                      <span>{f.q}</span>
                      <span className="font-mono text-sm font-bold text-rust ml-4">
                        {activeFaq === i ? '−' : '+'}
                      </span>
                    </button>
                    {activeFaq === i && (
                      <div className="px-6 pb-5 font-mono text-xs text-ink-soft leading-relaxed border-t border-kraft/50 pt-3">
                        {f.a}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>

            {/* Final Call to Action */}
            <section className="text-center py-12 border-t border-cream/15 space-y-6">
              <h2 className="font-serif text-4xl md:text-5xl uppercase tracking-[0.02em] text-cream">
                See the whole loop in one run.
              </h2>
              <p className="font-mono text-xs md:text-sm text-cream/75 max-w-xl mx-auto leading-relaxed">
                Experience the complete B4 combined reproduction flow with live container streaming,
                Critic review, and human sign-off.
              </p>
              <div className="pt-2">
                <Link
                  to="/new?case=b4"
                  className="inline-block px-8 py-4 font-mono text-xs uppercase tracking-[0.22em] font-bold text-ink bg-cream hover:bg-paper active:scale-95 transition-all shadow-xl"
                  style={{
                    clipPath:
                      'polygon(0% 4px, 4px 0%, calc(100% - 4px) 0%, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0% calc(100% - 4px))',
                  }}
                >
                  Launch Demo Case (B4) →
                </Link>
              </div>
            </section>

            {/* Editorial Footer */}
            <footer className="pt-12 border-t border-cream/10 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-cream/60">
              <div className="flex items-center gap-3">
                <span className="font-bold tracking-widest uppercase text-cream">RERUN</span>
                <span>·</span>
                <span>Reproduce a paper's result. Prove every step.</span>
              </div>
              <div className="flex items-center gap-4">
                <button
                  onClick={toggleStaticMode}
                  className="underline hover:text-cream transition-colors text-[11px]"
                >
                  {isStatic ? 'Enable Scroll Animations' : 'Skip Scroll Animations'}
                </button>
                <span>·</span>
                <span>Rerun Lab · 2026</span>
              </div>
            </footer>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Landing;
