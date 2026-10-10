import { useSyncExternalStore } from 'react';

type S = { scene: number; theme: 'light' | 'dark' };
let s: S = { scene: 0, theme: 'dark' };
const subs = new Set<() => void>();

export const sceneStore = {
  get: () => s,
  set(n: S) {
    if (n.scene === s.scene && n.theme === s.theme) return;
    s = n;
    document.documentElement.dataset.navTheme = n.theme;
    subs.forEach((f) => f());
  },
  subscribe(f: () => void) {
    subs.add(f);
    return () => {
      subs.delete(f);
    };
  },
};

export const useScene = () => useSyncExternalStore(sceneStore.subscribe, sceneStore.get);
