/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['"Be Vietnam Pro"', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'] },
      colors: {
        ink: '#0f2438', text: '#334155', muted: '#64748b', line: '#e3e8ef', canvas: '#f3f5f8',
        primary: '#2a78d6', primaryDark: '#1c5cab', primarySoft: '#e8f1fc',
        ai: '#6250d6', aiSoft: '#efedfc',
        neg: '#d64545', pos: '#2a78d6',
      },
      boxShadow: { card: '0 1px 2px rgba(15,36,56,0.05), 0 1px 1px rgba(15,36,56,0.03)' },
    },
  },
  plugins: [],
}
