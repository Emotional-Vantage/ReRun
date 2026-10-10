import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { SCENES, NAV_Y, PAD, TEAR_VH } from './config';
import { getTear } from './tear';
import { TearEdge } from './TearEdge';
import { sceneStore } from './store';

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = (t: number) => t * t * (3 - 2 * t);

/**
 * Each scene owns a dwell band (it sits still) followed by a tear band (its
 * sheet lifts away). Scroll offsets are absolute pixels so the layout has to be
 * recomputed whenever the viewport height changes.
 */
export function computeLayout(vh: number) {
  let acc = 0;
  return SCENES.map((s, i) => {
    const dwell = (s.dwellVh / 100) * vh;
    const tear = i < SCENES.length - 1 ? (TEAR_VH / 100) * vh : 0;
    const o = {
      start: acc,
      tearStart: acc + dwell,
      tear,
      end: acc + dwell + tear,
      band: (s.bandVh / 100) * vh,
    };
    acc = o.end;
    return o;
  });
}

export const trackHeight = (vh: number) => {
  const L = computeLayout(vh);
  return L[L.length - 1].start + vh;
};

export function scrollToScene(id: string) {
  const i = SCENES.findIndex((s) => s.id === id);
  if (i < 0) return;
  const top = computeLayout(window.innerHeight)[i].start;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.dispatchEvent(new CustomEvent('rerun:scene-jump'));
  window.scrollTo({ top, behavior: reduce ? 'auto' : 'smooth' });
}

export type SceneContent = { id: string; body: ReactNode; teaser?: ReactNode };

interface SceneElements {
  root: HTMLElement;
  n: HTMLElement;
  upper: HTMLElement;
  lower?: HTMLElement;
}

export function SceneStage({ scenes }: { scenes: SceneContent[] }) {
  const els = useRef<SceneElements[]>([]);
  const [vh, setVh] = useState(() => (typeof window !== 'undefined' ? window.innerHeight : 900));

  useEffect(() => {
    const f = () => setVh(window.innerHeight);
    window.addEventListener('resize', f);
    return () => window.removeEventListener('resize', f);
  }, []);

  const layout = useMemo(() => computeLayout(vh), [vh]);

  useLayoutEffect(() => {
    let raf = 0;

    // Written straight to style properties inside a rAF rather than through
    // React state: this runs on every scroll frame and must not re-render.
    const apply = () => {
      raf = 0;
      const y = window.scrollY;
      const last = SCENES.length - 1;
      let current = last;
      for (let i = 0; i < last; i++) {
        if (y < layout[i].end) {
          current = i;
          break;
        }
      }

      SCENES.forEach((_, i) => {
        const el = els.current[i];
        if (!el || !el.root || !el.upper || !el.n) return;
        const L = layout[i];
        const t = i < last ? clamp((y - L.tearStart) / L.tear) : 0;
        const e = ease(t);

        // Only the current sheet and the one behind it can be seen; everything
        // else is hidden and made inert so it cannot take focus or a click.
        const visible = i === current || i === current + 1;
        el.root.style.visibility = visible ? 'visible' : 'hidden';
        el.root.toggleAttribute('inert', i !== current);
        el.root.style.setProperty('--s', String(clamp((y - L.start) / ((L.end - L.start) || 1))));
        el.root.style.setProperty('--te', String(Math.sin(Math.PI * e)));
        el.upper.style.transform = `translate3d(0,${(-e * (vh + PAD)).toFixed(
          1
        )}px,0) rotate(${(e * 0.4).toFixed(3)}deg)`;
        if (el.lower) {
          el.lower.style.transform = `translate3d(0,${(
            Math.min(e / 0.75, 1) * (L.band + PAD)
          ).toFixed(1)}px,0)`;
        }
        if (i > 0) {
          const pe = ease(clamp((y - layout[i - 1].tearStart) / layout[i - 1].tear));
          el.n.style.setProperty('--p', String(1 - pe));
        }
      });

      // navbar theme: whichever sheet is under the navbar text
      const Lc = layout[current];
      const ec = current < last ? ease(clamp((y - Lc.tearStart) / Lc.tear)) : 0;
      const edgeY = vh - Lc.band - ec * (vh + PAD);
      const theme =
        edgeY > NAV_Y || current === last ? SCENES[current].theme : SCENES[current + 1].theme;
      sceneStore.set({ scene: ec > 0.5 && current < last ? current + 1 : current, theme });
    };

    /*
      Settle a half-torn page.

      Stopping mid-tear used to leave the sheet frozen at whatever fraction the
      scroll happened to end on, so the reader was left looking at two half
      pages and neither scene's content. Once scrolling stops inside a tear
      band we commit to one side: past SNAP_AT the tear finishes, before it the
      page falls back shut. The threshold is deliberately below half, because a
      tear that is already a third open reads as "going forward".

      Only an idle scroll triggers this, never a frame mid-gesture, and the
      programmatic scroll it fires is ignored by the next settle so the two
      cannot chase each other. Anyone who has asked for less motion keeps the
      free position they scrolled to.
    */
    const SNAP_AT = 0.4;
    const SETTLE_MS = 140;
    let settleTimer = 0;
    let snapping = false;
    let lastY = window.scrollY;
    let goingDown = true;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    const settle = () => {
      settleTimer = 0;
      if (snapping || reduceMotion.matches) return;

      const y = window.scrollY;
      const last = SCENES.length - 1;

      // The page cannot be scrolled past its end, so a tear left open at the
      // very bottom has nowhere to snap forward to. Leave it alone.
      const maxY = document.documentElement.scrollHeight - window.innerHeight;

      for (let i = 0; i < last; i++) {
        const L = layout[i];
        const t = (y - L.tearStart) / L.tear;
        if (t <= 0.02 || t >= 0.98) continue;

        /*
          The threshold is measured along the direction of travel, not from the
          top of the tear. A flat "past 40% goes forward" rule reads correctly
          going down but traps you going up: leaving a scene means scrolling
          back through 60% of the tear in a single gesture, and anything less
          is pulled forward again, which feels like the page refusing to let
          you back. Mirroring it means either direction commits once you have
          pulled the page 40% of the way there.
        */
        const commitForward = goingDown ? t >= SNAP_AT : t > 1 - SNAP_AT;
        const target = commitForward ? L.end : L.tearStart;
        if (Math.abs(target - y) < 1 || target > maxY + 1) return;

        snapping = true;
        window.scrollTo({ top: target, behavior: 'smooth' });
        // Released once the smooth scroll has had time to land. A plain timeout
        // rather than scrollend, which Safari does not fire.
        window.setTimeout(() => {
          snapping = false;
        }, 700);
        return;
      }
    };

    const onScroll = () => {
      const y = window.scrollY;
      // A snap in progress is our own scrolling, not the reader's; letting it
      // set the direction would make the snap decide its own threshold.
      if (!snapping && y !== lastY) goingDown = y > lastY;
      lastY = y;

      if (!raf) raf = requestAnimationFrame(apply);
      if (settleTimer) clearTimeout(settleTimer);
      settleTimer = window.setTimeout(settle, SETTLE_MS);
    };

    // A deliberate jump from the dot nav or a button is already a committed
    // destination; it must not be second-guessed by the settle that follows it.
    const onProgrammatic = () => {
      snapping = true;
      window.setTimeout(() => {
        snapping = false;
      }, 900);
    };
    window.addEventListener('rerun:scene-jump', onProgrammatic);

    window.addEventListener('scroll', onScroll, { passive: true });
    apply();
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('rerun:scene-jump', onProgrammatic);
      if (settleTimer) clearTimeout(settleTimer);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [layout, vh]);

  const register = (i: number, key: keyof SceneElements) => (r: HTMLDivElement | null) => {
    if (!r) return;
    if (!els.current[i]) els.current[i] = {} as SceneElements;
    els.current[i][key] = r;
  };

  return (
    <div className="track" style={{ height: trackHeight(vh) }}>
      <div className="stage">
        {scenes.map((s, i) => {
          const last = i === SCENES.length - 1;
          const upperTear = getTear(1000 + i * 7, 'bottom');
          const lowerTear = getTear(1000 + i * 7 + 3, 'top');
          return (
            <div
              key={s.id}
              className="scene"
              style={{
                zIndex: SCENES.length - i,
                ['--band' as string]: `${SCENES[i].bandVh}svh`,
              }}
              ref={register(i, 'root')}
            >
              <div className="scene-n" ref={register(i, 'n')}>
                {!last && (
                  <div className="scene-lower" ref={register(i, 'lower')}>
                    <div
                      className="body"
                      style={{ clipPath: lowerTear.clip, WebkitClipPath: lowerTear.clip }}
                    >
                      {s.teaser}
                    </div>
                    <TearEdge seed={1000 + i * 7 + 3} edge="top" />
                  </div>
                )}
                <div
                  className="scene-upper"
                  ref={register(i, 'upper')}
                  style={last ? { height: '100svh' } : undefined}
                >
                  <div
                    className="body"
                    style={
                      last ? undefined : { clipPath: upperTear.clip, WebkitClipPath: upperTear.clip }
                    }
                  >
                    {s.body}
                  </div>
                  {!last && <TearEdge seed={1000 + i * 7} edge="bottom" />}
                </div>
              </div>
            </div>
          );
        })}
        <div className="grain" aria-hidden="true" />
      </div>
    </div>
  );
}
