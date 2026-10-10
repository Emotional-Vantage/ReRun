import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { SCENES } from '../engine/config';
import { scrollToScene } from '../engine/SceneStage';
import { useScene } from '../engine/store';
import { useStaticMode, toggleStaticMode } from '../engine/useStatic';
import { BadgeLogo } from './BadgeLogo';

export const NavbarLanding: React.FC = () => {
  const { scene, theme } = useScene();
  const isStatic = useStaticMode();
  const [mobileOpen, setMobileOpen] = useState(false);

  // The bar itself is transparent and sits over whichever sheet is beneath it,
  // so its ink colour follows the scene theme rather than the bar.
  const isLight = theme === 'light';
  const navColor = isLight ? 'var(--ink)' : 'var(--cream)';

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  return (
    <>
      <header
        className="fixed top-0 left-0 right-0 z-[100] h-[96px] md:h-[110px] pointer-events-none transition-colors duration-300"
        style={{ color: navColor }}
      >
        <div className="max-w-[1440px] mx-auto h-full px-5 sm:px-8 lg:px-10 flex items-center justify-between">
          {/* Left: Brand Wordmark + Loop Mark */}
          <div className="flex items-center gap-3 pointer-events-auto shrink-0">
            <Link
              to="/"
              onClick={(e) => {
                e.preventDefault();
                scrollToScene('cover');
              }}
              className="group flex items-center gap-2.5 focus:outline-none focus:ring-2 focus:ring-rust py-1"
            >
              {/* Loop icon mark */}
              <svg
                viewBox="0 0 24 24"
                className="w-5 h-5 stroke-current fill-none transition-transform group-hover:scale-110"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M4 18 L10 6 L15 14 L18 10 L22 18 Z" />
                <path d="M6 13 C9 7, 18 6, 20 13 C21 17, 16 20, 12 17" strokeDasharray="2 2" />
              </svg>
              <span className="font-mono text-sm font-bold tracking-[0.25em] uppercase">RERUN</span>
            </Link>
          </div>

          {/* Centre: Scene Links */}
          <nav
            aria-label="Main Navigation"
            className="hidden min-[1140px]:flex items-center gap-4 lg:gap-6 xl:gap-7 pointer-events-auto font-mono text-[11px] lg:text-xs uppercase tracking-[0.16em] lg:tracking-[0.2em]"
          >
            {SCENES.map((s, idx) => {
              const isActive = scene === idx;
              return (
                <button
                  key={s.id}
                  onClick={() => scrollToScene(s.id)}
                  className={`relative py-1.5 transition-all duration-200 focus:outline-none focus:ring-1 focus:ring-rust ${
                    isActive ? 'opacity-100 font-bold' : 'opacity-65 hover:opacity-100'
                  }`}
                >
                  {s.nav}
                  {isActive && (
                    <span
                      className="absolute left-0 right-0 bottom-[-2px] h-[2px] bg-current transition-all"
                      aria-hidden="true"
                    />
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right: Motion Toggle + Open App Button + Framed Badge */}
          <div className="flex items-center gap-3 sm:gap-4 pointer-events-auto shrink-0">
            {/* Scroll Animation Toggle Button in Navbar */}
            <button
              type="button"
              onClick={toggleStaticMode}
              className={`hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.15em] border transition-all active:scale-95 ${
                isLight
                  ? 'border-ink/40 text-ink hover:border-ink hover:bg-ink/5'
                  : 'border-cream/40 text-cream hover:border-cream hover:bg-cream/10'
              }`}
              style={{
                clipPath:
                  'polygon(0% 2px, 2px 0%, calc(100% - 2px) 0%, 100% 2px, 100% calc(100% - 2px), calc(100% - 2px) 100%, 2px 100%, 0% calc(100% - 2px))',
              }}
              title={
                isStatic
                  ? 'Enable sticky scroll tear animation'
                  : 'Skip scroll tear animation (switch to static mode)'
              }
            >
              <span className="text-rust font-bold">{isStatic ? '⏸' : '↺'}</span>
              <span>{isStatic ? 'STATIC' : 'TEAR'}</span>
            </button>

            {/* Tactile Primary CTA: Open the App */}
            <Link
              to="/new"
              className={`group flex items-center gap-2 px-4 py-2 font-mono text-xs uppercase tracking-[0.18em] transition-all duration-200 active:scale-95 shadow-md hover:-translate-y-0.5 border border-l-4 border-l-rust ${
                isLight
                  ? 'bg-ink text-cream hover:bg-ink-soft border-ink shadow-[0_3px_10px_rgba(31,42,68,0.25)]'
                  : 'bg-cream text-ink hover:bg-paper border-cream shadow-[0_3px_12px_rgba(0,0,0,0.35)]'
              }`}
              style={{
                clipPath:
                  'polygon(0% 2px, 2px 0%, calc(100% - 3px) 0%, 100% 3px, 100% calc(100% - 2px), calc(100% - 2px) 100%, 2px 100%, 0% calc(100% - 2px))',
              }}
              title="Launch Rerun Reproduction Engine"
            >
              <span className="font-bold">Open the App</span>
              <span className="text-rust font-black group-hover:translate-x-0.5 transition-transform">
                →
              </span>
            </Link>

            {/* Framed Badge Logo */}
            <BadgeLogo className="hidden sm:flex" />

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="min-[1140px]:hidden p-2 text-current focus:outline-none focus:ring-1 focus:ring-rust"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileOpen}
            >
              <svg
                viewBox="0 0 24 24"
                className="w-6 h-6 stroke-current fill-none"
                strokeWidth="1.5"
              >
                {mobileOpen ? (
                  <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                ) : (
                  <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" strokeLinejoin="round" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Drawer (Paper Sheet with Torn Bottom Edge) */}
      {mobileOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-x-0 top-0 z-[99] bg-paper text-ink p-8 shadow-2xl min-[1100px]:hidden border-b border-kraft"
          style={{
            clipPath:
              'polygon(0 0, 100% 0, 100% 92%, 90% 95%, 80% 91%, 70% 96%, 60% 92%, 50% 97%, 40% 93%, 30% 96%, 20% 92%, 10% 95%, 0 91%)',
          }}
        >
          <div className="flex justify-between items-center mb-8 border-b border-kraft pb-4">
            <span className="font-mono text-sm uppercase tracking-widest font-bold text-ink">
              RERUN · FIELD INDEX
            </span>
            <button
              onClick={() => setMobileOpen(false)}
              className="p-1 text-ink focus:outline-none"
              aria-label="Close menu"
            >
              ✕
            </button>
          </div>
          <div className="flex flex-col gap-4 font-mono text-sm uppercase tracking-widest">
            {SCENES.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setMobileOpen(false);
                  scrollToScene(s.id);
                }}
                className="text-left py-2 border-b border-kraft/40 hover:text-rust transition-colors"
              >
                {s.nav}
              </button>
            ))}
            <Link
              to="/new"
              onClick={() => setMobileOpen(false)}
              className="mt-4 px-4 py-3 bg-ink text-cream text-center text-xs uppercase tracking-widest font-bold"
            >
              Open the App →
            </Link>
          </div>
        </div>
      )}
    </>
  );
};
