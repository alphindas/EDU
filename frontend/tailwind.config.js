import animate from "tailwindcss-animate";

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "1rem", screens: { "2xl": "1400px" } },
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        bg: "hsl(var(--bg))",
        card: "hsl(var(--card))",
        ink: "hsl(var(--ink))",
        mute: "hsl(var(--mute))",
        line: "hsl(var(--line))",
        soft: "hsl(var(--soft))",
        primary: { DEFAULT: "hsl(var(--ac))", foreground: "hsl(0 0% 100%)" },
        accent2: "hsl(var(--ac2))",
        ok: "hsl(var(--ok))",
        warn: "hsl(var(--warn))",
        bad: "hsl(var(--bad))",
      },
      borderRadius: { xl: "0.9rem", "2xl": "1.2rem" },
      boxShadow: { card: "0 1px 2px hsl(var(--shadow) / .06), 0 8px 24px -12px hsl(var(--shadow) / .25)" },
      keyframes: { fade: { from: { opacity: 0, transform: "translateY(4px)" }, to: { opacity: 1, transform: "none" } } },
      animation: { fade: "fade .25s ease-out both" },
    },
  },
  plugins: [animate],
};
