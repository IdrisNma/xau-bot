/** @type {import('tailwindcss').Config} */
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0e14",
        panel: "#0f1620",
        panel2: "#131b27",
        border: "#1f2a37",
        accent: "#22d3a8",
        danger: "#ef4444",
        warn: "#f59e0b",
        info: "#60a5fa",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
