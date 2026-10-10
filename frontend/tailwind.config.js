/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: 'var(--cream)',
        paper: 'var(--paper)',
        'kraft-light': 'var(--kraft-light)',
        kraft: 'var(--kraft)',
        'kraft-tree': 'var(--kraft-tree)',
        'shadow-strip': 'var(--shadow-strip)',
        'rose-paper': 'var(--rose-paper)',

        ink: 'var(--ink)',
        'ink-soft': 'var(--ink-soft)',
        'ink-blue': 'var(--ink-blue)',
        'frame-navy': 'var(--frame-navy)',

        'night-top': 'var(--night-top)',
        'night-bot': 'var(--night-bot)',
        'night-deep': 'var(--night-deep)',

        'dusk-top': 'var(--dusk-top)',
        'dusk-mid': 'var(--dusk-mid)',
        'dusk-low': 'var(--dusk-low)',
        'dawn-top': 'var(--dawn-top)',
        'dawn-mid': 'var(--dawn-mid)',
        'dawn-low': 'var(--dawn-low)',
        'ember-top': 'var(--ember-top)',
        'ember-bot': 'var(--ember-bot)',
        'ember-glow': 'var(--ember-glow)',

        'mtn-far': 'var(--mtn-far)',
        'mtn-tan': 'var(--mtn-tan)',
        'mtn-clay': 'var(--mtn-clay)',
        'mtn-rust': 'var(--mtn-rust)',
        'mtn-lilac': 'var(--mtn-lilac)',
        'mtn-peach': 'var(--mtn-peach)',
        pine: 'var(--pine)',
        cone: 'var(--cone)',
        bark: 'var(--bark)',
        squirrel: 'var(--squirrel)',

        rust: 'var(--rust)',
        'rust-ink': 'var(--rust-ink)',

        solver: 'var(--solver)',
        critic: 'var(--critic)',
        human: 'var(--human)',
        fail: 'var(--fail)',
        ok: 'var(--ok)',
        tool: 'var(--tool)',
      },
      fontFamily: {
        display: ['"Libre Caslon Text"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
