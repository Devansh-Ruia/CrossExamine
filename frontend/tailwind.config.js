/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./pages/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    // Outside extend intentionally -- this app is monospace-only
    fontFamily: {
      mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
    },
    extend: {
      colors: {
        bg: '#0a0a0f',
        'bg-raised': '#0f0f18',
        border: '#1e1e2a',
        'text-primary': '#e8e8e8',
        'text-dim': '#888888',
        'text-muted': '#555555',
        'text-ghost': '#333333',
        attack: '#e84040',
        defense: '#9b5cf6',
        amber: '#d4a017',
        low: '#4a8c5c',
      },
      fontSize: {
        label: ['11px', { lineHeight: '1.5', letterSpacing: '0.15em' }],
        body: ['13px', { lineHeight: '1.5' }],
        reading: ['14px', { lineHeight: '1.6' }],
      },
    },
  },
  plugins: [],
};
