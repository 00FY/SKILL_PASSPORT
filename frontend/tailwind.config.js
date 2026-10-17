/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: "#131314",
        surface: {
          lowest: "#0e0e0f",
          low: "#101112",
          card: "#151617",
          container: "#201f21",
          high: "#2a2a2b",
          highest: "#353436",
        },
        border: {
          dark: "#1B1C1E",
          light: "#232426",
          subtle: "rgba(255, 255, 255, 0.08)",
        },
        accent: {
          cyan: "#50d8e9",
          violet: "#bec2ff",
          indigo: "#5E6BFF",
          amber: "#ffb689",
          error: "#ffb4ab",
          errorDark: "#93000a",
        },
        romer: {
          text: "#e5e2e3",
          muted: "#c6c5d8",
          dim: "#9A9DA3",
        }
      },
      fontFamily: {
        heading: ['Manrope', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      letterSpacing: {
        tighter: '-0.05em',
        tight: '-0.03em',
        widest: '0.12em',
      }
    },
  },
  plugins: [],
}
