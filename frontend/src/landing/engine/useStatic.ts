import { useSyncExternalStore } from 'react';

const Q = '(max-width: 767px), (prefers-reduced-motion: reduce)';
const sub = (f: () => void) => {
  const m = matchMedia(Q);
  m.addEventListener('change', f);
  return () => m.removeEventListener('change', f);
};

export const useStaticMode = () => {
  const mq = useSyncExternalStore(
    sub,
    () => matchMedia(Q).matches,
    () => false
  );
  let skip = false;
  try {
    skip = localStorage.getItem('skip-anim') === '1';
  } catch {
    /* ignore */
  }
  return mq || skip;
};

export const toggleStaticMode = () => {
  try {
    const current = localStorage.getItem('skip-anim') === '1';
    localStorage.setItem('skip-anim', current ? '0' : '1');
    window.location.reload();
  } catch {
    /* ignore */
  }
};
