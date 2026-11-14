import { create } from "zustand";
import { persist } from "zustand/middleware";

/** 12 colour palettes; "ocean" (sky blue + navy) is the default. Swatch = [main, partner] for the picker preview. */
export const PALETTES = {
  ocean: ["hsl(199 89% 48%)", "hsl(222 62% 32%)"],
  sky: ["hsl(205 85% 55%)", "hsl(215 60% 38%)"],
  mint: ["hsl(158 64% 40%)", "hsl(190 70% 30%)"],
  forest: ["hsl(142 55% 36%)", "hsl(150 45% 24%)"],
  teal: ["hsl(180 70% 36%)", "hsl(200 60% 28%)"],
  indigo: ["hsl(232 70% 56%)", "hsl(245 55% 34%)"],
  violet: ["hsl(258 70% 60%)", "hsl(222 62% 32%)"],
  lavender: ["hsl(270 55% 64%)", "hsl(290 40% 42%)"],
  rose: ["hsl(340 72% 56%)", "hsl(280 50% 40%)"],
  coral: ["hsl(6 80% 60%)", "hsl(350 55% 40%)"],
  sunset: ["hsl(17 88% 55%)", "hsl(340 60% 40%)"],
  mango: ["hsl(38 92% 48%)", "hsl(22 80% 38%)"],
} as const;
export type Accent = keyof typeof PALETTES;
export const ACCENTS = Object.keys(PALETTES) as Accent[];
export const DEFAULT_ACCENT: Accent = "ocean";

interface ThemeState { dark: boolean; accent: Accent; toggle: () => void; setDark: (d: boolean) => void; setAccent: (a: Accent) => void }

/** Light theme + ocean palette by default. Saved in the browser so each user keeps their choice. */
export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      dark: false,
      accent: DEFAULT_ACCENT,
      toggle: () => set((s) => ({ dark: !s.dark })),
      setDark: (dark) => set({ dark }),
      setAccent: (accent) => set({ accent: accent in PALETTES ? accent : DEFAULT_ACCENT }),
    }),
    { name: "edunest-theme-v2" },
  ),
);

export function applyTheme(dark: boolean, accent: Accent) {
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.dataset.accent = accent in PALETTES ? accent : DEFAULT_ACCENT;
}
