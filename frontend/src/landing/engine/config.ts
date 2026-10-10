export const NAV_Y = 57;       // px: where the navbar text sits (for theme switching)
export const PAD = 60;         // px extra travel so edges fully leave the screen
export const TEAR_VH = 100;    // scroll distance of one tear, in vh

export const SCENES = [
  { id: 'cover',        nav: 'COVER',        theme: 'dark',  dwellVh: 40,  bandVh: 25 },
  { id: 'problem',      nav: 'PROBLEM',      theme: 'light', dwellVh: 70,  bandVh: 14 },
  { id: 'how-it-works', nav: 'HOW IT WORKS', theme: 'dark',  dwellVh: 80,  bandVh: 14 },
  { id: 'roles',        nav: 'ROLES',        theme: 'light', dwellVh: 70,  bandVh: 14 },
  { id: 'trust',        nav: 'TRUST',        theme: 'dark',  dwellVh: 70,  bandVh: 14 },
  { id: 'demo',         nav: 'DEMO',         theme: 'light', dwellVh: 140, bandVh: 14 },
  { id: 'finale',       nav: 'FAQ',          theme: 'dark',  dwellVh: 0,   bandVh: 0  }, // last: no lower sheet
] as const;

export type SceneDef = (typeof SCENES)[number];
