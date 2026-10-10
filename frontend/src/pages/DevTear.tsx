import React, { useEffect, useState } from 'react';
import { SceneStage, computeLayout, type SceneContent } from '../landing/engine/SceneStage';
import { PaperDefs } from '../landing/engine/PaperDefs';
import { useScene } from '../landing/engine/store';
import { SCENES } from '../landing/engine/config';

export const DevTear: React.FC = () => {
  const { scene, theme } = useScene();
  const [scrollY, setScrollY] = useState(0);
  const isDebug =
    typeof window !== 'undefined' && window.location.search.includes('debug=tear');

  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const layout = typeof window !== 'undefined' ? computeLayout(window.innerHeight) : [];

  const scenes: SceneContent[] = [
    {
      id: 'cover',
      body: (
        <div
          className="w-full h-full flex flex-col items-center justify-center p-12 text-center select-none"
          style={{
            background:
              'linear-gradient(180deg, var(--dusk-top) 0%, var(--dusk-mid) 50%, var(--dusk-low) 100%)',
            color: 'var(--cream)',
          }}
        >
          <div className="text-xs uppercase tracking-[0.25em] text-cream/70 mb-4 font-mono">
            Phase 1 Engine Proof · Scene 01
          </div>
          <h1 className="font-serif text-5xl md:text-7xl font-normal tracking-[0.02em] uppercase text-cream max-w-4xl leading-tight">
            Does the code reproduce the number?
          </h1>
          <p className="mt-6 text-sm font-mono tracking-wider text-cream/80 max-w-xl">
            [SCENE 1 UPPER SHEET] Keep scrolling down to watch this dusk sky tear open with a ragged
            fibre edge.
          </p>
          <div className="mt-8 px-6 py-3 border border-cream/30 text-cream text-xs uppercase font-mono tracking-widest bg-cream/10">
            Scroll Down ↓
          </div>
        </div>
      ),
      teaser: (
        <div
          className="w-full h-full flex items-center justify-between px-10 text-ink font-mono text-xs uppercase tracking-widest select-none"
          style={{ background: 'var(--kraft-light)', color: 'var(--ink)' }}
        >
          <span>↓ Keep Scrolling — The Page Tears Open</span>
          <span>Next: Problem Postcard</span>
        </div>
      ),
    },
    {
      id: 'problem',
      body: (
        <div
          className="w-full h-full flex flex-col items-center justify-center p-12 text-center select-none"
          style={{
            background: 'var(--kraft-light)',
            color: 'var(--ink)',
          }}
        >
          <div className="text-xs uppercase tracking-[0.25em] text-ink-soft mb-4 font-mono">
            No. 02 · Problem Postcard
          </div>
          <h2 className="font-serif text-4xl md:text-6xl font-normal tracking-[0.02em] uppercase text-ink max-w-3xl leading-tight">
            It crashes or the number is wrong.
          </h2>
          <p className="mt-6 text-sm font-mono tracking-wider text-ink-soft max-w-xl">
            [SCENE 2 UPPER SHEET] Kraft paper surface rising from behind as Scene 1 tears away.
          </p>
        </div>
      ),
      teaser: (
        <div
          className="w-full h-full flex items-center justify-between px-10 font-mono text-xs uppercase tracking-widest select-none"
          style={{ background: 'var(--night-top)', color: 'var(--cream)' }}
        >
          <span>↓ Next — How It Works (Field Notes)</span>
          <span>Night Sky Waiting Behind</span>
        </div>
      ),
    },
    {
      id: 'how-it-works',
      body: (
        <div
          className="w-full h-full flex flex-col items-center justify-center p-12 text-center select-none"
          style={{
            background: 'linear-gradient(180deg, var(--night-top) 0%, var(--night-bot) 100%)',
            color: 'var(--cream)',
          }}
        >
          <div className="text-xs uppercase tracking-[0.25em] text-cream/70 mb-4 font-mono">
            No. 03 · Field Notes
          </div>
          <h2 className="font-serif text-4xl md:text-6xl font-normal tracking-[0.02em] uppercase text-cream max-w-3xl leading-tight">
            Retrace every step through the mountain.
          </h2>
          <p className="mt-6 text-sm font-mono tracking-wider text-cream/80 max-w-xl">
            [SCENE 3 UPPER SHEET] Night sky backdrop revealed from behind Kraft paper.
          </p>
        </div>
      ),
      teaser: (
        <div
          className="w-full h-full flex items-center justify-between px-10 font-mono text-xs uppercase tracking-widest select-none"
          style={{ background: 'var(--rose-paper)', color: 'var(--ink)' }}
        >
          <span>↓ Next — The Field Crew</span>
          <span>Roles Sheet</span>
        </div>
      ),
    },
    {
      id: 'roles',
      body: (
        <div
          className="w-full h-full flex flex-col items-center justify-center p-12 text-center select-none"
          style={{ background: 'var(--rose-paper)', color: 'var(--ink)' }}
        >
          <div className="text-xs uppercase tracking-[0.25em] text-ink-soft mb-4 font-mono">
            No. 04 · Roles
          </div>
          <h2 className="font-serif text-4xl md:text-6xl font-normal tracking-[0.02em] uppercase text-ink max-w-3xl leading-tight">
            Meet the Roles
          </h2>
        </div>
      ),
      teaser: (
        <div
          className="w-full h-full flex items-center justify-between px-10 font-mono text-xs uppercase tracking-widest select-none"
          style={{ background: 'var(--ember-top)', color: 'var(--cream)' }}
        >
          <span>↓ Next — Trust & Guardrails</span>
          <span>Ember Sky</span>
        </div>
      ),
    },
    {
      id: 'trust',
      body: (
        <div
          className="w-full h-full flex flex-col items-center justify-center p-12 text-center select-none"
          style={{
            background: 'linear-gradient(180deg, var(--ember-top) 0%, var(--ember-bot) 100%)',
            color: 'var(--cream)',
          }}
        >
          <div className="text-xs uppercase tracking-[0.25em] text-cream/70 mb-4 font-mono">
            No. 05 · Built to be Trusted
          </div>
          <h2 className="font-serif text-4xl md:text-6xl font-normal tracking-[0.02em] uppercase text-cream max-w-3xl leading-tight">
            Built to be Trusted
          </h2>
        </div>
      ),
      teaser: (
        <div
          className="w-full h-full flex items-center justify-between px-10 font-mono text-xs uppercase tracking-widest select-none"
          style={{ background: 'var(--dawn-top)', color: 'var(--ink)' }}
        >
          <span>↓ Next — The Route So Far</span>
          <span>Dawn Sky</span>
        </div>
      ),
    },
    {
      id: 'demo',
      body: (
        <div
          className="w-full h-full flex flex-col items-center justify-center p-12 text-center select-none"
          style={{
            background:
              'linear-gradient(180deg, var(--dawn-top) 0%, var(--dawn-mid) 50%, var(--dawn-low) 100%)',
            color: 'var(--ink)',
          }}
        >
          <div className="text-xs uppercase tracking-[0.25em] text-ink-soft mb-4 font-mono">
            No. 06 · The Route So Far
          </div>
          <h2 className="font-serif text-4xl md:text-6xl font-normal tracking-[0.02em] uppercase text-ink max-w-3xl leading-tight">
            Sample Run & Trail
          </h2>
        </div>
      ),
      teaser: (
        <div
          className="w-full h-full flex items-center justify-between px-10 font-mono text-xs uppercase tracking-widest select-none"
          style={{ background: 'var(--night-deep)', color: 'var(--cream)' }}
        >
          <span>↓ Next — Finale & FAQ</span>
          <span>Night Deep</span>
        </div>
      ),
    },
    {
      id: 'finale',
      body: (
        <div
          className="w-full h-full flex flex-col items-center justify-center p-12 text-center select-none"
          style={{ background: 'var(--night-deep)', color: 'var(--cream)' }}
        >
          <div className="text-xs uppercase tracking-[0.25em] text-cream/70 mb-4 font-mono">
            No. 07 · Finale
          </div>
          <h2 className="font-serif text-4xl md:text-6xl font-normal tracking-[0.02em] uppercase text-cream max-w-3xl leading-tight">
            Proof at the Summit
          </h2>
        </div>
      ),
    },
  ];

  return (
    <div className="relative w-full bg-night-deep">
      <PaperDefs />
      <SceneStage scenes={scenes} />

      {/* Debug panel when ?debug=tear is in URL or always rendered if isDebug */}
      {isDebug && (
        <div
          className="fixed bottom-4 left-4 z-[9999] bg-[#0B1220]/90 border border-cream/30 text-cream p-4 rounded text-xs font-mono shadow-2xl backdrop-blur max-w-sm pointer-events-none"
          style={{ lineHeight: 1.6 }}
        >
          <div className="font-bold text-rust border-b border-cream/20 pb-1 mb-2 tracking-widest uppercase">
            Tear Engine Debug (?debug=tear)
          </div>
          <div>
            scrollY: <span className="text-cream font-bold">{Math.round(scrollY)}px</span>
          </div>
          <div>
            activeScene:{' '}
            <span className="text-cream font-bold">
              {scene} ({SCENES[scene]?.id})
            </span>
          </div>
          <div>
            navTheme: <span className="text-cream font-bold uppercase">{theme}</span>
          </div>
          <div className="mt-2 pt-2 border-t border-cream/10">
            {layout.map((l, i) => {
              if (i >= SCENES.length - 1) return null;
              const t = Math.max(0, Math.min(1, (scrollY - l.tearStart) / (l.tear || 1)));
              return (
                <div key={i} className="flex justify-between text-[11px]">
                  <span>
                    Scene {i} → {i + 1}:
                  </span>
                  <span className={t > 0 && t < 1 ? 'text-rust font-bold' : 'text-cream/60'}>
                    t = {t.toFixed(3)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default DevTear;
