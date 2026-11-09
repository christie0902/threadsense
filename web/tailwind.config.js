/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Slate-teal grounds (lighter than the earlier near-black) so panels, tiles and controls separate clearly.
        ink: { 950: '#0e1822', 900: '#15222f', 850: '#1a2a38', 800: '#213343', 700: '#2b4052' },
      },
      fontFamily: {
        sans: ['"Segoe UI Variable Text"', '"Segoe UI"', 'Inter', 'system-ui', '-apple-system', 'Roboto', 'sans-serif'],
        display: ['"Segoe UI Variable Display"', '"Segoe UI"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"Cascadia Code"', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      keyframes: {
        drift: { '0%,100%': { transform: 'rotate(0deg) scale(1)' }, '50%': { transform: 'rotate(180deg) scale(1.04)' } },
        breathe: { '0%,100%': { opacity: '0.55' }, '50%': { opacity: '1' } },
      },
      animation: { drift: 'drift 36s linear infinite', breathe: 'breathe 4.5s ease-in-out infinite' },
    },
  },
  plugins: [],
}
